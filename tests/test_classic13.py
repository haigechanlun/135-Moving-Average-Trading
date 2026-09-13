from __future__ import annotations

import pandas as pd

from njm135.core.catalog import CLASSIC_13, classic_keys
from njm135.core.indicators import add_ma_system
from njm135.core.patterns import detect_patterns


def _bars(close, open_=None, high=None, low=None, volume=None) -> pd.DataFrame:
    close = pd.Series(close, dtype=float)
    if open_ is None:
        open_ = close.shift(1).fillna(close.iloc[0])
    else:
        open_ = pd.Series(open_, dtype=float)
    if high is None:
        high = pd.concat([open_, close], axis=1).max(axis=1) * 1.002
    if low is None:
        low = pd.concat([open_, close], axis=1).min(axis=1) * 0.998
    data = {"open": open_, "high": high, "low": low, "close": close}
    if volume is not None:
        data["volume"] = volume
    return pd.DataFrame(data)


def test_classic_13_columns_exist() -> None:
    close = pd.Series(range(1, 121), dtype=float)
    framed = detect_patterns(add_ma_system(_bars(close)))
    for key in classic_keys():
        assert key in framed.columns
    assert len(CLASSIC_13) == 13


def test_yi_yang_and_yi_yin() -> None:
    flat = [10.0] * 80
    # 阳线从均线簇下穿到上
    close = flat + [10.6]
    open_ = [10.0] * 80 + [9.4]
    high = [10.05] * 80 + [10.7]
    low = [9.95] * 80 + [9.35]
    framed = detect_patterns(add_ma_system(_bars(close, open_=open_, high=high, low=low)))
    assert bool(framed["yi_yang_chuan_sanxian"].iloc[-1])

    close2 = flat + [9.4]
    open_2 = [10.0] * 80 + [10.6]
    high2 = [10.05] * 80 + [10.65]
    low2 = [9.95] * 80 + [9.35]
    framed2 = detect_patterns(add_ma_system(_bars(close2, open_=open_2, high=high2, low=low2)))
    assert bool(framed2["yi_yin_po_sanxian"].iloc[-1])


def test_jianhao_needs_macd_weakening() -> None:
    up = list(range(1, 90))
    stall = [89, 88, 86, 83, 79, 74, 68]
    close = pd.Series(up + stall, dtype=float)
    framed = detect_patterns(add_ma_system(_bars(close)))
    assert framed["jianhao_jiushou"].sum() >= 1


def test_yizhi_and_dushang_need_high_zone() -> None:
    base = list(range(20, 80))
    # 一枝独秀：高位阳线长上影
    close = base + [90.0]
    open_ = [float(x) for x in base] + [88.0]
    high = [float(x) + 0.5 for x in base] + [96.0]
    low = [float(x) - 0.5 for x in base] + [87.5]
    vol = [100.0] * len(base) + [300.0]
    framed = detect_patterns(add_ma_system(_bars(close, open_=open_, high=high, low=low, volume=vol)))
    assert bool(framed["yizhi_duxiu"].iloc[-1])

    # 独上高楼：高位跳空高开收阴
    close2 = base + [85.0]
    open_2 = [float(x) for x in base] + [92.0]
    high2 = [float(x) + 0.3 for x in base] + [92.2]
    low2 = [float(x) - 0.3 for x in base] + [84.5]
    framed2 = detect_patterns(add_ma_system(_bars(close2, open_=open_2, high=high2, low=low2)))
    assert bool(framed2["dushang_gaolou"].iloc[-1])
