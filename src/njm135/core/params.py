"""形态量化参数。编程前必须钉死的阈值都集中在这里。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Confirm = Literal["close"]


@dataclass(frozen=True)
class PatternParams:
    """默认按收盘确认；均线类型由 ``add_ma_system(ma_type=)`` 决定。"""

    confirm: Confirm = "close"

    flatten_lookback: int = 2
    flatten_pct: float = 0.005

    near_pct: float = 0.015
    near_atr: float = 0.8
    atr_window: int = 14

    volume_window: int = 5
    volume_expand: float = 1.2
    volume_shrink: float = 0.8

    downtrend_lookback: int = 20
    deep_below_13: float = 0.06

    small_yang_max: float = 0.05
    ant_yang_bars: int = 5
    ant_ma_spread: float = 0.03

    high_lookback: int = 30
    high_bias: float = 0.08

    jianhao_bias: float = 0.10

    converge_pct: float = 0.03
    converge_bars: int = 20

    upper_shadow: float = 0.025
    detach_ma13: float = 0.05

    gap_up: float = 0.029
    yin_body: float = 0.03

    event_lookback: int = 40
    digest_bars: int = 5
