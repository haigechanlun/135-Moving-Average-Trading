from __future__ import annotations

import pandas as pd
import pytest

from njm135.backtest.engine import run_backtest
from njm135.risk import RiskConfig


def _frame(closes: list[float], buy_at: int = 0) -> pd.DataFrame:
    n = len(closes)
    c = pd.Series(closes, dtype=float).to_numpy()
    return pd.DataFrame(
        {
            "open": c,
            "high": c * 1.01,
            "low": c * 0.99,
            "close": c,
            "buy": [i == buy_at for i in range(n)],
            "sell": [False] * n,
        },
        index=pd.date_range("2024-01-01", periods=n, freq="1D", tz="UTC"),
    )


def test_stop_loss_exits_on_next_open() -> None:
    bars = _frame([100, 100, 100, 91, 91, 91])
    res = run_backtest(bars, initial_cash=1000.0, risk=RiskConfig(stop_loss_pct=0.08))
    trade = res.trades.iloc[0]
    assert trade["entry_time"] == bars.index[1]
    # 第 3 根收盘跌破 -8%，下一根开盘才成交
    assert trade["exit_time"] == bars.index[4]
    assert trade["exit_reason"] == "stop"


def test_trailing_stop_uses_peak_close_since_entry() -> None:
    bars = _frame([100, 100, 110, 120, 107, 107])
    res = run_backtest(bars, initial_cash=1000.0, risk=RiskConfig(trailing_pct=0.10))
    trade = res.trades.iloc[0]
    assert trade["exit_time"] == bars.index[5]
    assert trade["exit_reason"] == "trail"
    # 未回撤到 10% 之前不该动
    calm = run_backtest(_frame([100, 100, 110, 120, 115, 115]), initial_cash=1000.0,
                        risk=RiskConfig(trailing_pct=0.10))
    assert calm.trades["exit_reason"].tolist() == [""]


def test_no_risk_config_keeps_signal_only_exits() -> None:
    bars = _frame([100, 100, 80, 80, 80])
    res = run_backtest(bars, initial_cash=1000.0)
    assert res.trades["exit_reason"].tolist() == [""]
    assert res.open_trades == 1


def test_atr_stop_needs_high_low() -> None:
    bars = _frame([100, 100, 90]).drop(columns=["high", "low"])
    with pytest.raises(ValueError, match="ATR"):
        run_backtest(bars, initial_cash=1000.0, risk=RiskConfig(atr_mult=3))


def test_loss_streak_starts_cooldown_and_blocks_entries() -> None:
    bars = _frame([100, 100, 90, 90, 90, 90, 90, 90])
    bars["buy"] = [True, False, True, True, True, True, True, True]
    bars["sell"] = [False, True, False, False, False, False, False, False]
    res = run_backtest(
        bars,
        initial_cash=1000.0,
        risk=RiskConfig(loss_streak=1, cooldown_bars=3),
    )
    assert len(res.trades) == 2
    assert res.trades.iloc[1]["entry_time"] == bars.index[6]
    assert res.bars["risk_blocked"].tolist()[2:5] == ["cooldown"] * 3


def test_regime_ma_blocks_below_and_resumes_above() -> None:
    bars = _frame([100, 100, 80, 80, 120, 120, 120])
    bars["buy"] = [False, False, True, True, True, False, False]
    res = run_backtest(bars, initial_cash=1000.0, risk=RiskConfig(regime_ma=3))
    assert res.bars.loc[bars.index[2], "risk_blocked"] == "regime"
    assert res.trades.iloc[0]["entry_time"] == bars.index[5]


def test_cooldown_arguments_must_be_paired() -> None:
    with pytest.raises(ValueError, match="同时设置"):
        RiskConfig(loss_streak=2)
