from __future__ import annotations

from pathlib import Path

import pandas as pd

from njm135.market.normalize import normalize_ohlcv

DEFAULT_DATA_DIR = Path("data")


def kline_filename(symbol: str, interval: str, kind: str) -> str:
    symbol = symbol.upper().replace("/", "").replace("_", "")
    return f"{symbol}_{kind}_{interval}.csv"


def kline_path(symbol: str, interval: str, kind: str, data_dir: str | Path | None = None) -> Path:
    root = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    return root / kline_filename(symbol, interval, kind)


def save_klines(bars: pd.DataFrame, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df = bars.copy()
    df.index.name = "date"
    df.to_csv(out)
    return out


def load_klines(path: str | Path) -> pd.DataFrame:
    return normalize_ohlcv(pd.read_csv(path))
