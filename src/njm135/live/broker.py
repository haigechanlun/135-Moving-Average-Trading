from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class Position:
    symbol: str
    side: str  # long / short
    size_contract: int
    size_usdt: float
    entry_price: float
    mark_price: float = 0.0
    unrealized_pnl: float = 0.0


@dataclass
class OrderResult:
    success: bool
    message: str = ""
    fill_price: float = 0.0
    size_usdt: float = 0.0
    contracts: int = 0


class Broker(Protocol):
    def get_balance(self) -> float: ...

    def get_mark_price(self, symbol: str) -> float: ...

    def get_position(self, symbol: str, side: str | None = None) -> Optional[Position]: ...

    def open_long(self, symbol: str, usdt_amount: float) -> OrderResult: ...

    def close_long(self, symbol: str) -> OrderResult: ...
