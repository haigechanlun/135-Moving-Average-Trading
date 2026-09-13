"""把同一套风控参数接到 backtest / live CLI。"""

from __future__ import annotations

import argparse

from njm135.risk.config import RiskConfig


def add_risk_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--stop-loss", type=float, help="固定止损，相对进场价，如 0.08")
    parser.add_argument("--trailing", type=float, help="移动止损，相对持仓期最高收盘，如 0.15")
    parser.add_argument("--atr-stop", type=float, help="ATR 跟踪止损倍数，如 3")
    parser.add_argument("--loss-streak", type=int, help="连续亏损 N 笔后暂停开仓")
    parser.add_argument("--cooldown-bars", type=int, help="连亏触发后冷却 K 根，需与 --loss-streak 同用")
    parser.add_argument("--regime-ma", type=int, help="仅收盘不低于该均线时允许开仓，如 100")


def risk_from_args(args: argparse.Namespace) -> RiskConfig:
    return RiskConfig(
        stop_loss_pct=args.stop_loss,
        trailing_pct=args.trailing,
        atr_mult=args.atr_stop,
        loss_streak=args.loss_streak,
        cooldown_bars=args.cooldown_bars,
        regime_ma=args.regime_ma,
    )


def risk_label(config: RiskConfig) -> str:
    if not config.enabled():
        return ""
    bits = []
    if config.stop_loss_pct is not None:
        bits.append(f"止损{config.stop_loss_pct:.0%}")
    if config.trailing_pct is not None:
        bits.append(f"移动止损{config.trailing_pct:.0%}")
    if config.atr_mult is not None:
        bits.append(f"ATR×{config.atr_mult:g}")
    if config.loss_streak is not None:
        bits.append(f"连亏{config.loss_streak}笔冷却{config.cooldown_bars}根")
    if config.regime_ma is not None:
        bits.append(f"MA{config.regime_ma}多头开关")
    return "  " + " ".join(bits)
