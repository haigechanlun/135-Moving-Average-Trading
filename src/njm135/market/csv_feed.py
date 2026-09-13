from __future__ import annotations

from pathlib import Path

import pandas as pd

from njm135.market.normalize import normalize_ohlcv


def load_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    return normalize_ohlcv(df)
