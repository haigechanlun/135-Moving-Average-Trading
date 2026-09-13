"""13 种经典形态目录（《黑客点击：神奇的135均线》公开名单）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Stage = Literal["bottom", "launch", "rally", "digest", "top"]
Role = Literal["buy", "add", "sell"]


@dataclass(frozen=True)
class PatternSpec:
    key: str
    name: str
    stage: Stage
    role: Role
    meaning: str


CLASSIC_13: tuple[PatternSpec, ...] = (
    PatternSpec("hongxing_chuqiang", "红杏出墙", "bottom", "buy", "空头排列中，13线走平，收盘首次站上13线"),
    PatternSpec("mayi_shangshu", "蚂蚁上树", "bottom", "buy", "连续小阳缓慢上行，接近或突破55线"),
    PatternSpec("heike_dianji", "黑客点击", "launch", "buy", "突破55后缩量回踩，在13与55结点附近获支撑"),
    PatternSpec("hongyi_xianv", "红衣侠女", "launch", "buy", "13上穿55附近出现放量阳线"),
    PatternSpec("haidi_laoyue", "海底捞月", "rally", "buy", "上涨结构中13下穿中长期线后再上穿55"),
    PatternSpec("junxian_huhuan", "均线互换", "rally", "buy", "34由下向上穿越55，趋势由弱转强"),
    PatternSpec("sanxian_tuijin", "三线推进", "rally", "buy", "13/34/55收敛后同步向上，常伴一阳穿三线"),
    PatternSpec("meikai_erdu", "梅开二度", "rally", "buy", "13短暂跌破34后再次金叉34"),
    PatternSpec("zou_sifang", "走四方", "digest", "add", "上涨途中围绕13线有节奏横向整理"),
    PatternSpec("langzi_huitou", "浪子回头", "digest", "buy", "回踩55附近获支撑后重新转强"),
    PatternSpec("yizhi_duxiu", "一枝独秀", "top", "sell", "高位脱离均线的长上影阳线"),
    PatternSpec("dushang_gaolou", "独上高楼", "top", "sell", "高位跳空后回落，量价或均线支持不足"),
    PatternSpec("jianhao_jiushou", "见好就收", "top", "sell", "13与55乖离过大，上涨动能减弱"),
)

# 定义清楚、建议一并代码化的补充形态
EXTRA_PATTERNS: tuple[PatternSpec, ...] = (
    PatternSpec("yi_yang_chuan_sanxian", "一阳穿三线", "launch", "buy", "一根阳线收盘同时站上13/34/55"),
    PatternSpec("yi_yin_po_sanxian", "一阴破三线", "top", "sell", "一根阴线收盘同时跌破13/34/55"),
    PatternSpec("yi_jian_chuan_xin", "一箭穿心", "top", "sell", "大阴从均线簇上方贯穿至下方"),
    PatternSpec("fendao_yangbiao", "分道扬镳", "top", "sell", "13下穿34，短中期趋势转弱"),
)


def classic_keys() -> tuple[str, ...]:
    return tuple(p.key for p in CLASSIC_13)
