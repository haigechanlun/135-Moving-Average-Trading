from __future__ import annotations


def to_binance(symbol: str) -> str:
    s = symbol.upper().replace("/", "").replace("_", "")
    return s


def to_gate(symbol: str) -> str:
    s = to_binance(symbol)
    if s.endswith("USDT") and "_" not in s:
        return s[:-4] + "_USDT"
    return s.replace("/", "_")
