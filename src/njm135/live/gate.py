"""Gate.io USDT 永续。接口形状对齐 haigechanlun/trade/gate/gate_trade.py。"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from njm135.live.broker import OrderResult, Position
from njm135.live.symbols import to_gate

logger = logging.getLogger(__name__)

HOST = "https://api.gateio.ws/api/v4"
SETTLE = "usdt"
GATE_API_REQUEST_TIMEOUT = (3.0, 15.0)


def contracts_from_usdt(
    usdt_amount: float,
    price: float,
    multiplier: float,
    min_size: float,
    max_size: float | None = None,
) -> int:
    """资金不够最小张时返回 0，绝不抬到 min_size。"""
    if price <= 0 or usdt_amount <= 0 or multiplier <= 0:
        return 0
    contracts = int(usdt_amount / (price * multiplier))
    min_n = int(min_size)
    if contracts < min_n:
        return 0
    if max_size is not None:
        contracts = min(contracts, int(max_size))
    return contracts

HOST = "https://api.gateio.ws/api/v4"
SETTLE = "usdt"
GATE_API_REQUEST_TIMEOUT = (3.0, 15.0)


class _TimeoutFuturesApi:
    def __init__(self, api, timeout=GATE_API_REQUEST_TIMEOUT):
        object.__setattr__(self, "_api", api)
        object.__setattr__(self, "_timeout", timeout)

    def __getattr__(self, name: str):
        attr = getattr(self._api, name)
        if not callable(attr):
            return attr
        timeout = self._timeout

        def wrapper(*args, **kwargs):
            kwargs.setdefault("_request_timeout", timeout)
            return attr(*args, **kwargs)

        return wrapper


class GateBroker:
    def __init__(self, api_key: str | None = None, api_secret: str | None = None):
        self.api_key = api_key or os.environ.get("GATE_API_KEY", "")
        self.api_secret = api_secret or os.environ.get("GATE_API_SECRET", "")
        if not self.api_key or not self.api_secret:
            raise ValueError("缺少 GATE_API_KEY / GATE_API_SECRET")
        self._client = None
        self._contract_cache: Dict[str, Dict[str, Any]] = {}

    def _get_client(self):
        if self._client is None:
            from gate_api import ApiClient, Configuration, FuturesApi

            config = Configuration(key=self.api_key, secret=self.api_secret, host=HOST)
            api_client = ApiClient(config)
            self._client = type(
                "Client",
                (),
                {"futures_api": _TimeoutFuturesApi(FuturesApi(api_client))},
            )()
        return self._client

    def get_contract_info(self, symbol: str) -> Dict[str, Any]:
        formatted = to_gate(symbol)
        if formatted in self._contract_cache:
            return self._contract_cache[formatted]
        try:
            contract = self._get_client().futures_api.get_futures_contract(SETTLE, formatted)
            info = {
                "quanto_multiplier": float(contract.quanto_multiplier),
                "min_size": float(contract.order_size_min),
                "max_size": float(contract.order_size_max),
            }
            self._contract_cache[formatted] = info
            return info
        except Exception as exc:
            logger.error("获取合约信息失败 %s: %s", symbol, exc)
            raise RuntimeError(f"无法获取合约信息 {formatted}") from exc

    def get_mark_price(self, symbol: str) -> float:
        formatted = to_gate(symbol)
        tickers = self._get_client().futures_api.list_futures_tickers(SETTLE, contract=formatted)
        if not tickers:
            return 0.0
        ticker = tickers[0]
        if ticker.mark_price:
            return float(ticker.mark_price)
        if ticker.last:
            return float(ticker.last)
        return 0.0

    def get_balance(self) -> float:
        account = self._get_client().futures_api.list_futures_accounts(SETTLE)
        return float(account.available) if account else 0.0

    def get_position(self, symbol: str, side: str | None = None) -> Optional[Position]:
        formatted = to_gate(symbol)
        want = formatted.replace("_", "")
        want_side = (side or "long").lower()
        positions = self._get_client().futures_api.list_positions(SETTLE)
        for pos in positions:
            raw_size = float(pos.size)
            if raw_size == 0:
                continue
            pos_symbol = pos.contract.replace("_", "")
            if pos_symbol != want:
                continue
            size_contract = abs(int(round(raw_size)))
            if size_contract <= 0:
                continue
            multiplier = self.get_contract_info(symbol)["quanto_multiplier"]
            size_base = size_contract * multiplier
            entry = float(pos.entry_price)
            mode = str(getattr(pos, "mode", "") or "")
            if mode == "dual_long":
                pos_side = "long"
            elif mode == "dual_short":
                pos_side = "short"
            else:
                pos_side = "long" if raw_size > 0 else "short"
            if pos_side != want_side:
                continue
            return Position(
                symbol=pos_symbol,
                side=pos_side,
                size_contract=size_contract,
                size_usdt=size_base * entry,
                entry_price=entry,
                mark_price=float(pos.mark_price),
                unrealized_pnl=float(pos.unrealised_pnl),
            )
        return None

    def usdt_to_contracts(self, symbol: str, usdt_amount: float, price: float | None = None) -> int:
        if price is None:
            price = self.get_mark_price(symbol)
        info = self.get_contract_info(symbol)
        return contracts_from_usdt(
            usdt_amount,
            price,
            info["quanto_multiplier"],
            info["min_size"],
            info.get("max_size"),
        )

    def _place(self, symbol: str, side: str, contracts: int, reduce_only: bool = False) -> OrderResult:
        from gate_api import FuturesOrder
        from gate_api.exceptions import GateApiException

        formatted = to_gate(symbol)
        size = contracts if side == "BUY" else -contracts
        order = FuturesOrder(contract=formatted, size=size, price="0", tif="ioc", reduce_only=reduce_only)
        try:
            result = self._get_client().futures_api.create_futures_order(SETTLE, order)
        except GateApiException as exc:
            logger.error("Gate API 错误: %s", exc)
            return OrderResult(False, str(exc))
        raw_size = abs(int(getattr(result, "size", 0) or 0))
        left = abs(int(getattr(result, "left", 0) or 0))
        filled = max(raw_size - left, 0)
        finish_as = str(getattr(result, "finish_as", "") or "")
        status = str(getattr(result, "status", "") or "")
        if filled <= 0:
            msg = f"未成交 status={status} finish_as={finish_as}"
            logger.error("Gate %s", msg)
            return OrderResult(False, msg)
        fill = float(getattr(result, "fill_price", 0) or 0) or self.get_mark_price(symbol)
        multiplier = self.get_contract_info(symbol)["quanto_multiplier"]
        return OrderResult(
            True,
            "ok",
            fill_price=fill,
            size_usdt=filled * multiplier * fill,
            contracts=filled,
        )

    def open_long(self, symbol: str, usdt_amount: float) -> OrderResult:
        price = self.get_mark_price(symbol)
        contracts = self.usdt_to_contracts(symbol, usdt_amount, price)
        if contracts <= 0:
            return OrderResult(False, "无效张数")
        logger.info("Gate 开多 %s 目标 %.2f USDT -> %s 张", symbol, usdt_amount, contracts)
        return self._place(symbol, "BUY", contracts)

    def close_long(self, symbol: str) -> OrderResult:
        pos = self.get_position(symbol, side="long")
        if pos is None or pos.side != "long" or pos.size_contract <= 0:
            return OrderResult(False, "无多仓")
        logger.info("Gate 平多 %s %s 张", symbol, pos.size_contract)
        return self._place(symbol, "SELL", pos.size_contract, reduce_only=True)
