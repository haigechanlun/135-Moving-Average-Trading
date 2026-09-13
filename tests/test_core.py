from __future__ import annotations

import pandas as pd
import pytest

from njm135.core.indicators import add_ma_system, golden_cross, sma
from njm135.core.patterns import detect_patterns
from njm135.core.strategy import StrategyConfig, generate_signals
from njm135.backtest import analyze


def test_sma_known_window() -> None:
    close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = sma(close, 3)
    assert pd.isna(out.iloc[1])
    assert out.iloc[2] == pytest.approx(2.0)
    assert out.iloc[4] == pytest.approx(4.0)


def test_golden_cross() -> None:
    fast = pd.Series([1.0, 1.0, 3.0, 4.0])
    slow = pd.Series([2.0, 2.0, 2.0, 2.0])
    gc = golden_cross(fast, slow)
    assert not bool(gc.iloc[1])
    assert bool(gc.iloc[2])
    assert not bool(gc.iloc[3])


def test_bull_and_bear_alignment() -> None:
    n = 80
    close = pd.Series(range(1, n + 1), dtype=float)
    bars = pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close})
    framed = add_ma_system(bars)
    assert bool(framed["bull_align"].iloc[-1])
    assert not bool(framed["bear_align"].iloc[-1])

    down = pd.Series(range(n, 0, -1), dtype=float)
    bars_down = pd.DataFrame({"open": down, "high": down + 1, "low": down - 1, "close": down})
    framed_down = add_ma_system(bars_down)
    assert bool(framed_down["bear_align"].iloc[-1])


def test_junxian_huhuan_and_fendao() -> None:
    close = pd.Series([10.0] * 60 + [20.0] * 40)
    bars = pd.DataFrame({"open": close, "high": close + 0.1, "low": close - 0.1, "close": close})
    framed = detect_patterns(add_ma_system(bars))
    assert framed["junxian_huhuan"].sum() >= 1

    close2 = pd.Series([20.0] * 60 + [5.0] * 40)
    bars2 = pd.DataFrame({"open": close2, "high": close2 + 0.1, "low": close2 - 0.1, "close": close2})
    framed2 = detect_patterns(add_ma_system(bars2))
    assert framed2["fendao_yangbiao"].sum() >= 1


def test_hongxing_chuqiang_on_constructed_series() -> None:
    down = [30.0 - 0.2 * i for i in range(70)]
    flat = [down[-1]] * 16
    rebound = down[-1] * 1.04
    close = pd.Series(down + flat + [rebound])
    open_ = close.copy()
    open_.iloc[-1] = close.iloc[-2]
    bars = pd.DataFrame(
        {"open": open_, "high": close * 1.01, "low": close * 0.99, "close": close}
    )
    framed = detect_patterns(add_ma_system(bars))
    assert bool(framed["hongxing_chuqiang"].iloc[-1])


def test_break_ma_is_a_state_not_a_crossing() -> None:
    """收盘在均线下方的每一根都算离场条件，否则在均线下方建的仓会没有出口。"""
    close = pd.Series([10.0] * 60 + [9.0] * 10)
    bars = pd.DataFrame({"open": close, "high": close + 0.1, "low": close - 0.1, "close": close})
    framed = detect_patterns(add_ma_system(bars))
    below = framed["close"] < framed["ma13"]
    assert below.iloc[-5:].all()
    assert framed.loc[below, "break_ma13"].all()
    assert not framed.loc[~below & framed["ma13"].notna(), "break_ma13"].any()


def test_exit_ma_switches_exit_line() -> None:
    n = 4
    flags = pd.DataFrame(
        {col: [False] * n for col in ("break_ma13", "break_ma34", "break_ma55")}
    )
    for col in (
        "hongxing_chuqiang", "mayi_shangshu", "heike_dianji", "hongyi_xianv", "haidi_laoyue",
        "junxian_huhuan", "sanxian_tuijin", "meikai_erdu", "zou_sifang", "langzi_huitou",
        "yi_yang_chuan_sanxian", "yizhi_duxiu", "dushang_gaolou", "jianhao_jiushou",
        "yi_yin_po_sanxian", "yi_jian_chuan_xin", "fendao_yangbiao",
    ):
        flags[col] = [False] * n
    flags.loc[1, "break_ma13"] = True
    flags.loc[2, "break_ma34"] = True

    ma13_exit = generate_signals(flags, StrategyConfig(exit_ma=13))["sell"].tolist()
    ma34_exit = generate_signals(flags, StrategyConfig(exit_ma=34))["sell"].tolist()
    assert ma13_exit == [False, True, False, False]
    assert ma34_exit == [False, False, True, False]

    with pytest.raises(ValueError):
        StrategyConfig(exit_ma=20)


def test_pipeline_backtest_runs() -> None:
    n = 160
    close = pd.Series([10.0] * 80 + list(range(11, 91)), dtype=float)
    bars = pd.DataFrame(
        {
            "open": close.shift(1).fillna(close.iloc[0]),
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": 1_000_000,
        }
    )
    framed, result = analyze(bars)
    assert "ma13" in framed.columns
    assert "buy" in framed.columns
    assert len(result.equity) == n
    assert result.equity.iloc[0] > 0


def test_same_bar_sell_beats_buy() -> None:
    n = 10
    flags = pd.DataFrame(
        {
            "hongxing_chuqiang": [False] * n,
            "mayi_shangshu": [False] * n,
            "heike_dianji": [False] * n,
            "hongyi_xianv": [False] * n,
            "haidi_laoyue": [False] * n,
            "junxian_huhuan": [False] * n,
            "sanxian_tuijin": [False] * n,
            "meikai_erdu": [False] * n,
            "zou_sifang": [False] * n,
            "langzi_huitou": [False] * n,
            "yi_yang_chuan_sanxian": [False] * n,
            "yizhi_duxiu": [False] * n,
            "dushang_gaolou": [False] * n,
            "jianhao_jiushou": [False] * n,
            "yi_yin_po_sanxian": [False] * n,
            "yi_jian_chuan_xin": [False] * n,
            "fendao_yangbiao": [False] * n,
            "break_ma13": [False] * n,
        }
    )
    flags.loc[9, "junxian_huhuan"] = True
    flags.loc[9, "yi_yin_po_sanxian"] = True
    out = generate_signals(flags)
    assert bool(out["sell"].iloc[-1])
    assert not bool(out["buy"].iloc[-1])
