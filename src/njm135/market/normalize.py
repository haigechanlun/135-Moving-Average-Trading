from __future__ import annotations

import pandas as pd

OHLCV_COLS = ("open", "high", "low", "close", "volume")


def normalize_ohlcv(df: pd.DataFrame, *, tz: str | None = None) -> pd.DataFrame:
    """统一为 DatetimeIndex + open/high/low/close/volume。"""
    out = df.copy()
    cols = {str(c).lower(): c for c in out.columns}
    rename = {}
    for name in ("open", "high", "low", "close", "volume", "time", "date", "datetime", "open_time"):
        if name in cols:
            rename[cols[name]] = name
    out = out.rename(columns=rename)

    if not isinstance(out.index, pd.DatetimeIndex):
        for time_col in ("open_time", "time", "date", "datetime"):
            if time_col in out.columns:
                out[time_col] = pd.to_datetime(out[time_col], utc=True, errors="coerce")
                out = out.set_index(time_col)
                break
        else:
            raise ValueError("无法识别时间列，需要 DatetimeIndex 或 time/date/open_time")

    out.index = pd.to_datetime(out.index, utc=True)
    if tz:
        out.index = out.index.tz_convert(tz)

    missing = [c for c in ("open", "high", "low", "close") if c not in out.columns]
    if missing:
        raise ValueError(f"缺少必要列: {missing}")
    if "volume" not in out.columns:
        out["volume"] = 0.0

    for col in OHLCV_COLS:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out = out[list(OHLCV_COLS)].sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out.dropna(subset=["open", "high", "low", "close"])
