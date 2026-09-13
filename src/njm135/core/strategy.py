"""把形态映射为买卖信号。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from njm135.core.params import PatternParams

Intent = Literal["buy", "sell", "hold"]


@dataclass(frozen=True)
class StrategyConfig:
    """默认：优先 8 个易代码化信号；同棒既买又卖时卖优先。"""

    use_hongxing: bool = True
    use_mayi: bool = True
    use_heike: bool = True
    use_hongyi: bool = False
    use_haidi: bool = False
    use_huhuan: bool = True
    use_sanxian: bool = False
    use_meikai: bool = True
    use_zousifang: bool = False
    use_langzi: bool = False
    use_yiyang: bool = True

    exit_yizhi: bool = False
    exit_dushang: bool = False
    exit_jianhao: bool = False
    exit_yiyin: bool = True
    exit_yijian: bool = True
    exit_on_fendao: bool = True
    exit_on_break_ma13: bool = True
    exit_ma: int = 13
    """离场均线：收盘跌破它就走。13 最贴原书，34 / 55 更能拿住趋势。"""

    pattern_params: PatternParams | None = None

    def __post_init__(self) -> None:
        if self.exit_ma not in (13, 34, 55):
            raise ValueError("exit_ma 只能是 13 / 34 / 55")


def generate_signals(bars: pd.DataFrame, config: StrategyConfig | None = None) -> pd.DataFrame:
    cfg = config or StrategyConfig()
    out = bars.copy()
    buy = pd.Series(False, index=out.index)
    mapping_buy = [
        (cfg.use_hongxing, "hongxing_chuqiang"),
        (cfg.use_mayi, "mayi_shangshu"),
        (cfg.use_heike, "heike_dianji"),
        (cfg.use_hongyi, "hongyi_xianv"),
        (cfg.use_haidi, "haidi_laoyue"),
        (cfg.use_huhuan, "junxian_huhuan"),
        (cfg.use_sanxian, "sanxian_tuijin"),
        (cfg.use_meikai, "meikai_erdu"),
        (cfg.use_zousifang, "zou_sifang"),
        (cfg.use_langzi, "langzi_huitou"),
        (cfg.use_yiyang, "yi_yang_chuan_sanxian"),
    ]
    for enabled, col in mapping_buy:
        if enabled:
            buy = buy | out[col]

    sell = pd.Series(False, index=out.index)
    mapping_sell = [
        (cfg.exit_yizhi, "yizhi_duxiu"),
        (cfg.exit_dushang, "dushang_gaolou"),
        (cfg.exit_jianhao, "jianhao_jiushou"),
        (cfg.exit_yiyin, "yi_yin_po_sanxian"),
        (cfg.exit_yijian, "yi_jian_chuan_xin"),
        (cfg.exit_on_fendao, "fendao_yangbiao"),
        (cfg.exit_on_break_ma13, f"break_ma{cfg.exit_ma}"),
    ]
    for enabled, col in mapping_sell:
        if enabled:
            sell = sell | out[col]

    out["sell"] = sell.fillna(False)
    out["buy"] = buy.fillna(False) & ~out["sell"]
    return out


def last_intent(bars: pd.DataFrame) -> Intent:
    if bars.empty or "buy" not in bars.columns:
        return "hold"
    row = bars.iloc[-1]
    if bool(row["buy"]):
        return "buy"
    if bool(row["sell"]):
        return "sell"
    return "hold"


def annotate(bars: pd.DataFrame, *, ma_type: str = "sma", config: StrategyConfig | None = None) -> pd.DataFrame:
    from njm135.core.indicators import add_ma_system
    from njm135.core.patterns import detect_patterns

    cfg = config or StrategyConfig()
    framed = add_ma_system(bars, ma_type=ma_type)  # type: ignore[arg-type]
    framed = detect_patterns(framed, cfg.pattern_params)
    return generate_signals(framed, cfg)
