from __future__ import annotations

import argparse
import logging
from pathlib import Path

from njm135.backtest import analyze, plot_analysis
from njm135.market import fetch_binance_klines, inspect_klines, load_csv, make_demo_bars
from njm135.market.store import kline_path, save_klines
from njm135.risk.args import add_risk_arguments, risk_from_args, risk_label


def _cmd_backtest(args: argparse.Namespace) -> None:
    if args.csv:
        bars = load_csv(args.csv)
        source = str(args.csv)
    elif args.demo:
        bars = make_demo_bars()
        source = "synthetic"
    else:
        bars = fetch_binance_klines(
            args.symbol,
            args.interval,
            limit=args.limit,
            kind=args.kind,
        )
        source = f"binance {args.kind} {args.symbol} {args.interval}"

    from njm135.core.strategy import StrategyConfig

    risk = risk_from_args(args)
    framed, result = analyze(
        bars,
        ma_type=args.ma_type,
        config=StrategyConfig(exit_ma=args.exit_ma),
        risk=risk,
        initial_cash=args.cash,
        position_pct=args.position_pct,
    )
    print(f"{source}  仓位{args.position_pct:.0%}  离场线 MA{args.exit_ma}{risk_label(risk)}")
    print(result.summary())
    if not result.trades.empty:
        print()
        print(result.trades.to_string(index=False))
    if args.plot:
        plot_analysis(framed, args.plot)
        print(f"\n图已保存: {Path(args.plot).resolve()}")


def _cmd_live(args: argparse.Namespace) -> None:
    from njm135.core.strategy import StrategyConfig
    from njm135.live.engine import LiveEngine, LiveEngineConfig
    from njm135.live.paper import PaperBroker

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    dry_run = not args.live
    cfg = LiveEngineConfig(
        symbol=args.symbol,
        interval=args.interval,
        kind=args.kind,
        kline_limit=args.limit,
        ma_type=args.ma_type,
        strategy=StrategyConfig(exit_ma=args.exit_ma),
        risk=risk_from_args(args),
        position_pct=args.position_pct,
        poll_seconds=args.poll,
        dry_run=dry_run,
    )
    if args.live:
        from njm135.live.gate import GateBroker

        broker = GateBroker()
    else:
        broker = PaperBroker(cash=args.cash)
    engine = LiveEngine(broker, cfg)
    if args.once:
        print(engine.run_once())
        return
    engine.run_loop()


def _cmd_fetch(args: argparse.Namespace) -> None:
    bars = fetch_binance_klines(
        args.symbol,
        args.interval,
        limit=args.limit,
        kind=args.kind,
        drop_last_unclosed=True,
    )
    report = inspect_klines(bars, args.interval, jump_pct=args.jump)
    path = args.out or kline_path(args.symbol, args.interval, args.kind, args.data_dir)
    save_klines(bars, path)
    print(f"已保存: {path.resolve()}  ({len(bars)} 根)")
    print(report.summary())
    if not report.ok:
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="宁俊明 135 战法")
    sub = parser.add_subparsers(dest="cmd", required=True)

    bt = sub.add_parser("backtest", help="用 Binance 行情回测")
    bt.add_argument("--symbol", default="BTCUSDT")
    bt.add_argument("--interval", default="1d")
    bt.add_argument("--limit", type=int, default=1500)
    bt.add_argument("--kind", choices=("spot", "futures"), default="futures")
    bt.add_argument("--csv", type=Path)
    bt.add_argument("--demo", action="store_true", help="使用合成数据，不访问网络")
    bt.add_argument("--ma-type", choices=("sma", "ema"), default="sma")
    bt.add_argument("--cash", type=float, default=10_000.0)
    bt.add_argument("--position-pct", type=float, default=1)
    bt.add_argument("--exit-ma", type=int, choices=(13, 34, 55), default=55, help="收盘跌破该均线离场")
    add_risk_arguments(bt)
    bt.add_argument("--plot", type=Path, default=Path("135_backtest.png"))
    bt.set_defaults(func=_cmd_backtest)

    lv = sub.add_parser("live", help="Binance 信号 + Gate 下单")
    lv.add_argument("--symbol", default="BTCUSDT")
    lv.add_argument("--interval", default="15m")
    lv.add_argument("--limit", type=int, default=800)
    lv.add_argument("--kind", choices=("spot", "futures"), default="futures")
    lv.add_argument("--ma-type", choices=("sma", "ema"), default="sma")
    lv.add_argument("--position-pct", type=float, default=0.3)
    lv.add_argument("--exit-ma", type=int, choices=(13, 34, 55), default=13, help="收盘跌破该均线离场")
    add_risk_arguments(lv)
    lv.add_argument("--poll", type=float, default=15.0)
    lv.add_argument("--cash", type=float, default=10_000.0, help="dry-run 模拟资金")
    lv.add_argument("--once", action="store_true", help="只跑一轮")
    lv.add_argument("--live", action="store_true", help="真实下单（默认 dry-run）")
    lv.set_defaults(func=_cmd_live)

    ft = sub.add_parser("fetch", help="拉取 Binance K 线，检查连续性并写入 data/")
    ft.add_argument("--symbol", default="BTCUSDT")
    ft.add_argument("--interval", default="1d")
    ft.add_argument("--limit", type=int, default=2500)
    ft.add_argument("--kind", choices=("spot", "futures"), default="futures")
    ft.add_argument("--data-dir", default="data")
    ft.add_argument("--out", type=Path, help="自定义保存路径")
    ft.add_argument("--jump", type=float, default=0.25, help="单根涨跌超过该比例记为警告")
    ft.set_defaults(func=_cmd_fetch)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
