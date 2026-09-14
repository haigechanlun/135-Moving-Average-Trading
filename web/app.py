"""FastAPI 后端：Binance K 线、USDT 永续列表与 135 信号。"""

from __future__ import annotations

import math
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from njm135.core.catalog import CLASSIC_13, EXTRA_PATTERNS
from njm135.core.strategy import StrategyConfig, annotate
from njm135.core.indicators import add_bollinger, add_macd, add_volatility
from njm135.market.binance import fetch_binance_klines

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
ALLOWED_INTERVALS = {"1h", "4h", "1d", "1w"}
INTERVAL_SECONDS = {"1h": 3600, "4h": 4 * 3600, "1d": 24 * 3600, "1w": 7 * 24 * 3600}
SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,20}USDT$")
EXCLUDED_BASES = {
    "USDT", "USDC", "FDUSD", "BUSD", "TUSD", "DAI", "USDE", "USDS", "PYUSD",
}
BINANCE_EXCHANGE_INFO = "https://fapi.binance.com/fapi/v1/exchangeInfo"
BINANCE_TICKER_24H = "https://fapi.binance.com/fapi/v1/ticker/24hr"

FALLBACK_COINS = (
    ("BTC", "Bitcoin"), ("ETH", "Ethereum"), ("BNB", "BNB"), ("SOL", "Solana"),
    ("XRP", "XRP"), ("DOGE", "Dogecoin"), ("ADA", "Cardano"), ("AVAX", "Avalanche"),
    ("TRX", "TRON"), ("DOT", "Polkadot"), ("LINK", "Chainlink"), ("MATIC", "Polygon"),
    ("LTC", "Litecoin"), ("BCH", "Bitcoin Cash"), ("NEAR", "NEAR Protocol"),
    ("UNI", "Uniswap"), ("APT", "Aptos"), ("ICP", "Internet Computer"),
    ("ETC", "Ethereum Classic"), ("FIL", "Filecoin"), ("ATOM", "Cosmos"),
    ("XLM", "Stellar"), ("HBAR", "Hedera"), ("SUI", "Sui"), ("AAVE", "Aave"),
    ("INJ", "Injective"), ("OP", "Optimism"), ("ARB", "Arbitrum"), ("TIA", "Celestia"),
    ("IMX", "Immutable"), ("SEI", "Sei"), ("RUNE", "THORChain"), ("MKR", "Maker"),
    ("GRT", "The Graph"), ("ALGO", "Algorand"), ("FTM", "Fantom"), ("VET", "VeChain"),
    ("THETA", "Theta"), ("EGLD", "MultiversX"), ("FLOW", "Flow"), ("SAND", "The Sandbox"),
    ("MANA", "Decentraland"), ("AXS", "Axie Infinity"), ("CHZ", "Chiliz"),
    ("KAS", "Kaspa"), ("PEPE", "Pepe"), ("WIF", "dogwifhat"), ("BONK", "Bonk"),
    ("SHIB", "Shiba Inu"), ("FLOKI", "FLOKI"),
)

_contracts_cache: tuple[float, list[dict[str, Any]]] = (0.0, [])
_tickers_cache: tuple[float, dict[str, dict[str, Any]]] = (0.0, {})
_symbols_cache: tuple[float, list[dict[str, Any]]] = (0.0, [])

app = FastAPI(title="135 Signal Desk", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def _json_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _usdt_perpetuals() -> list[dict[str, Any]]:
    global _contracts_cache
    cached_at, cached = _contracts_cache
    if cached and time.time() - cached_at < 3600:
        return cached

    response = requests.get(BINANCE_EXCHANGE_INFO, timeout=12)
    response.raise_for_status()
    result = []
    for item in response.json().get("symbols", []):
        base = str(item.get("baseAsset", "")).upper()
        symbol = str(item.get("symbol", "")).upper()
        if (
            item.get("quoteAsset") != "USDT"
            or item.get("contractType") != "PERPETUAL"
            or item.get("status") != "TRADING"
            or base in EXCLUDED_BASES
            or not SYMBOL_RE.fullmatch(symbol)
        ):
            continue
        result.append({"symbol": symbol, "base": base, "name": base})
    _contracts_cache = (time.time(), result)
    return result


def _ticker_map() -> dict[str, dict[str, Any]]:
    global _tickers_cache
    cached_at, cached = _tickers_cache
    if cached and time.time() - cached_at < 30:
        return cached

    response = requests.get(BINANCE_TICKER_24H, timeout=12)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("unexpected ticker payload")
    tickers: dict[str, dict[str, Any]] = {}
    for item in payload:
        symbol = str(item.get("symbol", "")).upper()
        tickers[symbol] = {
            "change24h": _json_number(item.get("priceChangePercent")),
            "lastPrice": _json_number(item.get("lastPrice")),
            "quoteVolume": _json_number(item.get("quoteVolume")),
        }
    _tickers_cache = (time.time(), tickers)
    return tickers


def _fallback_symbols() -> list[dict[str, Any]]:
    return [
        {
            "symbol": f"{base}USDT",
            "base": base,
            "name": name,
            "rank": rank,
            "change24h": None,
            "lastPrice": None,
            "quoteVolume": None,
        }
        for rank, (base, name) in enumerate(FALLBACK_COINS, 1)
    ]


def get_symbols() -> list[dict[str, Any]]:
    global _symbols_cache
    cached_at, cached = _symbols_cache
    if cached and time.time() - cached_at < 30:
        return cached

    try:
        contracts = _usdt_perpetuals()
        tickers = {}
        try:
            tickers = _ticker_map()
        except (requests.RequestException, ValueError, TypeError):
            tickers = {}
        result = []
        for contract in contracts:
            ticker = tickers.get(contract["symbol"], {})
            result.append(
                {
                    "symbol": contract["symbol"],
                    "base": contract["base"],
                    "name": contract["name"],
                    "rank": None,
                    "change24h": ticker.get("change24h"),
                    "lastPrice": ticker.get("lastPrice"),
                    "quoteVolume": ticker.get("quoteVolume"),
                }
            )
        result.sort(key=lambda item: item.get("quoteVolume") or 0.0, reverse=True)
        for index, item in enumerate(result, 1):
            item["rank"] = index
        if not result:
            result = _fallback_symbols()
    except (requests.RequestException, ValueError, TypeError, KeyError):
        result = _fallback_symbols()

    _symbols_cache = (time.time(), result)
    return result


PATTERNS = CLASSIC_13 + EXTRA_PATTERNS
PATTERN_BY_KEY = {pattern.key: pattern for pattern in PATTERNS}


def _is_forming(open_time: Any, interval: str) -> bool:
    seconds = INTERVAL_SECONDS[interval]
    start = pd.Timestamp(open_time)
    if start.tzinfo is None:
        start = start.tz_localize("UTC")
    return pd.Timestamp.now(tz="UTC") < start + pd.Timedelta(seconds=seconds)


def _volume_point(ts: int, open_price: float, close: float, volume: float) -> dict[str, Any]:
    return {
        "time": ts,
        "value": volume,
        "color": "#22c55e66" if close >= open_price else "#ef444466",
    }


def _parse_symbol(symbol: str) -> str:
    symbol = symbol.upper().replace("/", "").replace("_", "")
    if not SYMBOL_RE.fullmatch(symbol):
        raise HTTPException(status_code=400, detail="仅支持 Binance USDT 交易对")
    return symbol


def _require_interval(interval: str) -> str:
    if interval not in ALLOWED_INTERVALS:
        raise HTTPException(status_code=400, detail="周期仅支持 1h / 4h / 1d / 1w")
    return interval


def _pattern_text(row: Any, keys: list[str]) -> str:
    return " · ".join(PATTERN_BY_KEY[key].name for key in keys if bool(row.get(key, False)))


def _serialize_chart(symbol: str, interval: str, limit: int, exit_ma: int) -> dict[str, Any]:
    bars = fetch_binance_klines(
        symbol,
        interval,
        limit=limit,
        kind="futures",
        drop_last_unclosed=False,
    )
    framed = annotate(bars, config=StrategyConfig(exit_ma=exit_ma))
    framed = add_volatility(add_bollinger(add_macd(framed)))

    candles: list[dict[str, Any]] = []
    volumes: list[dict[str, Any]] = []
    ma13: list[dict[str, Any]] = []
    ma34: list[dict[str, Any]] = []
    ma55: list[dict[str, Any]] = []
    boll_mid: list[dict[str, Any]] = []
    boll_upper: list[dict[str, Any]] = []
    boll_lower: list[dict[str, Any]] = []
    macd_dif: list[dict[str, Any]] = []
    macd_dea: list[dict[str, Any]] = []
    macd_hist: list[dict[str, Any]] = []
    atr_pct: list[dict[str, Any]] = []
    atr_pct_ma: list[dict[str, Any]] = []
    strategy_markers: list[dict[str, Any]] = []
    pattern_markers: list[dict[str, Any]] = []

    buy_keys = [p.key for p in PATTERNS if p.role in {"buy", "add"}]
    sell_keys = [p.key for p in PATTERNS if p.role == "sell"]
    in_position = False
    latest_action = "hold"

    for timestamp, row in framed.iterrows():
        ts = int(timestamp.timestamp())
        close = float(row["close"])
        candle = {
            "time": ts,
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": close,
        }
        candles.append(candle)
        volumes.append(_volume_point(ts, float(row["open"]), close, float(row.get("volume", 0.0))))
        for output, key in (
            (ma13, "ma13"),
            (ma34, "ma34"),
            (ma55, "ma55"),
            (boll_mid, "boll_mid"),
            (boll_upper, "boll_upper"),
            (boll_lower, "boll_lower"),
        ):
            value = _json_number(row[key])
            if value is not None:
                output.append({"time": ts, "value": value})

        # 副图与主图靠逻辑序号同步，缺值要补占位点，否则两图会整体错开。
        for output, key in ((macd_dif, "macd_dif"), (macd_dea, "macd_dea"), (atr_pct_ma, "atr_pct_ma")):
            value = _json_number(row[key])
            output.append({"time": ts} if value is None else {"time": ts, "value": value})
        hist = _json_number(row["macd_hist"])
        if hist is None:
            macd_hist.append({"time": ts})
        else:
            macd_hist.append(
                {
                    "time": ts,
                    "value": hist,
                    "color": "#2dd4a7aa" if hist >= 0 else "#ff6678aa",
                }
            )
        vol = _json_number(row["atr_pct"])
        baseline = _json_number(row["atr_pct_ma"])
        if vol is None:
            atr_pct.append({"time": ts})
        else:
            hot = baseline is not None and vol >= baseline
            atr_pct.append(
                {
                    "time": ts,
                    "value": vol,
                    "color": "#f6a94aaa" if hot else "#5eead466",
                }
            )

        active = [p.key for p in PATTERNS if bool(row.get(p.key, False))]
        if active:
            buys = [key for key in active if key in buy_keys]
            sells = [key for key in active if key in sell_keys]
            if buys:
                pattern_markers.append(
                    {
                        "time": ts,
                        "position": "belowBar",
                        "color": "#38bdf8",
                        "shape": "circle",
                        "text": _pattern_text(row, buys),
                    }
                )
            if sells:
                pattern_markers.append(
                    {
                        "time": ts,
                        "position": "aboveBar",
                        "color": "#f59e0b",
                        "shape": "circle",
                        "text": _pattern_text(row, sells),
                    }
                )

        action = "hold"
        if bool(row["buy"]) and not in_position:
            action = "buy"
            in_position = True
            keys = [key for key in buy_keys if bool(row.get(key, False))]
            strategy_markers.append(
                {
                    "time": ts,
                    "position": "belowBar",
                    "color": "#22c55e",
                    "shape": "arrowUp",
                    "text": _pattern_text(row, keys) or "买入",
                }
            )
        elif bool(row["sell"]) and in_position:
            action = "sell"
            in_position = False
            keys = [key for key in sell_keys if bool(row.get(key, False))]
            text = _pattern_text(row, keys)
            if bool(row.get(f"break_ma{exit_ma}", False)):
                text = f"{text} · 跌破MA{exit_ma}".strip(" ·")
            strategy_markers.append(
                {
                    "time": ts,
                    "position": "aboveBar",
                    "color": "#ef4444",
                    "shape": "arrowDown",
                    "text": text or "卖出",
                }
            )
        latest_action = action

    last = framed.iloc[-1]
    previous = framed.iloc[-2] if len(framed) > 1 else last
    last_close = float(last["close"])
    change = last_close / float(previous["close"]) - 1.0
    latest_patterns = [p.name for p in PATTERNS if bool(last.get(p.key, False))]
    return {
        "symbol": symbol,
        "interval": interval,
        "candles": candles,
        "volume": volumes,
        "ma": {"13": ma13, "34": ma34, "55": ma55},
        "boll": {"mid": boll_mid, "upper": boll_upper, "lower": boll_lower},
        "macd": {"dif": macd_dif, "dea": macd_dea, "hist": macd_hist},
        "vol": {"atrPct": atr_pct, "baseline": atr_pct_ma},
        "strategyMarkers": strategy_markers,
        "patternMarkers": pattern_markers,
        "meta": {
            "lastClose": last_close,
            "change": change,
            "lastTime": int(framed.index[-1].timestamp()),
            "forming": _is_forming(framed.index[-1], interval),
            "signal": latest_action,
            "position": "long" if in_position else "flat",
            "patterns": latest_patterns,
            "bars": len(framed),
        },
    }


def _binance_http(exc: requests.HTTPError, symbol: str) -> HTTPException:
    status = exc.response.status_code if exc.response is not None else 502
    if status == 400:
        return HTTPException(status_code=404, detail=f"Binance 不支持 {symbol}")
    return HTTPException(status_code=502, detail="Binance 行情暂时不可用")


def _serialize_live_bar(symbol: str, interval: str) -> dict[str, Any]:
    bars = fetch_binance_klines(
        symbol,
        interval,
        limit=2,
        kind="futures",
        drop_last_unclosed=False,
        sleep_s=0,
    )
    last = bars.iloc[-1]
    previous = bars.iloc[-2] if len(bars) > 1 else last
    ts = int(bars.index[-1].timestamp())
    open_price = float(last["open"])
    close = float(last["close"])
    return {
        "symbol": symbol,
        "interval": interval,
        "candle": {
            "time": ts,
            "open": open_price,
            "high": float(last["high"]),
            "low": float(last["low"]),
            "close": close,
        },
        "volume": _volume_point(ts, open_price, close, float(last.get("volume", 0.0))),
        "lastClose": close,
        "change": close / float(previous["close"]) - 1.0,
        "forming": _is_forming(bars.index[-1], interval),
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/symbols")
def symbols() -> dict[str, Any]:
    return {"items": get_symbols(), "updatedAt": int(time.time())}


@app.get("/api/chart")
def chart(
    symbol: str = Query("BTCUSDT"),
    interval: str = Query("1d"),
    limit: int = Query(600, ge=100, le=1000),
    exit_ma: int = Query(55, alias="exitMa"),
) -> dict[str, Any]:
    symbol = _parse_symbol(symbol)
    interval = _require_interval(interval)
    if exit_ma not in {13, 34, 55}:
        raise HTTPException(status_code=400, detail="离场线仅支持 MA13 / MA34 / MA55")
    try:
        return _serialize_chart(symbol, interval, limit, exit_ma)
    except requests.HTTPError as exc:
        raise _binance_http(exc, symbol) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Binance 行情请求失败") from exc


@app.get("/api/bar")
def latest_bar(
    symbol: str = Query("BTCUSDT"),
    interval: str = Query("1d"),
) -> dict[str, Any]:
    symbol = _parse_symbol(symbol)
    interval = _require_interval(interval)
    try:
        return _serialize_live_bar(symbol, interval)
    except requests.HTTPError as exc:
        raise _binance_http(exc, symbol) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Binance 行情请求失败") from exc
