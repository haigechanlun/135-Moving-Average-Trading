# 135 均线战法（宁俊明）

基础 Python 量化仓库：13 / 34 / 55 日均线系统。行情用 **Binance**，实盘下单用 **Gate.io USDT 永续**，模块划分对齐 `haigechanlun`（`data/binance_api.py` + `trade/gate/gate_trade.py`）。

本仓库是教学与研究骨架，不是原书 55 种图解的完整复刻，也不构成投资建议。

## 模块

```
src/njm135/
  core/       基础核心：均线、形态、买卖信号（不碰交易所）
  market/     行情：Binance K 线、CSV、合成数据
  risk/       风控：止损、冷却、大均线过滤（回测和实盘共用）
  backtest/   回测：下一根开盘成交、净值图
  live/       实盘：Broker 协议、Gate 适配、轮询引擎
```

数据流：

1. `market` 拉 Binance 已完成 K 线
2. `core` 计算 135 形态与信号
3. `backtest` 离线回测，或 `live` 把信号交给 Gate

## 原理

「135」取自斐波那契 **13、34、55** 的首位数字。

| 均线 | 角色 |
|------|------|
| MA13 | 短期强弱；有效跌破倾向离场 |
| MA34 | 承上启下；上穿 55 为「均线互换」 |
| MA55 | 中期趋势与多空分界 |

默认 SMA，突破一律 **收盘确认**。阈值集中在 `PatternParams`（走平斜率、靠近均线的百分比/ATR、放量缩量窗口、长期下跌/高位回看周期）。

### 13 种经典形态

| 阶段 | 形态 | 量化要点 | 默认角色 |
|------|------|----------|----------|
| 底部 | 红杏出墙 | 空头排列，13走平或勾头，收盘上穿13 | 买（默认） |
| 底部 | 蚂蚁上树 | 均线粘合，连续小阳上55 | 买（默认） |
| 启动 | 黑客点击 | 上破55后缩量回踩13/55结点 | 买（默认） |
| 启动 | 红衣侠女 | 13金叉55 + 放量阳线 | 标注 |
| 拉升 | 海底捞月 | 13下穿中长期线后再金叉55 | 标注 |
| 拉升 | 均线互换 | 34由下上穿55 | 买（默认） |
| 拉升 | 三线推进 | 三线收敛后同步向上 | 标注 |
| 拉升 | 梅开二度 | 13死叉34后再金叉34 | 买（默认） |
| 整理 | 走四方 | 上涨中围绕13横向整理 | 观察 |
| 整理 | 浪子回头 | 连阴回踩55后收阳转强 | 标注 |
| 顶部 | 一枝独秀 | 高位脱离13的长上影阳 | 标注 |
| 顶部 | 独上高楼 | 高位跳空高开收阴 | 标注 |
| 顶部 | 见好就收 | 13/55 乖离>10% 且 DIF 拐头向下 | 标注 |

默认策略只交易定义最清楚的 8 类：**买**红杏出墙 / 蚂蚁上树 / 黑客点击 / 均线互换 / 梅开二度 / 一阳穿三线；**卖**一阴破三线 / 一箭穿心（另加分道扬镳、跌破 MA13）。同一根 K 线既买又卖时 **卖优先**。

「跌破均线」是**状态**（收盘在均线下方的每一根都算），不是「向下穿越的那一根」。用穿越会漏掉在均线下方建仓的情形（黑客点击回踩就可能如此），那种持仓会一直等不到离场条件。离场均线可切换：`--exit-ma 13|34|55`，默认 13 最贴原书，34/55 拿得更久。

蚂蚁上树在 BTC 日线上一次都不触发（连续 5 根小阳 + 均线粘合 <3% 太严），目前等于没启用。

回测与实盘都是：已收盘 K 线出信号，下一根开盘附近成交。CLI 默认仓位比例 `--position-pct 0.3`。`--limit` 会向前翻页，超过 1000 根时会多次请求。

回测摘要会打印年化、同期买持、夏普、索提诺、卡尔玛、最大回撤（及最长回撤天数）、盈亏比、平均盈亏与平均持仓。夏普按权益日收益、无风险利率 0、加密 24/7（由 K 线间隔推算每年根数）年化。

图分三栏：价格（对数轴，黄色底为持仓期，大三角是**真实成交**，小点是信号）、净值对比买入持有、回撤曲线。注意信号 ≠ 成交：已持仓时的买信号会被忽略。

BTCUSDT 日线 2019-11~2026-09、满仓、手续费 0.1%：

| 离场线 | 笔数 | 胜率 | 累计 | 年化 | 夏普 | 最大回撤 | PF |
|--------|------|------|------|------|------|----------|-----|
| MA13（默认） | 52 | 42.3% | 204% | 17.7% | 0.83 | -41.0% | 2.52 |
| MA34 | 32 | 46.9% | 1036% | 42.7% | 1.28 | -44.3% | 5.75 |
| 买入持有 | — | — | 754% | — | — | -77% | — |

4h / 1h 上无论哪条离场线都是亏的（信号过密），日线才有意义。

### 持仓状态离场

形态信号是无状态的，表达不了「相对进场价」这类规则，所以独立包 `njm135.risk` 管理 `RiskConfig` 与有状态的 `RiskManager`。回测引擎和实盘轮询共用同一套判定。

```bash
python -m njm135 backtest --csv data/BTCUSDT_futures_1d.csv --exit-ma 55 --trailing 0.10
```

- `--stop-loss 0.08` 固定止损（相对进场价）
- `--trailing 0.10` 移动止损（相对持仓期最高收盘）
- `--atr-stop 3` ATR 跟踪止损
- `--loss-streak 2 --cooldown-bars 30` 连亏 2 笔后冷却 30 根
- `--regime-ma 100` 收盘低于 MA100 时停止新开多，重新站上后恢复

冷却与 MA100 是**开仓过滤**，不会强制平掉已有仓位。例如：

```bash
python -m njm135 backtest --csv data/BTCUSDT_futures_1d.csv \
  --position-pct 1 --exit-ma 55 --loss-streak 2 --cooldown-bars 30

python -m njm135 backtest --csv data/BTCUSDT_futures_4h.csv \
  --position-pct 1 --exit-ma 55 --loss-streak 2 --cooldown-bars 30 --regime-ma 100
```

一律在**已收盘** K 线上判定、下一根开盘成交，和实盘轮询已收盘 K 线的行为一致；不假设交易所挂着止损单，所以不会出现盘中被精确打在止损价上的乐观成交。成交记录多一列 `exit_reason`（signal / stop / trail / atr），摘要里也会给出分布。

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

实盘再装 Gate SDK：

```bash
pip install -e ".[dev,live]"
```

## 回测（Binance）

```bash
python -m njm135 backtest --symbol BTCUSDT --interval 1d --kind futures --limit 1500 --position-pct 0.3

python -m njm135 backtest --csv data/BTCUSDT_futures_1d.csv --position-pct 1 --exit-ma 55
```

现货：`--kind spot`。离线：`--demo` 或 `--csv klines.csv`。

拉取并检查 K 线（默认写入 `data/`）：

```bash
python -m njm135 fetch --symbol BTCUSDT --interval 1d --kind futures --limit 2500
```

## 实盘（Binance 信号 + Gate 下单）

默认走内存模拟仓（会记账，不会打到 Gate）：

```bash
export GATE_API_KEY=...
export GATE_API_SECRET=...
python -m njm135 live --symbol BTCUSDT --interval 15m --once \
  --exit-ma 55 --loss-streak 2 --cooldown-bars 30 --regime-ma 100
```

真实下单必须加 `--live`：

```bash
python -m njm135 live --symbol BTCUSDT --interval 15m --live --position-pct 0.3
```

Binance 交易对写成 `BTCUSDT`，内部会转成 Gate 的 `BTC_USDT`。K 线走 Binance 公开接口，不需要 Binance Key。

## 测试

```bash
pytest
```
