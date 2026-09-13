"""135 战法核心：均线、形态、买卖信号。不依赖交易所。"""

from njm135.core.catalog import CLASSIC_13, classic_keys
from njm135.core.indicators import add_ma_system, death_cross, ema, golden_cross, sma
from njm135.core.params import PatternParams
from njm135.core.patterns import detect_patterns
from njm135.core.strategy import StrategyConfig, generate_signals, last_intent

__all__ = [
    "CLASSIC_13",
    "PatternParams",
    "StrategyConfig",
    "add_ma_system",
    "classic_keys",
    "death_cross",
    "detect_patterns",
    "ema",
    "generate_signals",
    "golden_cross",
    "last_intent",
    "sma",
]

__all__ = [
    "StrategyConfig",
    "add_ma_system",
    "death_cross",
    "detect_patterns",
    "ema",
    "generate_signals",
    "golden_cross",
    "last_intent",
    "sma",
]
