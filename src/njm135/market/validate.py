"""K 线连续性与 OHLC 异常检查。"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from njm135.market.interval import interval_delta


@dataclass
class KlineReport:
    bars: int
    start: pd.Timestamp | None
    end: pd.Timestamp | None
    duplicates: int = 0
    unordered: bool = False
    gaps: list[tuple[pd.Timestamp, pd.Timestamp, float]] = field(default_factory=list)
    ohlc_errors: int = 0
    non_positive: int = 0
    zero_volume: int = 0
    big_jumps: list[tuple[pd.Timestamp, float]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (
            self.bars > 0
            and self.duplicates == 0
            and not self.unordered
            and not self.gaps
            and self.ohlc_errors == 0
            and self.non_positive == 0
        )

    def summary(self) -> str:
        lines = [
            f"根数: {self.bars}",
            f"区间: {self.start} -> {self.end}",
            f"重复时间: {self.duplicates}",
            f"未排序: {self.unordered}",
            f"缺口: {len(self.gaps)}",
            f"OHLC 不合法: {self.ohlc_errors}",
            f"非正价格: {self.non_positive}",
            f"零成交量: {self.zero_volume}",
            f"异常跳空(警告): {len(self.big_jumps)}",
            f"结论: {'通过' if self.ok else '有异常'}",
        ]
        for a, b, days in self.gaps[:20]:
            lines.append(f"  缺口 {a} -> {b}  间隔 {days:.2f} 根")
        for ts, ret in self.big_jumps[:10]:
            lines.append(f"  跳空 {ts}  {ret:+.2%}")
        if len(self.gaps) > 20:
            lines.append(f"  ... 另有 {len(self.gaps) - 20} 个缺口")
        return "\n".join(lines)


def inspect_klines(
    bars: pd.DataFrame,
    interval: str,
    *,
    jump_pct: float = 0.25,
) -> KlineReport:
    if bars.empty:
        return KlineReport(bars=0, start=None, end=None)

    idx = pd.DatetimeIndex(bars.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC")

    duplicates = int(idx.duplicated().sum())
    unordered = bool(not idx.is_monotonic_increasing)
    ordered = bars.copy()
    ordered.index = idx
    ordered = ordered[~ordered.index.duplicated(keep="last")].sort_index()

    delta = interval_delta(interval)
    gaps: list[tuple[pd.Timestamp, pd.Timestamp, float]] = []
    times = ordered.index
    for prev, cur in zip(times[:-1], times[1:]):
        expected = prev + delta
        if cur > expected:
            missing = (cur - prev) / delta
            gaps.append((prev, cur, float(missing)))

    high_ok = ordered["high"] + 1e-12 >= ordered[["open", "close"]].max(axis=1)
    low_ok = ordered["low"] - 1e-12 <= ordered[["open", "close"]].min(axis=1)
    hl_ok = ordered["high"] + 1e-12 >= ordered["low"]
    ohlc_errors = int((~(high_ok & low_ok & hl_ok)).sum())
    non_positive = int((ordered[["open", "high", "low", "close"]] <= 0).any(axis=1).sum())
    zero_volume = int((ordered["volume"] <= 0).sum()) if "volume" in ordered.columns else 0

    ret = ordered["close"].pct_change().abs()
    jump_idx = ret[ret > jump_pct].dropna()
    big_jumps = [(ts, float(jump_idx.loc[ts])) for ts in jump_idx.index]

    return KlineReport(
        bars=len(ordered),
        start=ordered.index[0],
        end=ordered.index[-1],
        duplicates=duplicates,
        unordered=unordered,
        gaps=gaps,
        ohlc_errors=ohlc_errors,
        non_positive=non_positive,
        zero_volume=zero_volume,
        big_jumps=big_jumps,
    )
