"""有状态风控：持仓止损、连亏冷却、大均线开仓过滤。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from njm135.risk.config import RiskConfig


def atr_series(bars: pd.DataFrame, window: int) -> pd.Series:
    if not {"high", "low", "close"} <= set(bars.columns):
        raise ValueError("ATR 需要 high / low / close 列")
    prev = bars["close"].shift(1)
    tr = pd.concat(
        [
            bars["high"] - bars["low"],
            (bars["high"] - prev).abs(),
            (bars["low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window, min_periods=window).mean()


def regime_ma_series(bars: pd.DataFrame, window: int) -> pd.Series:
    return bars["close"].rolling(window, min_periods=window).mean()


@dataclass(frozen=True)
class RiskIndicators:
    atr: np.ndarray | None = None
    regime_ma: np.ndarray | None = None


def compute_indicators(bars: pd.DataFrame, config: RiskConfig) -> RiskIndicators:
    atr = None
    regime = None
    if config.atr_mult is not None:
        atr = atr_series(bars, config.atr_window).to_numpy(dtype=float)
    if config.regime_ma is not None:
        regime = regime_ma_series(bars, config.regime_ma).to_numpy(dtype=float)
    return RiskIndicators(atr=atr, regime_ma=regime)


def _finite(value: float) -> bool:
    return value is not None and np.isfinite(value)


class RiskManager:
    """跨 K 线保留连亏/冷却状态；回测循环和实盘轮询共用。"""

    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()
        self.consecutive_losses = 0
        self.cooldown_remaining = 0

    def exit_reason(
        self,
        close: float,
        entry_px: float,
        peak_close: float,
        atr: float = float("nan"),
    ) -> str:
        cfg = self.config
        if (
            cfg.stop_loss_pct is not None
            and entry_px > 0
            and close <= entry_px * (1.0 - cfg.stop_loss_pct)
        ):
            return "stop"
        if (
            cfg.trailing_pct is not None
            and peak_close > 0
            and close <= peak_close * (1.0 - cfg.trailing_pct)
        ):
            return "trail"
        if cfg.atr_mult is not None and _finite(atr) and peak_close > 0:
            if close <= peak_close - cfg.atr_mult * atr:
                return "atr"
        return ""

    def record_trade(self, trade_return: float) -> None:
        """平仓后更新连亏；第 N 笔亏损的平仓 K 线算冷却第 1 根。"""
        cfg = self.config
        if cfg.loss_streak is None:
            return
        self.consecutive_losses = self.consecutive_losses + 1 if trade_return < 0 else 0
        if self.consecutive_losses >= cfg.loss_streak:
            self.cooldown_remaining = cfg.cooldown_bars or 0
            self.consecutive_losses = 0

    def entry_block_reason(self, close: float, regime_ma: float = float("nan")) -> str:
        if self.cooldown_remaining > 0:
            return "cooldown"
        if self.config.regime_ma is not None:
            if not _finite(regime_ma) or close < regime_ma:
                return "regime"
        return ""

    def finish_bar(self) -> None:
        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1
