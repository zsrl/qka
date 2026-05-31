---
name: qka
description: >
  QKA 框架使用技能。当用户需要基于 QKA 框架编写 A 股量化策略、运行回测、
  处理股票数据、生成报告时使用。涵盖 QKA 全部核心 API 的使用方法。
---

# QKA 框架技能

## 概述

QKA 是一个 A 股量化交易回测框架。核心流程：

```
Data(symbols) → Strategy(策略类) → Backtest(回测) → Report(报告)
                  ↑
          indicators(预计算指标)
```

**类名约束：** 自定义策略类必须命名为 `MyStrategy`，继承 `Strategy`

## 能力边界

**能做的策略类型：**
- 趋势跟踪（双均线、海龟突破、MACD）
- 均值回归（RSI、Bollinger Bands）
- 多因子选股（PE/ROE/动量/波动率打分选股，周期 rebalance）
- 等权/市值加权组合
- 定投（固定间隔买入固定金额）
- 大盘 MA 择时、股债轮动

**做不了的：**
- 分钟级/高频（无分钟数据）
- 期权、期货
- 机器学习选股（无特征工程管道）
- 实盘交易
- 事件驱动（无财报/公告订阅）
- 多周期策略（仅单周期）

## A 股交易规则

1. 买入股数必须是 100 的整数倍（一手）
2. 价格必须 > 0 且不是 NaN
3. 资金不足时不买入
4. `sizing.percent()` 和 `sizing.fixed()` 已自动按手取整

---

<!-- AUTO: API 签名 -->

### Data

### `Data(**symbols** \`Optional[List[str]]\` = None, **period** \`str\` = '1d', **adjust** \`str\` = 'qfq', **source** \`str\` = 'baostock', **pool_size** \`int\` = 10, **datadir** \`Optional[Path]\` = None, **indicators** \`Optional[dict]\` = None)\`

    初始化数据对象

### `Data.get(**lazy** \`bool\` = False) → \`lazy=False: pd.DataFrame，列名格式 {symbol}|{factor}\`\`

    获取历史数据。 并发下载所有股票数据，应用因子计算，并返回合并后的数据。

<!-- /AUTO -->

# Data 模块

数据获取、缓存和指标预计算。

## Data 构造函数

```python
from qka import Data

data = Data(
    symbols=['000001.SZ', '600000.SH'],  # 股票代码
    period='1d',                          # 周期：'1d'
    adjust='qfq',                         # 复权：'qfq'/'hfq'/'bfq'
    source='baostock',                    # 数据源：'baostock'/'akshare'/'qmt'
    pool_size=10,                         # 并发线程数（仅 akshare）
    datadir=None,                         # 缓存目录，默认 ./datadir
    indicators=None,                      # 预计算指标
)
```

- `symbols`: A 股代码 `000001.SZ`（深市）或 `600000.SH`（沪市）
- `period`: 目前仅支持 `'1d'`（日线）
- `adjust`: `'qfq'`（前复权，默认）、`'hfq'`（后复权）、`'bfq'`（不复权）
- `source`: `'baostock'`（默认，串行下载）、`'akshare'`（HTTP 并发）、`'qmt'`（QMT）
- `datadir`: 默认当前目录的 `datadir/`，缓存 parquet 文件

## indicators 参数

两种格式：

### 格式一：字典（推荐）

```python
data = Data(symbols=['000001.SZ'], indicators={
    'sma_5': ('sma', 5),                   # (指标名, 参数...)
    'sma_20': ('sma', 20),                 # 默认用 close 计算
    'rsi_14': ('rsi', 14),
    'macd': ('macd', 12, 26, 9),
    'bbands': ('bbands', 20, 2),
    'atr_14': ('atr', 14),
    'ma5_custom': lambda df: df['close'].rolling(5).mean(),  # 自定义因子
    'sma_on_high': ('sma', 'high', 20),    # 指定用 high 列计算
})
```

支持的 TA 指标名：`sma`, `ema`, `wma`, `rsi`, `macd`, `bbands`, `atr`

- `macd` 产生 3 列：`macd`, `macd_signal`, `macd_diff`
- `bbands` 产生 3 列：`bbands_upper`, `bbands_middle`, `bbands_lower`

### 格式二：函数

```python
data = Data(symbols=['000001.SZ'], indicators=lambda df:
    df.assign(
        ma5=df['close'].rolling(5).mean(),
        ma20=df['close'].rolling(20).mean()
    )
)
```

函数接收单只股票的 DataFrame，返回添加了额外列的 DataFrame。

## 获取数据

```python
data = Data(symbols=['000001.SZ', '600000.SH'], indicators={'sma_5': ('sma', 5)})

# 下载并返回全部数据（触发下载）
df = data.get()

# 懒加载模式（大数据用 dask，分块迭代）
ddf = data.get(lazy=True)
```

- `get()` 返回 `pd.DataFrame`，列名格式 `{symbol}|{factor}`
- 示例列名：`000001.SZ|close`, `000001.SZ|sma_5`, `600000.SH|volume`
- `get(lazy=True)` 返回 `dask.DataFrame`，计算前操作延迟执行

## 常见错误

```python
# ✅ 正确：传 indicators 到 Data 构造函数
Data(symbols=['000001.SZ'], indicators={'sma_5': ('sma', 5)})

# ❌ 错误：Data() 后不能动态加指标
data = Data(['000001.SZ'])
data.indicators = {...}  # 没用
```

---

<!-- AUTO: API 签名 -->

### Strategy

### `Strategy(**cash** \`float\` = 100000.0)\`

    初始化策略

### `Strategy.get(**factor** \`str\`) → \`pd.Series，index=股票代码，values=最新值\`\`

    获取当前 bar 的横截面数据。 替代旧的 on_bar(date, get) 中的 get 参数。 仅当 on_bar 通过 self._data 注入数据后才能使用。

### `Strategy.history(**factor** \`str\`, **window** \`int\` = 20) → \`pd.DataFrame，行=日期，列=股票代码\`\`

    获取因子的历史窗口数据。

### `Strategy.on_bar(**date**)\`

    每个 bar 的处理逻辑，必须由子类实现。 使用 self.get(factor) / self.history(factor, window) 获取数据。 --- 用法 --- class MyStrategy(Strategy): def on_bar(self, date): # 横截面数据（当前 bar 所有股票） close = self.get('close') # 历史序列（过去 N...

<!-- /AUTO -->

# Strategy 模块

策略编写核心。

## 策略类结构

```python
from qka import Strategy

class MyStrategy(Strategy):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 初始化自定义状态（可选）
        # 不写 __init__ 也行，用父类默认值

    def on_bar(self, date):
        """每个交易日回调一次"""
        # date: pd.Timestamp
        # self.get() / self.history() 获取数据
        # self.broker 交易
        # self.sizing 计算仓位
        pass
```

**规则：**
- 类名必须是 `MyStrategy`
- `__init__` 必须用 `**kwargs` 透传，不能固定参数
- ❌ 禁止写 `on_bar(self, date, get)`——没有 `get` 参数

## self.get(factor) -> pd.Series

当前 bar 所有股票的横截面数据。

```python
close = self.get('close')           # 所有股票的收盘价
volume = self.get('volume')         # 成交量
high = self.get('high')             # 最高价

for sym in close.index:             # 遍历股票
    price = float(close[sym])
    if price > 0:
        ...
```

- `factor`: 因子名，如 `'close'`, `'open'`, `'high'`, `'low'`, `'volume'`
- 也可以取预计算指标：`self.get('sma_5')`, `self.get('rsi_14')`
- 返回 `pd.Series`, index=股票代码
- 如果某股票当前值缺失，会从 Series 中排除

```python
# ✅ 正确用法
close = self.get('close')
for sym in close.index:
    ...

# ❌ 错误用法
self.get('close', count=20)  # 没有 count 参数
get('close')                  # get 不是全局函数
```

## self.history(factor, window) -> pd.DataFrame

因子的历史窗口数据。

```python
hist = self.history('close', 20)        # 过去 20 天收盘价
ma5 = hist.iloc[-5:].mean()             # 最近 5 天均值，Series(index=股票代码)
today_close = hist.iloc[-1]             # 今天收盘价
yesterday_close = hist.iloc[-2]         # 昨天收盘价
series = hist[sym].dropna()             # 某只股票的历史序列
```

- 返回 `pd.DataFrame`, 行=日期（倒序）, 列=股票代码
- 如果 `history` 的数据不够 `window` 天，前几行会有 NaN
- **用 `.dropna()` 清理后再计算**
- `hist.iloc[-N:]` 取最近 N 天

## self.broker

交易接口。详见下方 Broker 模块。

```python
self.broker.buy('000001.SZ', price, 100)    # 买入 100 股
self.broker.sell('000001.SZ', price, 100)   # 卖出 100 股
```

## self.sizing

仓位计算。详见下方 Sizing 模块。

```python
# 10% 资金买入，自动按手取整
size = self.sizing.percent(0.1, price)
self.broker.buy(sym, price, size)
```

---

<!-- AUTO: API 签名 -->

### Broker

### `Broker(**initial_cash** = 100000.0, **commission_rate** = DEFAULT_COMMISSION_RATE, **stamp_duty_rate** = DEFAULT_STAMP_DUTY_RATE, **slippage** = DEFAULT_SLIPPAGE)\`

    初始化Broker

### `Broker.on_bar(**date**, **get**)\`

    Bar结束时记录当前状态。

### `Broker.buy(**symbol** \`str\`, **price** \`float\`, **size** \`int\`) → \`bool\`\`

    买入操作 考虑滑点（买入价上移）和佣金（最低 5 元）。

### `Broker.sell(**symbol** \`str\`, **price** \`float\`, **size** \`int\`) → \`bool\`\`

    卖出操作 考虑滑点（卖出价下移）、佣金（最低 5 元）和印花税。

### `Broker.get(**factor** \`str\`, **timestamp** = None) → \`Any\`\`

    从trades DataFrame中获取数据

<!-- /AUTO -->

# Broker 模块

虚拟交易经纪商，管理资金、持仓和费用。

## 初始化

Broker 由 Strategy 自动创建，用户在策略中通过 `self.broker` 访问。

```python
# Strategy 内部自动创建
strategy = MyStrategy(cash=100000)  # 初始资金 10 万
```

## 交易接口

```python
# 买入
self.broker.buy(symbol, price, size)
# symbol: 股票代码，如 '000001.SZ'
# price: 成交价（float）
# size: 股数（int，必须 100 的倍数）

# 卖出
self.broker.sell(symbol, price, size)
```

## 状态属性

```python
self.broker.cash          # 可用资金（float）
self.broker.positions     # 持仓 dict

# 持仓格式：
# {symbol: {'size': int, 'avg_price': float, 'cost': float}}

symbol in self.broker.positions  # 判断是否持仓
```

## 费用设置

```python
from qka import Broker

broker = Broker(
    initial_cash=100000,
    commission_rate=0.00025,   # 万2.5 佣金（默认）
    stamp_duty_rate=0.0005,    # 万5 印花税，仅卖出（默认）
    slippage=0.001,            # 0.1% 滑点（默认）
)
```

- 最低佣金 5 元
- 印花税仅卖出时收取

## 回测结果数据

回测执行后，以下属性保存完整记录：

### self.broker.trades — 逐日净值记录（pd.DataFrame）

```python
equity = self.broker.trades['total']     # 净值序列（Series, index=日期）
cash   = self.broker.trades['cash']      # 现金
value  = self.broker.trades['value']     # 持仓市值
```

用于构造净值曲线：

```python
import pandas as pd
eq = pd.Series(self.broker.trades['total'].values, 
               index=self.broker.trades.index)
```

### self.broker.trade_history — 逐笔交易记录（list[dict]）

每笔 dict 的字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `action` | str | `'buy'` 或 `'sell'` |
| `symbol` | str | 股票代码 |
| `price` | float | 市价 |
| `exec_price` | float | 滑点后成交价 |
| `size` | int | 股数 |
| `amount` | float | 成交金额 |
| `commission` | float | 佣金 |
| `timestamp` | 时间戳 | 交易日期 |

卖出额外含 `net_proceeds`（扣除费用后净收入）。

## 正确/错误用法

```python
# ✅ 正确
if '000001.SZ' in self.broker.positions:
    size = self.broker.positions['000001.SZ']['size']
    self.broker.sell('000001.SZ', price, size)

# ❌ 错误：直接修改内部状态
self.broker.cash -= 1000
self.broker.positions['000001.SZ'] = {'size': 100, ...}
```

---

<!-- AUTO: API 签名 -->

### SizingAccessor

### `SizingAccessor(**broker**)\`
### `SizingAccessor.fixed_shares(**n** \`int\`) → \`int\`\`

    固定股数。 如果 n 不足一手（100股），返回 0。

### `SizingAccessor.fixed_amount(**amount** \`float\`, **price** \`float\`) → \`int\`\`

    固定金额。 计算 amount 能买多少股，向下按手取整。

### `SizingAccessor.percent(**ratio** \`float\`, **price** \`float\`) → \`int\`\`

    资金百分比。 使用可用现金的 ratio 比例买入，按手取整。

### `SizingAccessor.atr_risk(**risk_ratio** \`float\`, **price** \`float\`, **atr_value** \`float\`, **multiplier** \`float\` = 2.0) → \`int\`\`

    ATR 风险仓位。 基于 ATR（平均真实波幅）计算仓位，确保单笔亏损不超过 risk_ratio 比例。 公式：股数 = (cash * risk_ratio) / (atr_value * multiplier)

### `SizingAccessor.kelly(**win_rate** \`float\`, **win_loss_ratio** \`float\`, **price** \`float\`) → \`int\`\`

    凯利公式。 f* = (p * b - q) / b 其中： - p = 胜率 - b = 赔率（盈利/亏损） - q = 1 - p（败率） 当 f* ≤ 0 时返回 0（不建议下注）。

<!-- /AUTO -->

# Sizing 模块

仓位计算工具。在策略中通过 `self.sizing` 访问。

## 方法

### self.sizing.percent(ratio, price) -> int

按可用资金的百分比计算买入股数，自动向下取整到 100 的倍数。

```python
# 用 10%（10000 元）资金买入
price = float(self.get('close')['000001.SZ'])
size = self.sizing.percent(0.1, price)
self.broker.buy('000001.SZ', price, size)
```

- `ratio`: 资金比例，如 `0.1` = 10%, `0.5` = 50%
- `price`: 当前价格
- 返回：股数（int），已按手取整
- 如果计算出的股数 < 100，返回 0

### self.sizing.fixed_shares(n) -> int

买入固定股数。

```python
size = self.sizing.fixed_shares(1000)     # 买入 1000 股
self.broker.buy('000001.SZ', price, size)
```

### self.sizing.fixed_amount(amount, price) -> int

买入固定金额。

```python
size = self.sizing.fixed_amount(5000, price)  # 投入 5000 元
self.broker.buy('000001.SZ', price, size)
```

## 注意事项

```python
# ✅ 正确：先算仓位再买入
price = float(self.get('close')['000001.SZ'])
size = self.sizing.percent(0.1, price)
if size >= 100:
    self.broker.buy(sym, price, size)

# ❌ 错误：不校验 size 直接买
self.broker.buy(sym, price, self.sizing.percent(0.1, price))
# 如果 percent 返回 0，buy 会报错
```

---

<!-- AUTO: API 签名 -->

### Backtest

### `Backtest(**data**, **strategy**)\`

    初始化回测引擎

### `Backtest.run(**benchmark** \`Optional[str]\` = None) → \`None。回测结果保存在 self.results 中，可通过\`\`

    执行回测 遍历所有时间点，在每个时间点调用策略的on_bar方法进行交易决策， 并记录交易后的状态。 大规模回测（>500 bar）时自动使用分区迭代，分块加载数据到内存， 避免一次性加载全量数据。

### `Backtest.summary() → \`dict\`\`

    计算并打印回测绩效指标 返回包含以下指标的字典： - 总收益率、年化收益率、年化波动率 - 夏普比率、最大回撤、Calmar比率 - 胜率、盈亏比、交易次数 - 最终资产、总手续费

<!-- /AUTO -->

# Backtest 模块

回测引擎，管理策略生命周期和数据加载流程。

## 用法

```python
from qka import Data, Backtest

data = Data(symbols=['000001.SZ'], indicators={'sma_5': ('sma', 5)})
bt = Backtest(data, MyStrategy(cash=100000))
bt.run(benchmark='000300.SH')   # 沪深300 为基准
```

- `data`: Data 实例（已配置 symbol 和 indicators）
- `MyStrategy(cash=...)`: 策略实例，cash 为初始资金
- `benchmark`: 基准指数代码，如 `'000300.SH'`（沪深300）、`'000001.SH'`（上证）

## Backtest 参数

```python
bt = Backtest(
    data,                         # Data 实例
    strategy,                     # Strategy 实例
    start_date='2023-01-01',      # 可选，数据过滤起始
    end_date='2024-12-31',        # 可选，数据过滤结束
)
```

## 回测结果

### summary() -> dict

```python
metrics = bt.summary()
```

返回的字典包含：
- `总收益率` — 策略总收益百分比
- `年化收益率` — 年化收益率
- `最大回撤` — 最大回撤百分比（负值）
- `夏普比率` — 年化夏普比率
- `胜率` — 盈利交易占比
- `交易次数` — 总交易笔数
- `benchmark_收益` — 基准总收益百分比
- `benchmark_年化` — 基准年化收益率

## 完整回测流程

```python
from qka import Data, Strategy, Backtest

class MyStrategy(Strategy):
    def on_bar(self, date):
        close = self.get('close')
        for sym in close.index:
            price = float(close[sym])
            if price <= 0:
                continue
            if sym not in self.broker.positions:
                size = self.sizing.percent(0.1, price)
                if size >= 100:
                    self.broker.buy(sym, price, size)

data = Data(symbols=['000001.SZ', '600000.SH'])
bt = Backtest(data, MyStrategy(cash=100000))
bt.run(benchmark='000300.SH')
print(bt.summary())
```

---
