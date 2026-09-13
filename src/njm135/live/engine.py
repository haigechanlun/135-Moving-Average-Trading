"""实盘循环：Binance 已收盘 K 线 → 135 信号 → 共用风控 → Gate 下单。"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

from njm135.core.strategy import StrategyConfig, annotate, last_intent
from njm135.live.broker import Broker, OrderResult
from njm135.live.symbols import to_binance
from njm135.market.binance import MarketKind, fetch_binance_klines
from njm135.risk import RiskConfig, RiskManager, compute_indicators

logger = logging.getLogger(__name__)


@dataclass
class LiveEngineConfig:
    symbol: str = "BTCUSDT"
    interval: str = "15m"
    kind: MarketKind = "futures"
    kline_limit: int = 800
    ma_type: str = "sma"
    strategy: StrategyConfig | None = None
    risk: RiskConfig | None = None
    position_pct: float = 0.3
    poll_seconds: float = 15.0
    dry_run: bool = True


class LiveEngine:
    def __init__(
        self,
        broker: Broker,
        config: LiveEngineConfig | None = None,
        *,
        fetch_bars: Optional[Callable[..., pd.DataFrame]] = None,
    ):
        self.broker = broker
        self.config = config or LiveEngineConfig()
        self.fetch_bars = fetch_bars or fetch_binance_klines
        self.risk = RiskManager(self.config.risk)
        self._last_bar_time: Optional[pd.Timestamp] = None
        self._entry_px = 0.0
        self._peak_close = 0.0
        self.symbol = to_binance(self.config.symbol)

    def load_closed_bars(self) -> pd.DataFrame:
        return self.fetch_bars(
            self.symbol,
            self.config.interval,
            limit=self.config.kline_limit,
            kind=self.config.kind,
            drop_last_unclosed=True,
        )

    def run_once(self) -> str:
        bars = self.load_closed_bars()
        if bars.empty:
            return "no_data"
        bar_time = bars.index[-1]
        framed = annotate(bars, ma_type=self.config.ma_type, config=self.config.strategy)
        intent = last_intent(framed)
        last_close = float(framed["close"].iloc[-1])
        logger.info("%s %s close=%.4f intent=%s", self.symbol, bar_time, last_close, intent)

        if self._last_bar_time is not None and bar_time <= self._last_bar_time:
            return "wait_new_bar"

        if hasattr(self.broker, "set_price"):
            self.broker.set_price(self.symbol, last_close)

        pos = self.broker.get_position(self.symbol, side="long")
        in_long = pos is not None and pos.size_usdt > 0
        ind = compute_indicators(framed, self.risk.config)
        atr = float(ind.atr[-1]) if ind.atr is not None and len(ind.atr) else float("nan")
        regime = (
            float(ind.regime_ma[-1])
            if ind.regime_ma is not None and len(ind.regime_ma)
            else float("nan")
        )

        action = "hold"
        if in_long:
            if self._entry_px <= 0 and pos is not None:
                self._entry_px = float(pos.entry_price)
                self._peak_close = max(self._entry_px, last_close)
            self._peak_close = max(self._peak_close, last_close)
            reason = "signal" if intent == "sell" else ""
            if not reason:
                reason = self.risk.exit_reason(last_close, self._entry_px, self._peak_close, atr)
            if reason:
                result = self._close(reason)
                action = f"close:{result.success}:{reason}:{result.message}"
            else:
                action = "hold"
        elif intent == "buy":
            blocked = self.risk.entry_block_reason(last_close, regime)
            if blocked:
                action = f"skip:buy:{blocked}"
            else:
                result = self._open(last_close)
                action = f"open:{result.success}:{result.message}"
        else:
            action = "hold"

        self.risk.finish_bar()
        self._last_bar_time = bar_time
        return action

    def _open(self, last_close: float) -> OrderResult:
        balance = self.broker.get_balance()
        usdt = max(balance * self.config.position_pct, 0.0)
        logger.info(
            "开多 %s %.2f USDT (dry_run=%s, close=%.4f)",
            self.symbol,
            usdt,
            self.config.dry_run,
            last_close,
        )
        result = self.broker.open_long(self.symbol, usdt)
        if result.success:
            self._entry_px = result.fill_price or last_close
            self._peak_close = last_close
        return result

    def _close(self, reason: str = "signal") -> OrderResult:
        logger.info("平多 %s reason=%s (dry_run=%s)", self.symbol, reason, self.config.dry_run)
        result = self.broker.close_long(self.symbol)
        if result.success:
            fill = result.fill_price or self._entry_px
            ret = fill / self._entry_px - 1.0 if self._entry_px else 0.0
            self.risk.record_trade(ret)
            self._entry_px = 0.0
            self._peak_close = 0.0
        return result

    def run_loop(self) -> None:
        logger.info(
            "启动实盘 %s %s dry_run=%s",
            self.symbol,
            self.config.interval,
            self.config.dry_run,
        )
        while True:
            try:
                action = self.run_once()
                logger.info("本轮: %s", action)
            except Exception:
                logger.exception("本轮失败")
            time.sleep(self.config.poll_seconds)
