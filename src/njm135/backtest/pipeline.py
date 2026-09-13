from __future__ import annotations

import pandas as pd

from njm135.backtest.engine import BacktestResult, run_backtest
from njm135.risk import RiskConfig
from njm135.core.strategy import StrategyConfig, annotate


def analyze(
    bars: pd.DataFrame,
    *,
    ma_type: str = "sma",
    config: StrategyConfig | None = None,
    risk: RiskConfig | None = None,
    commission: float = 0.001,
    initial_cash: float = 1.0,
    position_pct: float = 1.0,
) -> tuple[pd.DataFrame, BacktestResult]:
    framed = annotate(bars, ma_type=ma_type, config=config)
    result = run_backtest(
        framed,
        commission=commission,
        initial_cash=initial_cash,
        position_pct=position_pct,
        risk=risk,
    )
    return result.bars, result
