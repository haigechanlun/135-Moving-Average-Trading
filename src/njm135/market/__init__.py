"""行情模块：Binance K 线为主，CSV / 合成数据用于离线。"""

from njm135.market.binance import fetch_binance_klines
from njm135.market.csv_feed import load_csv
from njm135.market.normalize import normalize_ohlcv
from njm135.market.store import kline_path, load_klines, save_klines
from njm135.market.synthetic import make_demo_bars
from njm135.market.validate import KlineReport, inspect_klines

__all__ = [
    "KlineReport",
    "fetch_binance_klines",
    "inspect_klines",
    "kline_path",
    "load_csv",
    "load_klines",
    "make_demo_bars",
    "normalize_ohlcv",
    "save_klines",
]

from njm135.market.binance import fetch_binance_klines
from njm135.market.csv_feed import load_csv
from njm135.market.normalize import normalize_ohlcv
from njm135.market.synthetic import make_demo_bars

__all__ = [
    "fetch_binance_klines",
    "load_csv",
    "make_demo_bars",
    "normalize_ohlcv",
]
