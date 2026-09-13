from __future__ import annotations

import pandas as pd
import pytest

from njm135.market.validate import inspect_klines


def _ohlc(times, close) -> pd.DataFrame:
    close = pd.Series(close, index=pd.to_datetime(times, utc=True), dtype=float)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1.0,
        }
    )


def test_inspect_detects_gap() -> None:
    times = ["2024-01-01", "2024-01-02", "2024-01-04"]
    report = inspect_klines(_ohlc(times, [1, 2, 3]), "1d")
    assert not report.ok
    assert len(report.gaps) == 1
    assert report.gaps[0][2] == pytest.approx(2.0)


def test_inspect_continuous_daily() -> None:
    times = pd.date_range("2024-01-01", periods=10, freq="1D", tz="UTC")
    report = inspect_klines(_ohlc(times, range(100, 110)), "1d")
    assert report.ok
    assert report.gaps == []
    assert report.ohlc_errors == 0
