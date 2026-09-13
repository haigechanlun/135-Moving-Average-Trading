from __future__ import annotations

from njm135.live.engine import LiveEngine, LiveEngineConfig
from njm135.live.paper import PaperBroker
from njm135.live.symbols import to_binance, to_gate
from njm135.market.synthetic import make_demo_bars
from njm135.risk import RiskConfig


def test_symbol_mapping() -> None:
    assert to_binance("btc_usdt") == "BTCUSDT"
    assert to_gate("BTCUSDT") == "BTC_USDT"
    assert to_gate("ETH/USDT") == "ETH_USDT"


def _bars(*_args, **_kwargs):
    return make_demo_bars(n=120)


def test_live_engine_opens_on_buy(monkeypatch) -> None:
    monkeypatch.setattr("njm135.live.engine.last_intent", lambda _bars: "buy")
    broker = PaperBroker(cash=1000.0)
    engine = LiveEngine(
        broker,
        LiveEngineConfig(symbol="BTCUSDT", dry_run=False, position_pct=0.5),
        fetch_bars=_bars,
    )
    action = engine.run_once()
    assert action.startswith("open:True")
    pos = broker.get_position("BTCUSDT")
    assert pos is not None
    assert pos.size_usdt == 500.0

    again = engine.run_once()
    assert again == "wait_new_bar"


def test_live_engine_closes_on_sell(monkeypatch) -> None:
    monkeypatch.setattr("njm135.live.engine.last_intent", lambda _bars: "sell")
    broker = PaperBroker(cash=1000.0)
    broker.set_price("BTCUSDT", 100.0)
    broker.open_long("BTCUSDT", 400.0)
    engine = LiveEngine(
        broker,
        LiveEngineConfig(symbol="BTCUSDT", dry_run=False),
        fetch_bars=_bars,
    )
    action = engine.run_once()
    assert action.startswith("close:True")
    assert broker.get_position("BTCUSDT") is None


def test_dry_run_uses_paper_broker(monkeypatch) -> None:
    monkeypatch.setattr("njm135.live.engine.last_intent", lambda _bars: "buy")
    broker = PaperBroker(cash=1000.0)
    engine = LiveEngine(
        broker,
        LiveEngineConfig(dry_run=True, position_pct=0.5),
        fetch_bars=_bars,
    )
    action = engine.run_once()
    assert action.startswith("open:True")
    pos = broker.get_position("BTCUSDT", side="long")
    assert pos is not None
    assert pos.size_usdt == 500.0
    assert broker.get_balance() == 500.0


def test_live_stop_loss_closes_even_when_intent_is_hold(monkeypatch) -> None:
    monkeypatch.setattr("njm135.live.engine.last_intent", lambda _bars: "hold")
    broker = PaperBroker(cash=1000.0)
    broker.set_price("BTCUSDT", 100.0)
    broker.open_long("BTCUSDT", 400.0)
    bars = make_demo_bars(n=40)
    bars.iloc[-1, bars.columns.get_loc("close")] = 90.0
    engine = LiveEngine(
        broker,
        LiveEngineConfig(symbol="BTCUSDT", dry_run=False, risk=RiskConfig(stop_loss_pct=0.08)),
        fetch_bars=lambda *_a, **_k: bars,
    )
    action = engine.run_once()
    assert action.startswith("close:True:stop")
    assert broker.get_position("BTCUSDT") is None


def test_live_regime_ma_blocks_buy(monkeypatch) -> None:
    monkeypatch.setattr("njm135.live.engine.last_intent", lambda _bars: "buy")
    broker = PaperBroker(cash=1000.0)
    bars = make_demo_bars(n=40)
    bars["close"] = list(range(40, 0, -1))
    engine = LiveEngine(
        broker,
        LiveEngineConfig(symbol="BTCUSDT", dry_run=False, risk=RiskConfig(regime_ma=5)),
        fetch_bars=lambda *_a, **_k: bars,
    )
    action = engine.run_once()
    assert action == "skip:buy:regime"
    assert broker.get_position("BTCUSDT") is None
