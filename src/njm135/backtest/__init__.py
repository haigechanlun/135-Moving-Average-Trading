"""回测模块：下一根开盘成交。"""

from njm135.backtest.engine import BacktestResult, run_backtest
from njm135.backtest.pipeline import analyze
from njm135.backtest.plotting import plot_analysis

__all__ = ["BacktestResult", "analyze", "plot_analysis", "run_backtest"]
