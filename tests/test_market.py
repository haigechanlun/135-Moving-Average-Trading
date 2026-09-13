from __future__ import annotations

import pandas as pd

from njm135.market.binance import drop_unclosed, fetch_binance_klines, raw_klines_to_df
from njm135.market.normalize import normalize_ohlcv


def test_normalize_from_time_column() -> None:
    df = pd.DataFrame(
        {
            "time": ["2024-01-01", "2024-01-02"],
            "Open": [1.0, 2.0],
            "High": [1.2, 2.2],
            "Low": [0.9, 1.8],
            "Close": [1.1, 2.1],
            "Volume": [10, 20],
        }
    )
    out = normalize_ohlcv(df)
    assert list(out.columns) == ["open", "high", "low", "close", "volume"]
    assert len(out) == 2


def test_raw_klines_and_drop_unclosed() -> None:
    rows = [
        [0, "1", "2", "0.5", "1.5", "10", 60_000, "0", "1", "0", "0", "0"],
        [120_000, "1.5", "2.5", "1.4", "2.0", "11", 180_000, "0", "1", "0", "0", "0"],
    ]
    raw = raw_klines_to_df(rows)
    now = pd.Timestamp(90_000, unit="ms", tz="UTC")
    closed = drop_unclosed(raw, now=now)
    assert len(closed) == 1
    now2 = pd.Timestamp(200_000, unit="ms", tz="UTC")
    assert len(drop_unclosed(raw, now=now2)) == 2


class _FakeResp:
    def __init__(self, rows):
        self._rows = rows

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._rows


class _FakeSession:
    def __init__(self):
        self.params = []

    def get(self, url, params=None, timeout=None):
        self.params.append(dict(params))
        if "endTime" not in params:
            rows = [
                [200, "1", "2", "0.5", "1.5", "10", 250, "0", "1", "0", "0", "0"],
                [300, "1", "2", "0.5", "1.5", "10", 350, "0", "1", "0", "0", "0"],
            ]
        else:
            assert params["endTime"] == 199
            rows = [
                [0, "1", "2", "0.5", "1.5", "10", 50, "0", "1", "0", "0", "0"],
                [100, "1", "2", "0.5", "1.5", "10", 150, "0", "1", "0", "0", "0"],
            ]
        return _FakeResp(rows)


def test_fetch_paginates_older_pages() -> None:
    session = _FakeSession()
    df = fetch_binance_klines("BTCUSDT", "1m", limit=4, session=session, sleep_s=0, page_size=2)
    assert len(df) == 4
    assert df.index[0] == pd.Timestamp(0, unit="ms", tz="UTC")
    assert df.index[-1] == pd.Timestamp(300, unit="ms", tz="UTC")
    assert "endTime" in session.params[1]
