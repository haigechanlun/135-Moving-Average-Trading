from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from njm135.market.synthetic import make_demo_bars
from web import app as web_app


def test_chart_payload_reuses_core_signals(monkeypatch) -> None:
    bars = make_demo_bars(n=140)
    monkeypatch.setattr(web_app, "fetch_binance_klines", lambda *_args, **_kwargs: bars)

    payload = web_app._serialize_chart("BTCUSDT", "1d", 140, 55)

    assert payload["symbol"] == "BTCUSDT"
    assert len(payload["candles"]) == 140
    assert payload["ma"]["55"]
    assert payload["boll"]["mid"]
    bars_count = len(payload["candles"])
    for key in ("dif", "dea", "hist"):
        series = payload["macd"][key]
        assert len(series) == bars_count
        assert series[0]["time"] == payload["candles"][0]["time"]
        assert any("value" in point for point in series)
    assert len(payload["vol"]["atrPct"]) == bars_count
    assert payload["vol"]["atrPct"][0]["time"] == payload["candles"][0]["time"]
    assert payload["meta"]["bars"] == 140
    assert payload["meta"]["signal"] in {"buy", "sell", "hold"}
    assert "forming" in payload["meta"]


def test_latest_bar_endpoint(monkeypatch) -> None:
    bars = make_demo_bars(n=12)
    monkeypatch.setattr(web_app, "fetch_binance_klines", lambda *_args, **_kwargs: bars)
    client = TestClient(web_app.app)
    payload = client.get("/api/bar?symbol=BTCUSDT&interval=1h").json()
    last = bars.iloc[-1]
    assert payload["candle"]["close"] == float(last["close"])
    assert payload["volume"]["time"] == payload["candle"]["time"]
    assert payload["forming"] is False
    assert client.get("/api/bar?symbol=BTCUSDT&interval=15m").status_code == 400
    assert client.get("/api/bar?symbol=BTCUSDT&interval=30m").status_code == 200


def test_web_routes_validate_chart_query() -> None:
    client = TestClient(web_app.app)

    assert client.get("/api/health").json() == {"status": "ok"}
    home = client.get("/")
    assert home.status_code == 200
    assert 'id="languageSwitch"' in home.text
    assert "Powered by haigechanlun" in home.text
    assert "https://x.com/haigechanlun666" in home.text
    response = client.get("/api/chart?symbol=NOT_A_PAIR&interval=1d")
    assert response.status_code == 400
    response = client.get("/api/chart?symbol=BTCUSDT&interval=15m")
    assert response.status_code == 400
    assert "30m" in web_app.ALLOWED_INTERVALS
    assert "1h" in web_app.ALLOWED_INTERVALS


def test_symbols_include_all_usdt_perpetuals(monkeypatch) -> None:
    web_app._contracts_cache = (0.0, [])
    web_app._tickers_cache = (0.0, {})
    web_app._symbols_cache = (0.0, [])

    class _Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return self._payload

    def fake_get(url, *args, **kwargs):
        if "exchangeInfo" in url:
            return _Response(
                {
                    "symbols": [
                        {
                            "symbol": "BTCUSDT",
                            "baseAsset": "BTC",
                            "quoteAsset": "USDT",
                            "contractType": "PERPETUAL",
                            "status": "TRADING",
                        },
                        {
                            "symbol": "ETHUSDT",
                            "baseAsset": "ETH",
                            "quoteAsset": "USDT",
                            "contractType": "PERPETUAL",
                            "status": "TRADING",
                        },
                        {
                            "symbol": "BTCUSDC",
                            "baseAsset": "BTC",
                            "quoteAsset": "USDC",
                            "contractType": "PERPETUAL",
                            "status": "TRADING",
                        },
                        {
                            "symbol": "SOLUSDT",
                            "baseAsset": "SOL",
                            "quoteAsset": "USDT",
                            "contractType": "CURRENT_QUARTER",
                            "status": "TRADING",
                        },
                        {
                            "symbol": "USDCUSDT",
                            "baseAsset": "USDC",
                            "quoteAsset": "USDT",
                            "contractType": "PERPETUAL",
                            "status": "TRADING",
                        },
                    ]
                }
            )
        if "ticker/24hr" in url:
            return _Response(
                [
                    {"symbol": "ETHUSDT", "priceChangePercent": "8.2", "lastPrice": "3500", "quoteVolume": "20"},
                    {"symbol": "BTCUSDT", "priceChangePercent": "-1.5", "lastPrice": "60000", "quoteVolume": "100"},
                ]
            )
        raise AssertionError(url)

    monkeypatch.setattr(web_app.requests, "get", fake_get)

    items = web_app.get_symbols()
    assert [item["symbol"] for item in items] == ["BTCUSDT", "ETHUSDT"]
    assert items[0]["quoteVolume"] == 100.0
    assert items[1]["change24h"] == 8.2

    client = TestClient(web_app.app)
    payload = client.get("/api/symbols").json()
    assert len(payload["items"]) == 2
