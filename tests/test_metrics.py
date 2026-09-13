from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from njm135.backtest.metrics import bars_per_year, compute_performance


def test_bars_per_year_daily() -> None:
    idx = pd.date_range("2020-01-01", periods=10, freq="1D", tz="UTC")
    assert bars_per_year(idx) == pytest.approx(365.25, rel=0.01)


def test_sharpe_positive_uptrend() -> None:
    idx = pd.date_range("2020-01-01", periods=50, freq="1D", tz="UTC")
    vals = np.linspace(100.0, 130.0, 50)
    vals[10] = 128.0
    equity = pd.Series(vals, index=idx)
    trades = pd.DataFrame({"return": [0.02, -0.01, 0.03]})
    perf = compute_performance(equity, trades, initial_cash=100.0, close=equity)
    assert perf.sharpe > 0
    assert perf.max_drawdown < 0
    assert perf.profit_factor > 1
    assert perf.buy_hold_return > 0
