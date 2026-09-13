from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def _log_axis_with_plain_ticks(ax: plt.Axes) -> None:
    """对数轴改成 8,000 / 20,000 这类真实数字，避免只剩 10⁴ 看不出量级差异。"""
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(LogLocator(base=10.0, subs=(1.0, 2.0, 5.0)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos: f"{v:,.0f}"))
    ax.yaxis.set_minor_formatter(NullFormatter())


def _fills(bars: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """真实成交：position 由 0→1 是买入，1→0 是卖出，成交价按当根开盘。"""
    pos = bars["position"].fillna(0.0)
    change = pos.diff().fillna(pos)
    return bars[change > 0], bars[change < 0]


def _holding_spans(bars: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    pos = bars["position"].fillna(0.0) > 0
    if not pos.any():
        return []
    groups = (pos != pos.shift()).cumsum()
    spans = []
    for _, seg in bars[pos].groupby(groups[pos]):
        spans.append((seg.index[0], seg.index[-1]))
    return spans


def plot_analysis(bars: pd.DataFrame, path: str | Path) -> None:
    """三段图：价格与真实成交 / 净值 / 回撤。图上只画策略真正用到的信号。"""
    has_equity = "equity" in bars.columns
    has_pos = "position" in bars.columns
    rows = 3 if has_equity else 1
    fig, axes = plt.subplots(
        rows,
        1,
        figsize=(12, 4 + 2.4 * (rows - 1)),
        sharex=True,
        gridspec_kw={"height_ratios": [2, 1, 1][:rows]},
    )
    ax_px = axes[0] if rows > 1 else axes

    ax_px.plot(bars.index, bars["close"], color="#222222", linewidth=1.0, label="收盘")
    ax_px.plot(bars.index, bars["ma13"], color="#d62728", linewidth=1.0, label="MA13")
    ax_px.plot(bars.index, bars["ma34"], color="#1f77b4", linewidth=1.0, label="MA34")
    ax_px.plot(bars.index, bars["ma55"], color="#2ca02c", linewidth=1.0, label="MA55")
    for col in sorted(set(bars.columns) - {"ma13", "ma34", "ma55"}):
        if col.startswith("ma") and col[2:].isdigit():
            ax_px.plot(
                bars.index,
                bars[col],
                color="#9467bd",
                linewidth=1.0,
                linestyle="--",
                label=col.upper(),
            )

    if has_pos:
        for start, end in _holding_spans(bars):
            ax_px.axvspan(start, end, color="#ffd27f", alpha=0.35, linewidth=0)

    # 触发过、但未必成交的信号（已持仓时的买信号会被忽略）
    if "buy" in bars.columns:
        sig = bars[bars["buy"].fillna(False)]
        ax_px.scatter(sig.index, sig["low"], marker="^", s=14, color="#ff7f0e", alpha=0.45, label="买信号")
    if "sell" in bars.columns:
        sig = bars[bars["sell"].fillna(False)]
        ax_px.scatter(sig.index, sig["high"], marker="v", s=8, color="#17becf", alpha=0.25, label="卖信号")

    if has_pos:
        entries, exits = _fills(bars)
        ax_px.scatter(
            entries.index, entries["open"], marker="^", s=90, color="#1a9850",
            edgecolors="black", linewidths=0.4, zorder=6, label=f"买入成交({len(entries)})",
        )
        ax_px.scatter(
            exits.index, exits["open"], marker="v", s=90, color="#d73027",
            edgecolors="black", linewidths=0.4, zorder=6, label=f"卖出成交({len(exits)})",
        )

    ax_px.set_ylabel("价格 USDT")
    _log_axis_with_plain_ticks(ax_px)
    ax_px.legend(loc="upper left", ncol=4, fontsize=8)
    ax_px.set_title("135 均线系统（13 / 34 / 55）：黄色底为持仓期")
    ax_px.grid(True, alpha=0.25)

    if not has_equity:
        fig.tight_layout()
        fig.savefig(path, dpi=120)
        plt.close(fig)
        return

    # 两条线都是「同样的初始资金投进去会变成多少钱」，起点相同才好比。
    eq = bars["equity"]
    initial = float(eq.iloc[0])
    bh = initial * bars["close"] / bars["close"].iloc[0]
    ax_eq = axes[1]
    ax_eq.plot(
        eq.index, eq, color="#111111", linewidth=1.2,
        label=f"策略 {eq.iloc[-1]:,.0f}（{eq.iloc[-1] / initial:.1f}×）",
    )
    ax_eq.plot(eq.index, eq.cummax(), color="#999999", linewidth=0.8, linestyle="--", label="历史高点")
    ax_eq.plot(
        bh.index, bh, color="#8c564b", linewidth=0.9, alpha=0.7,
        label=f"买入持有 {bh.iloc[-1]:,.0f}（{bh.iloc[-1] / initial:.1f}×）",
    )
    ax_eq.axhline(initial, color="#999999", linewidth=0.6, alpha=0.6)
    _log_axis_with_plain_ticks(ax_eq)
    ax_eq.set_ylabel(f"净值 USDT（初始 {initial:,.0f}）")
    ax_eq.legend(loc="upper left", fontsize=8)
    ax_eq.grid(True, alpha=0.25)

    dd = (eq / eq.cummax() - 1.0) * 100.0
    bh_dd = (bh / bh.cummax() - 1.0) * 100.0
    ax_dd = axes[2]
    ax_dd.fill_between(bh_dd.index, bh_dd, 0.0, color="#8c564b", alpha=0.22)
    ax_dd.plot(bh_dd.index, bh_dd, color="#8c564b", linewidth=0.9, label=f"买入持有 {bh_dd.min():.1f}%")
    ax_dd.fill_between(dd.index, dd, 0.0, color="#d73027", alpha=0.35)
    ax_dd.plot(dd.index, dd, color="#d73027", linewidth=0.9, label=f"策略 {dd.min():.1f}%")
    bh_worst = bh_dd.idxmin()
    worst = dd.idxmin()
    ax_dd.annotate(
        f"买持 {bh_dd.min():.1f}%\n{bh_worst.date()}",
        xy=(bh_worst, bh_dd.min()),
        xytext=(8, 8),
        textcoords="offset points",
        fontsize=8,
        color="#8c564b",
    )
    ax_dd.annotate(
        f"策略 {dd.min():.1f}%\n{worst.date()}",
        xy=(worst, dd.min()),
        xytext=(8, 18),
        textcoords="offset points",
        fontsize=8,
        color="#d73027",
    )
    ax_dd.set_ylabel("回撤 %")
    ax_dd.legend(loc="lower left", fontsize=8)
    ax_dd.grid(True, alpha=0.25)

    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
