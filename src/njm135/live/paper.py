from __future__ import annotations

from typing import Dict, Optional

from njm135.live.broker import OrderResult, Position
from njm135.live.symbols import to_binance


class PaperBroker:
    """内存模拟仓，用于 dry-run 与单测。"""

    def __init__(self, cash: float = 10_000.0, prices: Dict[str, float] | None = None):
        self.cash = float(cash)
        self.prices = prices or {}
        self.positions: Dict[str, Position] = {}

    def set_price(self, symbol: str, price: float) -> None:
        self.prices[to_binance(symbol)] = float(price)

    def get_balance(self) -> float:
        return self.cash

    def get_mark_price(self, symbol: str) -> float:
        return float(self.prices.get(to_binance(symbol), 0.0))

    def get_position(self, symbol: str, side: str | None = None) -> Optional[Position]:
        pos = self.positions.get(to_binance(symbol))
        if pos is None:
            return None
        if side and pos.side != side:
            return None
        return pos

    def open_long(self, symbol: str, usdt_amount: float) -> OrderResult:
        key = to_binance(symbol)
        if key in self.positions:
            return OrderResult(False, "已有多仓")
        px = self.get_mark_price(symbol)
        if px <= 0 or usdt_amount <= 0 or usdt_amount > self.cash:
            return OrderResult(False, "资金或价格无效")
        self.cash -= usdt_amount
        self.positions[key] = Position(
            symbol=key,
            side="long",
            size_contract=1,
            size_usdt=usdt_amount,
            entry_price=px,
            mark_price=px,
        )
        return OrderResult(True, "paper open long", fill_price=px, size_usdt=usdt_amount, contracts=1)

    def close_long(self, symbol: str) -> OrderResult:
        key = to_binance(symbol)
        pos = self.positions.pop(key, None)
        if pos is None or pos.side != "long":
            return OrderResult(False, "无多仓")
        px = self.get_mark_price(symbol) or pos.entry_price
        pnl = pos.size_usdt * (px / pos.entry_price - 1.0)
        self.cash += pos.size_usdt + pnl
        return OrderResult(True, "paper close long", fill_price=px, size_usdt=pos.size_usdt)
