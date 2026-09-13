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
