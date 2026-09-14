"""135 均线系统：13 / 34 / 55，参数来自斐波那契数列。"""

from __future__ import annotations

from typing import Literal

import pandas as pd

MAType = Literal["sma", "ema"]

SHORT_WINDOW = 13
MID_WINDOW = 34
LONG_WINDOW = 55


def sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window=window, min_periods=window).mean()


def ema(close: pd.Series, window: int) -> pd.Series:
    return close.ewm(span=window, adjust=False, min_periods=window).mean()


def _ma(close: pd.Series, window: int, ma_type: MAType) -> pd.Series:
    if ma_type == "sma":
        return sma(close, window)
    if ma_type == "ema":
        return ema(close, window)
    raise ValueError(f"不支持的均线类型: {ma_type}")


def add_ma_system(
    bars: pd.DataFrame,
    *,
    ma_type: MAType = "sma",
    short: int = SHORT_WINDOW,
    mid: int = MID_WINDOW,
    long: int = LONG_WINDOW,
    slope_lookback: int = 1,
) -> pd.DataFrame:
    """在 OHLCV 行情上计算 13/34/55 均线及多空排列。"""
    required = {"open", "high", "low", "close"}
    missing = required - set(bars.columns)
    if missing:
        raise ValueError(f"缺少必要列: {sorted(missing)}")

    out = bars.copy()
    close = out["close"].astype(float)
    out["ma13"] = _ma(close, short, ma_type)
    out["ma34"] = _ma(close, mid, ma_type)
    out["ma55"] = _ma(close, long, ma_type)

    out["ma13_up"] = out["ma13"] >= out["ma13"].shift(slope_lookback)
    out["ma34_up"] = out["ma34"] >= out["ma34"].shift(slope_lookback)
    out["ma55_up"] = out["ma55"] >= out["ma55"].shift(slope_lookback)

    out["bull_align"] = (
        (out["ma13"] > out["ma34"])
        & (out["ma34"] > out["ma55"])
        & out["ma13_up"]
        & out["ma34_up"]
        & out["ma55_up"]
    )
    out["bear_align"] = (
        (out["ma13"] < out["ma34"])
        & (out["ma34"] < out["ma55"])
        & ~out["ma13_up"]
        & ~out["ma34_up"]
        & ~out["ma55_up"]
    )
    return out


def golden_cross(fast: pd.Series, slow: pd.Series) -> pd.Series:
    return (fast > slow) & (fast.shift(1) <= slow.shift(1))


def death_cross(fast: pd.Series, slow: pd.Series) -> pd.Series:
    return (fast < slow) & (fast.shift(1) >= slow.shift(1))


def add_macd(
    bars: pd.DataFrame,
    *,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """DIF / DEA / MACD 柱（柱线为 (DIF-DEA)*2，通达信口径）。"""
    out = bars.copy()
    close = out["close"].astype(float)
    dif = ema(close, fast) - ema(close, slow)
    dea = dif.ewm(span=signal, adjust=False, min_periods=signal, ignore_na=True).mean()
    out["macd_dif"] = dif
    out["macd_dea"] = dea
    out["macd_hist"] = (dif - dea) * 2.0
    return out


def add_bollinger(
    bars: pd.DataFrame,
    *,
    window: int = 20,
    num_std: float = 2.0,
) -> pd.DataFrame:
    """收盘价布林带：中轨 SMA，上下轨 ±N 倍标准差。"""
    out = bars.copy()
    close = out["close"].astype(float)
    mid = close.rolling(window=window, min_periods=window).mean()
    std = close.rolling(window=window, min_periods=window).std(ddof=0)
    out["boll_mid"] = mid
    out["boll_upper"] = mid + num_std * std
    out["boll_lower"] = mid - num_std * std
    return out


def true_range(bars: pd.DataFrame) -> pd.Series:
    prev = bars["close"].shift(1)
    return pd.concat(
        [
            bars["high"] - bars["low"],
            (bars["high"] - prev).abs(),
            (bars["low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)


def add_volatility(
    bars: pd.DataFrame,
    *,
    window: int = 14,
    baseline: int = 55,
) -> pd.DataFrame:
    """ATR% = ATR(window) / 收盘价 × 100。

    柱高表示**最近已经走了多大振幅**（占价格的百分比），不是对未来暴涨暴跌的预测。
    ``atr_pct_ma`` 是 ATR% 自己的均线，用来判断当前波动高于还是低于这段行情的常态。
    """
    out = bars.copy()
    close = out["close"].astype(float).replace(0, pd.NA)
    atr = true_range(out).rolling(window=window, min_periods=window).mean()
    atr_pct = atr / close * 100.0
    out["atr"] = atr
    out["atr_pct"] = atr_pct
    out["atr_pct_ma"] = sma(atr_pct, baseline)
    return out
