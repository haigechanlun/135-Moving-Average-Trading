"""Binance 公开 K 线（拉行情不需要 API Key）。"""

from __future__ import annotations

import time
from typing import Literal

import pandas as pd
import requests

from njm135.market.normalize import normalize_ohlcv

MarketKind = Literal["spot", "futures"]

SPOT_KLINES = "https://api.binance.com/api/v3/klines"
FUTURES_KLINES = "https://fapi.binance.com/fapi/v1/klines"

_KLINE_COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "qav",
    "trades",
    "tbbav",
    "tbqav",
    "ignore",
]


def klines_url(kind: MarketKind) -> str:
    return SPOT_KLINES if kind == "spot" else FUTURES_KLINES


def raw_klines_to_df(rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=_KLINE_COLUMNS)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    return df


def drop_unclosed(df: pd.DataFrame, *, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """丢掉尚未收盘的最后一根（实盘信号只用已完成 K 线）。"""
    if df.empty or "close_time" not in df.columns:
        return df
    ts = now if now is not None else pd.Timestamp.now(tz="UTC")
    closed = df[df["close_time"] <= ts]
    return closed if not closed.empty else df.iloc[:-1]


def fetch_binance_klines(
    symbol: str = "BTCUSDT",
    interval: str = "15m",
    *,
    limit: int = 1500,
    kind: MarketKind = "futures",
    session: requests.Session | None = None,
    sleep_s: float = 0.1,
    drop_last_unclosed: bool = False,
    page_size: int = 1000,
) -> pd.DataFrame:
    """从近到远翻页，拼出最多 ``limit`` 根（单次 API 最多 1000）。"""
    http = session or requests.Session()
    url = klines_url(kind)
    symbol = symbol.upper().replace("/", "").replace("_", "")
    chunks: list[list] = []
    end_time = None
    per_request = min(max(page_size, 1), 1000)
    remaining = limit

    while remaining > 0:
        fetch_limit = min(per_request, remaining)
        params = {"symbol": symbol, "interval": interval, "limit": fetch_limit}
        if end_time is not None:
            params["endTime"] = end_time
        resp = http.get(url, params=params, timeout=20)
        resp.raise_for_status()
        rows = resp.json()
        if not isinstance(rows, list):
            raise RuntimeError(f"Binance 返回异常: {rows}")
        if not rows:
            break
        chunks.append(rows)
        remaining -= len(rows)
        oldest_open = int(rows[0][0])
        end_time = oldest_open - 1
        if len(rows) < fetch_limit:
            break
        if sleep_s:
            time.sleep(sleep_s)

    all_rows: list = []
    for chunk in reversed(chunks):
        all_rows.extend(chunk)
    if not all_rows:
        raise RuntimeError(f"Binance 无 K 线: {symbol} {interval} ({kind})")

    seen = set()
    unique = []
    for row in all_rows:
        key = row[0]
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)

    raw = raw_klines_to_df(unique)
    if drop_last_unclosed:
        raw = drop_unclosed(raw)
    return normalize_ohlcv(raw)
