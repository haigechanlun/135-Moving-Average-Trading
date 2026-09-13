from __future__ import annotations

import numpy as np
import pandas as pd

from njm135.market.normalize import normalize_ohlcv


def make_demo_bars(n: int = 220, seed: int = 7) -> pd.DataFrame:
    """先下跌后反转上行的合成行情，便于离线演示。"""
    rng = np.random.default_rng(seed)
    rets = np.concatenate(
        [
            rng.normal(-0.006, 0.012, size=90),
            rng.normal(0.002, 0.008, size=40),
            rng.normal(0.008, 0.010, size=90),
        ]
    )[:n]
    close = 20.0 * np.cumprod(1.0 + rets)
    noise = rng.normal(0.0, 0.004, size=n)
    open_ = np.concatenate([[close[0]], close[:-1]]) * (1.0 + noise)
    high = np.maximum(open_, close) * (1.0 + rng.uniform(0.001, 0.012, size=n))
    low = np.minimum(open_, close) * (1.0 - rng.uniform(0.001, 0.012, size=n))
    volume = rng.integers(1_000_000, 5_000_000, size=n)
    idx = pd.bdate_range("2019-01-02", periods=n, tz="UTC")
    raw = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )
    return normalize_ohlcv(raw)
