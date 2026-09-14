"""135 战法 13 种经典形态 + 若干易代码化补充形态。"""

from __future__ import annotations

import pandas as pd

from njm135.core.indicators import death_cross, golden_cross
from njm135.core.params import PatternParams


def _atr(bars: pd.DataFrame, window: int) -> pd.Series:
    prev = bars["close"].shift(1)
    tr = pd.concat(
        [
            bars["high"] - bars["low"],
            (bars["high"] - prev).abs(),
            (bars["low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window, min_periods=1).mean()


def _recent(cond: pd.Series, window: int) -> pd.Series:
    return cond.fillna(False).rolling(window, min_periods=1).max().astype(bool)


def _flat(ma: pd.Series, lookback: int, pct: float) -> pd.Series:
    """仅斜率接近 0，不含单边上行。"""
    delta = (ma - ma.shift(lookback)).abs() / ma.replace(0, pd.NA)
    return (delta < pct).fillna(False)


def _hook_up(ma: pd.Series, lookback: int) -> pd.Series:
    """由降转升（勾头）。"""
    prev = ma.shift(lookback)
    older = ma.shift(lookback * 2)
    return (ma >= prev) & (prev <= older)


def _near(a: pd.Series, b: pd.Series, close: pd.Series, atr: pd.Series, params: PatternParams) -> pd.Series:
    dist = (a - b).abs()
    return (dist / close <= params.near_pct) | (dist <= params.near_atr * atr)


def _vol_ratio(bars: pd.DataFrame, window: int) -> pd.Series:
    if "volume" not in bars.columns:
        return pd.Series(1.0, index=bars.index)
    ma = bars["volume"].rolling(window, min_periods=1).mean()
    return bars["volume"] / ma.replace(0, pd.NA)


def _first_of_run(condition: pd.Series) -> pd.Series:
    """连续满足条件时只保留第一根，避免同一形态重复记账。"""
    current = condition.fillna(False).astype(bool)
    previous = current.shift(1, fill_value=False)
    return current & ~previous


def detect_patterns(bars: pd.DataFrame, params: PatternParams | None = None) -> pd.DataFrame:
    """要求已含 ``ma13`` / ``ma34`` / ``ma55``。突破一律收盘确认。"""
    for col in ("open", "high", "low", "close", "ma13", "ma34", "ma55"):
        if col not in bars.columns:
            raise ValueError(f"缺少列: {col}")

    p = params or PatternParams()
    out = bars.copy()
    o, h, low, c = out["open"], out["high"], out["low"], out["close"]
    ma13, ma34, ma55 = out["ma13"], out["ma34"], out["ma55"]
    yang = c >= o
    yin = c < o
    ret = c.pct_change()
    atr = _atr(out, p.atr_window)
    vol_r = _vol_ratio(out, p.volume_window)
    has_vol = "volume" in out.columns
    vol_expand = (vol_r >= p.volume_expand) if has_vol else pd.Series(True, index=out.index)
    vol_shrink = (vol_r <= p.volume_shrink) if has_vol else pd.Series(True, index=out.index)

    ma_max = pd.concat([ma13, ma34, ma55], axis=1).max(axis=1)
    ma_min = pd.concat([ma13, ma34, ma55], axis=1).min(axis=1)
    ma_spread = (ma_max - ma_min) / c.replace(0, pd.NA)
    high_zone = (c / c.rolling(p.high_lookback, min_periods=1).max() > (1.0 - p.high_bias)) & (
        (c / ma55 - 1.0) > p.high_bias
    )

    close_up_13 = (c > ma13) & (c.shift(1) <= ma13.shift(1))
    close_up_55 = (c > ma55) & (c.shift(1) <= ma55.shift(1))

    # --- 底部 ---
    recently_deep = _recent((c / ma13 - 1.0) < -p.deep_below_13, p.downtrend_lookback)
    hongxing_candidate = (
        (ma55 > ma34)
        & (ma34 > ma13)
        & (_flat(ma13, p.flatten_lookback, p.flatten_pct) | _hook_up(ma13, p.flatten_lookback))
        & close_up_13
        & yang
        & recently_deep
    )
    # 候选出现后等待 N 根收盘均守住 MA13，信号标在确认根。只引用当前和历史，
    # 因此是延迟确认而不是把未来结果回填到候选根。
    confirm_bars = max(1, p.hongxing_confirm_bars)
    above_13 = c > ma13
    stayed_above = (
        above_13.rolling(confirm_bars, min_periods=confirm_bars).min().fillna(0).astype(bool)
    )
    out["hongxing_chuqiang"] = hongxing_candidate.shift(confirm_bars - 1, fill_value=False) & stayed_above

    small_yang = yang & ret.between(0.0, p.small_yang_max)
    out["mayi_shangshu"] = (
        (ma_spread < p.ant_ma_spread)
        & (small_yang.rolling(p.ant_yang_bars, min_periods=p.ant_yang_bars).sum() == p.ant_yang_bars)
        & (c > ma55)
        & ((c.shift(1) < ma55.shift(1)) | (c.shift(2) < ma55.shift(2)))
    )

    # --- 启动 ---
    out["heike_dianji"] = (
        _recent(close_up_55, 15)
        & yin
        & vol_shrink
        & (c > ma55)
        & _near(c, ma55, c, atr, p)
        & _near(ma13, ma55, c, atr, p)
    )

    out["hongyi_xianv"] = (
        _flat(ma55, 5, 0.01)
        & golden_cross(ma13, ma55)
        & yang
        & (ret > 0.005)
        & vol_expand
    )

    # --- 拉升 ---
    out["haidi_laoyue"] = (
        _recent(death_cross(ma13, ma34), p.event_lookback)
        & _recent(death_cross(ma13, ma55), p.event_lookback)
        & _flat(ma34, 5, 0.02)
        & _flat(ma55, 5, 0.02)
        & golden_cross(ma13, ma55)
        & vol_expand
    )

    out["junxian_huhuan"] = golden_cross(ma34, ma55)

    yy1 = (o < ma13) & (c > ma13)
    yy2 = (o < ma34) & (c > ma34)
    yy3 = (o < ma55) & (c > ma55)
    out["yi_yang_chuan_sanxian"] = yang & yy1 & yy2 & yy3

    converged = (ma_spread < p.converge_pct).rolling(p.converge_bars, min_periods=5).mean() > 0.7
    all_up = (ma13 >= ma13.shift(1)) & (ma34 >= ma34.shift(1)) & (ma55 >= ma55.shift(1))
    out["sanxian_tuijin"] = converged & all_up & (out["yi_yang_chuan_sanxian"] | ((c > ma_max) & yang))

    out["meikai_erdu"] = (
        _recent(golden_cross(ma13, ma55), p.event_lookback)
        & _recent(death_cross(ma13, ma34), 20)
        & golden_cross(ma13, ma34)
        & (ma34 > ma55)
    )

    # --- 整理 ---
    around_13 = _near(c, ma13, c, atr, p)
    small_range = (c.pct_change().abs().rolling(p.digest_bars).max() < 0.03)
    mixed = (
        yang.rolling(p.digest_bars, min_periods=p.digest_bars).sum().between(1, p.digest_bars - 1)
    )
    out["zou_sifang"] = (
        (ma13 > ma34)
        & _flat(ma13, p.flatten_lookback, p.flatten_pct)
        & around_13.rolling(p.digest_bars).min().astype(bool)
        & small_range
        & mixed
    )

    three_yin = yin & yin.shift(1) & yin.shift(2)
    out["langzi_huitou"] = (
        (ma34 > ma55)
        & three_yin.shift(1)
        & yang
        & (low <= ma55 * (1.0 + p.near_pct))
        & (c > ma55)
        & vol_expand
    )

    # --- 顶部 ---
    upper = (h / c.replace(0, pd.NA) - 1.0) > p.upper_shadow
    out["yizhi_duxiu"] = (
        high_zone
        & yang
        & upper
        & (c > ma13 * (1.0 + p.detach_ma13))
        & (ma13 > ma34)
        & vol_expand
    )

    gap = o / c.shift(1) - 1.0
    out["dushang_gaolou"] = (
        high_zone
        & (gap > p.gap_up)
        & yin
        & ((o / c - 1.0) > p.yin_body)
        & (o > ma_max)
    )

    bias_1355 = (ma13 - ma55) / ma13.replace(0, pd.NA)
    ema12 = c.ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = c.ewm(span=26, adjust=False, min_periods=26).mean()
    dif = ema12 - ema26
    macd_turning_down = (dif < dif.shift(1)) & (dif.shift(1) >= dif.shift(2))
    out["jianhao_jiushou"] = (
        (ma13 > ma34)
        & (ma34 > ma55)
        & (bias_1355 > p.jianhao_bias)
        & macd_turning_down
    )

    out["yi_yin_po_sanxian"] = yin & (o > ma_max) & (c < ma_min)
    out["yi_jian_chuan_xin"] = (
        yin
        & (h > ma_max)
        & (c < ma_min)
        & ((o - c) / c.replace(0, pd.NA) > 0.03)
        & (ma13.shift(1) > ma34.shift(1))
    )
    out["fendao_yangbiao"] = death_cross(ma13, ma34)
    # 离场线用「收盘处于均线下方」这个状态，而不是「向下穿越」那一根。
    # 穿越式会漏掉在均线下方建仓的情形（如黑客点击回踩），持仓可能一直没有离场条件。
    out["break_ma13"] = c < ma13
    out["break_ma34"] = c < ma34
    out["break_ma55"] = c < ma55

    bool_cols = [
        "hongxing_chuqiang",
        "mayi_shangshu",
        "heike_dianji",
        "hongyi_xianv",
        "haidi_laoyue",
        "junxian_huhuan",
        "sanxian_tuijin",
        "meikai_erdu",
        "zou_sifang",
        "langzi_huitou",
        "yizhi_duxiu",
        "dushang_gaolou",
        "jianhao_jiushou",
        "yi_yang_chuan_sanxian",
        "yi_yin_po_sanxian",
        "yi_jian_chuan_xin",
        "fendao_yangbiao",
        "break_ma13",
        "break_ma34",
        "break_ma55",
    ]
    for col in bool_cols:
        out[col] = out[col].fillna(False).astype(bool)

    # 形态是事件；连续多根满足只应记录一次。跌破均线则必须保留为状态，
    # 因为持仓可能在线下建立，后续每根都需要提供离场条件。
    for col in bool_cols:
        if not col.startswith("break_ma"):
            out[col] = _first_of_run(out[col])
    return out
