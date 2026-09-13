"""下一根开盘成交的简易回测。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from njm135.backtest.metrics import Performance, compute_performance
from njm135.risk import RiskConfig, RiskManager, compute_indicators


def _pct(x: float) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.2%}"


def _num(x: float, digits: int = 2) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.{digits}f}"


@dataclass(frozen=True)
class BacktestResult:
    equity: pd.Series
    trades: pd.DataFrame
    bars: pd.DataFrame
    total_return: float
    max_drawdown: float
    trade_count: int
    win_rate: float
    open_trades: int = 0
    performance: Performance | None = None

    def summary(self) -> str:
        p = self.performance
        wr = f"{self.win_rate:.1%}" if self.trade_count else "n/a"
        if p is None:
            return (
                f"已平仓次数: {self.trade_count}\n"
                f"未平仓次数: {self.open_trades}\n"
                f"胜率: {wr}\n"
                f"累计收益: {self.total_return:.2%}\n"
                f"最大回撤: {self.max_drawdown:.2%}"
            )
        return (
            f"已平仓次数: {p.trade_count}\n"
            f"未平仓次数: {self.open_trades}\n"
            f"胜率: {wr}\n"
            f"累计收益: {_pct(p.total_return)}\n"
            f"年化收益: {_pct(p.annual_return)}\n"
            f"同期买持: {_pct(p.buy_hold_return)}\n"
            f"夏普率: {_num(p.sharpe)}\n"
            f"索提诺: {_num(p.sortino)}\n"
            f"卡尔玛: {_num(p.calmar)}\n"
            f"最大回撤: {_pct(p.max_drawdown)}\n"
            f"最长回撤: {_num(p.max_dd_days, 1)} 天\n"
            f"盈亏比(PF): {_num(p.profit_factor)}\n"
            f"平均盈利: {_pct(p.avg_win)}\n"
            f"平均亏损: {_pct(p.avg_loss)}\n"
            f"平均持仓: {_num(p.avg_hold_bars, 1)} 根"
            f"{self._exit_breakdown()}"
            f"{self._risk_block_breakdown()}"
        )

    def _exit_breakdown(self) -> str:
        if "exit_reason" not in self.trades.columns:
            return ""
        counts = self.trades["exit_reason"].replace("", pd.NA).dropna().value_counts()
        if counts.empty or set(counts.index) == {"signal"}:
            return ""
        names = {"signal": "形态信号", "stop": "固定止损", "trail": "移动止损", "atr": "ATR止损"}
        parts = ", ".join(f"{names.get(k, k)} {v}" for k, v in counts.items())
        return f"\n离场原因: {parts}"

    def _risk_block_breakdown(self) -> str:
        if "risk_blocked" not in self.bars.columns:
            return ""
        counts = self.bars["risk_blocked"].replace("", pd.NA).dropna().value_counts()
        if counts.empty:
            return ""
        names = {"cooldown": "冷却期", "regime": "大均线过滤"}
        parts = ", ".join(f"{names.get(k, k)} {v}" for k, v in counts.items())
        return f"\n拦截买信号: {parts}"


def run_backtest(
    bars: pd.DataFrame,
    *,
    commission: float = 0.001,
    initial_cash: float = 1.0,
    position_pct: float = 1.0,
    risk: RiskConfig | None = None,
) -> BacktestResult:
    """多头：信号当日收盘确认，下一根 K 线开盘成交（与实盘「已收盘后再下单」对齐）。"""
    if not 0.0 < position_pct <= 1.0:
        raise ValueError("position_pct 须在 (0, 1] 内")
    needed = {"open", "close", "buy", "sell"}
    missing = needed - set(bars.columns)
    if missing:
        raise ValueError(f"缺少列: {sorted(missing)}")

    risk_manager = RiskManager(risk)
    risk_ind = compute_indicators(bars, risk_manager.config)
    atr = risk_ind.atr
    regime_ma = risk_ind.regime_ma

    n = len(bars)
    position = np.zeros(n, dtype=float)
    risk_blocked = np.full(n, "", dtype=object)
    cash = np.zeros(n, dtype=float)
    holdings = np.zeros(n, dtype=float)
    cash[0] = initial_cash

    in_pos = False
    qty = 0.0
    entry_px = 0.0
    trades: list[dict] = []

    opens = bars["open"].to_numpy(dtype=float)
    closes = bars["close"].to_numpy(dtype=float)
    buys = bars["buy"].fillna(False).to_numpy(dtype=bool)
    sells = bars["sell"].fillna(False).to_numpy(dtype=bool)
    index = bars.index

    pending_buy = False
    pending_sell = False
    pending_reason = ""
    peak_close = 0.0

    for i in range(n):
        if i > 0:
            cash[i] = cash[i - 1]
            qty = holdings[i - 1]
            in_pos = qty > 0

        if pending_buy and not in_pos:
            px = opens[i] * (1.0 + commission)
            notional = cash[i] * position_pct
            if notional > 0 and px > 0:
                qty = notional / px
                cash[i] = cash[i] - notional
                in_pos = True
                entry_px = px
                peak_close = closes[i]
                trades.append(
                    {
                        "entry_time": index[i],
                        "entry_price": px,
                        "exit_time": pd.NaT,
                        "exit_price": np.nan,
                        "return": np.nan,
                        "exit_reason": "",
                    }
                )
            pending_buy = False

        if pending_sell and in_pos:
            px = opens[i] * (1.0 - commission)
            cash[i] = cash[i] + qty * px
            ret = px / entry_px - 1.0 if entry_px else np.nan
            trades[-1]["exit_time"] = index[i]
            trades[-1]["exit_price"] = px
            trades[-1]["return"] = ret
            trades[-1]["exit_reason"] = pending_reason
            risk_manager.record_trade(float(ret))
            qty = 0.0
            in_pos = False
            pending_sell = False
            pending_reason = ""

        holdings[i] = qty
        position[i] = 1.0 if in_pos else 0.0

        if in_pos:
            peak_close = max(peak_close, closes[i])

        if in_pos and sells[i]:
            pending_sell = True
            pending_reason = "signal"
            pending_buy = False
        elif in_pos:
            atr_i = float(atr[i]) if atr is not None else float("nan")
            reason = risk_manager.exit_reason(closes[i], entry_px, peak_close, atr_i)
            if reason:
                pending_sell = True
                pending_reason = reason
                pending_buy = False
        elif (not in_pos) and buys[i]:
            ma_i = float(regime_ma[i]) if regime_ma is not None else float("nan")
            risk_blocked[i] = risk_manager.entry_block_reason(closes[i], ma_i)
            if not risk_blocked[i]:
                pending_buy = True
                pending_sell = False

        risk_manager.finish_bar()

    mark = holdings * closes + cash
    equity = pd.Series(mark, index=index, name="equity")
    peak = equity.cummax()
    drawdown = (equity / peak - 1.0).min()

    trade_df = pd.DataFrame(trades)
    closed = trade_df.dropna(subset=["return"]) if not trade_df.empty else trade_df
    open_count = int(len(trade_df) - len(closed)) if not trade_df.empty else 0
    win_rate = float((closed["return"] > 0).mean()) if len(closed) else 0.0
    perf = compute_performance(
        equity,
        trade_df,
        initial_cash=initial_cash,
        close=bars["close"],
    )

    out = bars.copy()
    out["position"] = position
    out["equity"] = equity
    out["risk_blocked"] = risk_blocked
    if regime_ma is not None and risk_manager.config.regime_ma is not None:
        out[f"ma{risk_manager.config.regime_ma}"] = regime_ma

    return BacktestResult(
        equity=equity,
        trades=trade_df,
        bars=out,
        total_return=float(equity.iloc[-1] / initial_cash - 1.0),
        max_drawdown=float(drawdown),
        trade_count=len(closed),
        win_rate=win_rate,
        open_trades=open_count,
        performance=perf,
    )
