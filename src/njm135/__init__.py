"""宁俊明 135 战法：13 / 34 / 55 均线系统。"""

from njm135.backtest import BacktestResult, analyze, run_backtest
from njm135.core import StrategyConfig, add_ma_system, detect_patterns, generate_signals, sma
from njm135.market import fetch_binance_klines, make_demo_bars
from njm135.risk import RiskConfig, RiskManager

__all__ = [
    "BacktestResult",
    "RiskConfig",
    "RiskManager",
    "StrategyConfig",
    "add_ma_system",
    "analyze",
    "detect_patterns",
    "fetch_binance_klines",
    "generate_signals",
    "make_demo_bars",
    "run_backtest",
    "sma",
]
