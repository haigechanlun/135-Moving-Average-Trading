"""回测常用绩效：夏普、年化、回撤、盈亏比。加密按 24/7 年化。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def bars_per_year(index: pd.Index) -> float:
    if not isinstance(index, pd.DatetimeIndex) or len(index) < 2:
        return 365.25
    diffs = pd.Series(index).diff().dropna()
    med = diffs.median()
    if pd.isna(med) or med <= pd.Timedelta(0):
        return 365.25
    return float(pd.Timedelta(days=365.25) / med)


def calendar_years(index: pd.Index) -> float:
    if not isinstance(index, pd.DatetimeIndex) or len(index) < 2:
        return max(len(index) / 365.25, 1e-9)
    span = index[-1] - index[0]
    days = span.total_seconds() / 86400.0
    return max(days / 365.25, 1e-9)


@dataclass(frozen=True)
class Performance:
    total_return: float
    annual_return: float
    buy_hold_return: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    max_dd_days: float
    trade_count: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    avg_hold_bars: float
    bars_per_year: float


def _ratio(numer: float, denom: float) -> float:
    if denom == 0 or not np.isfinite(denom):
        return float("nan")
    return float(numer / denom)


def compute_performance(
    equity: pd.Series,
    trades: pd.DataFrame,
    *,
    initial_cash: float,
    close: pd.Series | None = None,
    risk_free: float = 0.0,
) -> Performance:
    total = float(equity.iloc[-1] / initial_cash - 1.0) if initial_cash else float("nan")
    years = calendar_years(equity.index)
    bpy = bars_per_year(equity.index)
    annual = (1.0 + total) ** (1.0 / years) - 1.0 if years > 0 and total > -1.0 else float("nan")

    rets = equity.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).dropna()
    rf_bar = risk_free / bpy if bpy else 0.0
    excess = rets - rf_bar
    vol = float(excess.std(ddof=1)) if len(excess) > 1 else 0.0
    mean_ex = float(excess.mean()) if len(excess) else 0.0
    if vol < 1e-12:
        sharpe = float("inf") if mean_ex > 0 else (float("-inf") if mean_ex < 0 else float("nan"))
    else:
        sharpe = mean_ex / vol * np.sqrt(bpy)

    # Sortino: downside deviation of all bars (zeros included), not std of losing bars only.
    down_sq = np.minimum(excess.to_numpy(dtype=float), 0.0) ** 2
    down_vol = float(np.sqrt(np.mean(down_sq))) if len(excess) else 0.0
    if down_vol < 1e-12:
        sortino = float("inf") if mean_ex > 0 else float("nan")
    else:
        sortino = mean_ex / down_vol * np.sqrt(bpy)

    peak = equity.cummax()
    dd = equity / peak - 1.0
    max_dd = float(dd.min()) if len(dd) else 0.0
    calmar = _ratio(annual, abs(max_dd)) if max_dd < 0 else float("nan")

    in_dd = dd < 0
    if in_dd.any() and isinstance(equity.index, pd.DatetimeIndex):
        groups = (in_dd != in_dd.shift()).cumsum()
        durations = []
        for _, g in dd[in_dd].groupby(groups):
            durations.append((g.index[-1] - g.index[0]).total_seconds() / 86400.0)
        max_dd_days = float(max(durations)) if durations else 0.0
    else:
        max_dd_days = float("nan")

    bh = float("nan")
    if close is not None and len(close) >= 2 and close.iloc[0]:
        bh = float(close.iloc[-1] / close.iloc[0] - 1.0)

    closed = trades.dropna(subset=["return"]) if not trades.empty and "return" in trades.columns else pd.DataFrame()
    n_trades = len(closed)
    win_rate = float((closed["return"] > 0).mean()) if n_trades else 0.0
    wins = closed.loc[closed["return"] > 0, "return"] if n_trades else pd.Series(dtype=float)
    losses = closed.loc[closed["return"] <= 0, "return"] if n_trades else pd.Series(dtype=float)
    profit_factor = _ratio(float(wins.sum()), abs(float(losses.sum()))) if n_trades else float("nan")
    avg_win = float(wins.mean()) if len(wins) else float("nan")
    avg_loss = float(losses.mean()) if len(losses) else float("nan")

    avg_hold = float("nan")
    if n_trades and "entry_time" in closed.columns and "exit_time" in closed.columns:
        hold = pd.to_datetime(closed["exit_time"]) - pd.to_datetime(closed["entry_time"])
        bar = pd.Timedelta(days=365.25) / bpy if bpy else pd.Timedelta(days=1)
        avg_hold = float((hold / bar).mean())

    return Performance(
        total_return=total,
        annual_return=float(annual),
        buy_hold_return=bh,
        sharpe=float(sharpe),
        sortino=float(sortino),
        calmar=float(calmar),
        max_drawdown=max_dd,
        max_dd_days=max_dd_days,
        trade_count=n_trades,
        win_rate=win_rate,
        profit_factor=float(profit_factor),
        avg_win=avg_win,
        avg_loss=avg_loss,
        avg_hold_bars=avg_hold,
        bars_per_year=bpy,
    )
