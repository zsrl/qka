# QKA 框架

## 架构

| 类 | 作用 |
|-----|------|
| `qka.Data` | 行情数据加载 + 技术指标计算 |
| `qka.Strategy` | 策略基类 — 实现 `on_bar` 做交易决策 |
| `qka.Backtest` | 回测引擎 — 串联 Data 和 Strategy，注入基础设施 |

---

## Data

数据获取和指标预计算。

### 构造

创建一个数据对象，配置数据源、股票代码和预计算指标。此时数据尚未下载，调用 `get()` 时才真正获取。

```python
from qka import Data

data = Data(
    symbols=['000001.SZ', '600000.SH'],
    period='1d',
    adjust='qfq',
    indicators=None,
)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `symbols` | `list[str]` | `None` | A 股代码，深市 `000001.SZ`，沪市 `600000.SH` |
| `period` | `str` | `'1d'` | 数据周期，当前仅支持 `'1d'` |
| `adjust` | `str` | `'qfq'` | 复权方式：`'qfq'` 前复权，`'hfq'` 后复权，`'bfq'` 不复权 |
| `indicators` | `dict` | `None` | 预计算指标，见下方 |

### indicators

在构造 `Data` 时传入，利用数据加载过程一次性预计算所有指标。**不能**在构造后补充。

#### 内置指标

直接透传 [ta](https://github.com/bukosabino/ta) 库的全部指标函数，格式为：`{'列名': ('ta.路径.函数名', '计算列', 参数...)}`。每个条目独立产一列，第二个参数固定为计算列名（不设默认值）。

```python
data = Data(
    symbols=['000001.SZ'],
    indicators={
        'sma_5':       ('ta.trend.sma_indicator', 'close', 5),
        'sma_20':      ('ta.trend.sma_indicator', 'close', 20),
        'ema_20':      ('ta.trend.ema_indicator', 'close', 20),
        'rsi_14':      ('ta.momentum.rsi', 'close', 14),
        'macd_line':   ('ta.trend.macd', 'close', 26, 12),
        'macd_signal': ('ta.trend.macd_signal', 'close', 26, 12, 9),
        'macd_hist':   ('ta.trend.macd_diff', 'close', 26, 12, 9),
        'bb_upper':    ('ta.volatility.bollinger_hband', 'close', 20, 2),
        'bb_middle':   ('ta.volatility.bollinger_mavg', 'close', 20),
        'bb_lower':    ('ta.volatility.bollinger_lband', 'close', 20, 2),
        'atr_14':      ('ta.volatility.average_true_range', 'high', 'low', 'close', 14),
        'adx_14':      ('ta.trend.adx', 'high', 'low', 'close', 14),
    },
)
```

- `spec[0]`: ta 函数完整路径
- `spec[1]`: 计算列名（`'close'`/`'high'`/`'low'`/`'open'`/`'volume'`）
- `spec[2:]`: 原样传给该函数

可用的 ta 函数：

#### trend

| 签名 | 说明 |
|------|------|
| `ta.trend.adx(high, low, close, window=14)` | 平均趋向指数 |
| `ta.trend.adx_neg(high, low, close, window=14)` | ADX 负向指标 |
| `ta.trend.adx_pos(high, low, close, window=14)` | ADX 正向指标 |
| `ta.trend.aroon_down(high, low, window=25)` | Aroon 下轨 |
| `ta.trend.aroon_up(high, low, window=25)` | Aroon 上轨 |
| `ta.trend.cci(high, low, close, window=20, constant=0.015)` | 商品通道指数 |
| `ta.trend.dpo(close, window=20)` | 去趋势价格振荡器 |
| `ta.trend.ema_indicator(close, window=12)` | 指数移动平均 |
| `ta.trend.ichimoku_a(high, low, window1=9, window2=26, visual=False)` | 一目均衡表 A 线（先行带） |
| `ta.trend.ichimoku_b(high, low, window2=26, window3=52, visual=False)` | 一目均衡表 B 线（先行带） |
| `ta.trend.ichimoku_base_line(high, low, window1=9, window2=26, visual=False)` | 一目均衡表基准线 |
| `ta.trend.ichimoku_conversion_line(high, low, window1=9, window2=26, visual=False)` | 一目均衡表转换线 |
| `ta.trend.kst(close, roc1=10, roc2=15, roc3=20, roc4=30, window1=10, window2=10, window3=10, window4=15)` | 确然指标（KST） |
| `ta.trend.kst_sig(close, roc1=10, roc2=15, roc3=20, roc4=30, window1=10, window2=10, window3=10, window4=15, nsig=9)` | KST 信号线 |
| `ta.trend.macd(close, window_slow=26, window_fast=12)` | MACD 线（DIF） |
| `ta.trend.macd_diff(close, window_slow=26, window_fast=12, window_sign=9)` | MACD 柱（HIST） |
| `ta.trend.macd_signal(close, window_slow=26, window_fast=12, window_sign=9)` | MACD 信号线（DEA） |
| `ta.trend.mass_index(high, low, window_fast=9, window_slow=25)` | 质量指数 |
| `ta.trend.psar_down(high, low, close, step=0.02, max_step=0.2)` | 抛物线 SAR（下方） |
| `ta.trend.psar_down_indicator(high, low, close, step=0.02, max_step=0.2)` | 抛物线 SAR 下方指示 |
| `ta.trend.psar_up(high, low, close, step=0.02, max_step=0.2)` | 抛物线 SAR（上方） |
| `ta.trend.psar_up_indicator(high, low, close, step=0.02, max_step=0.2)` | 抛物线 SAR 上方指示 |
| `ta.trend.sma_indicator(close, window=12)` | 简单移动平均 |
| `ta.trend.stc(close, window_slow=50, window_fast=23, cycle=10, smooth1=3, smooth2=3)` | 沙夫趋势周期 |
| `ta.trend.trix(close, window=15)` | 三重指数平滑平均线 |
| `ta.trend.vortex_indicator_neg(high, low, close, window=14)` | 漩涡指标负向 |
| `ta.trend.vortex_indicator_pos(high, low, close, window=14)` | 漩涡指标正向 |
| `ta.trend.wma_indicator(close, window=9)` | 加权移动平均 |

#### momentum

| 签名 | 说明 |
|------|------|
| `ta.momentum.awesome_oscillator(high, low, window1=5, window2=34)` | 动量振荡器 |
| `ta.momentum.kama(close, window=10, pow1=2, pow2=30)` | 考夫曼自适应移动平均 |
| `ta.momentum.ppo(close, window_slow=26, window_fast=12, window_sign=9)` | 价格百分比振荡器 |
| `ta.momentum.ppo_hist(close, window_slow=26, window_fast=12, window_sign=9)` | PPO 柱 |
| `ta.momentum.ppo_signal(close, window_slow=26, window_fast=12, window_sign=9)` | PPO 信号线 |
| `ta.momentum.pvo(volume, window_slow=26, window_fast=12, window_sign=9)` | 成交量百分比振荡器 |
| `ta.momentum.pvo_hist(volume, window_slow=26, window_fast=12, window_sign=9)` | PVO 柱 |
| `ta.momentum.pvo_signal(volume, window_slow=26, window_fast=12, window_sign=9)` | PVO 信号线 |
| `ta.momentum.roc(close, window=12)` | 变动率 |
| `ta.momentum.rsi(close, window=14)` | 相对强弱指数 |
| `ta.momentum.stoch(high, low, close, window=14, smooth_window=3)` | 随机指标 %K |
| `ta.momentum.stoch_signal(high, low, close, window=14, smooth_window=3)` | 随机指标 %D |
| `ta.momentum.stochrsi(close, window=14, smooth1=3, smooth2=3)` | 随机 RSI |
| `ta.momentum.stochrsi_d(close, window=14, smooth1=3, smooth2=3)` | 随机 RSI %D |
| `ta.momentum.stochrsi_k(close, window=14, smooth1=3, smooth2=3)` | 随机 RSI %K |
| `ta.momentum.tsi(close, window_slow=25, window_fast=13)` | 真实强度指数 |
| `ta.momentum.ultimate_oscillator(high, low, close, window1=7, window2=14, window3=28, weight1=4.0, weight2=2.0, weight3=1.0)` | 终极振荡器 |
| `ta.momentum.williams_r(high, low, close, lbp=14)` | 威廉指标 |

#### volatility

| 签名 | 说明 |
|------|------|
| `ta.volatility.average_true_range(high, low, close, window=14)` | 平均真实波幅 |
| `ta.volatility.bollinger_hband(close, window=20, window_dev=2)` | 布林带上轨 |
| `ta.volatility.bollinger_hband_indicator(close, window=20, window_dev=2)` | 布林带上轨指示 |
| `ta.volatility.bollinger_lband(close, window=20, window_dev=2)` | 布林带下轨 |
| `ta.volatility.bollinger_lband_indicator(close, window=20, window_dev=2)` | 布林带下轨指示 |
| `ta.volatility.bollinger_mavg(close, window=20)` | 布林带中轨 |
| `ta.volatility.bollinger_pband(close, window=20, window_dev=2)` | 布林带 %B |
| `ta.volatility.bollinger_wband(close, window=20, window_dev=2)` | 布林带带宽 |
| `ta.volatility.donchian_channel_hband(high, low, close, window=20, offset=0)` | 唐奇安通道上轨 |
| `ta.volatility.donchian_channel_lband(high, low, close, window=20, offset=0)` | 唐奇安通道下轨 |
| `ta.volatility.donchian_channel_mband(high, low, close, window=10, offset=0)` | 唐奇安通道中轨 |
| `ta.volatility.donchian_channel_pband(high, low, close, window=10, offset=0)` | 唐奇安通道 %B |
| `ta.volatility.donchian_channel_wband(high, low, close, window=10, offset=0)` | 唐奇安通道带宽 |
| `ta.volatility.keltner_channel_hband(high, low, close, window=20, window_atr=10, original_version=True)` | 肯特纳通道上轨 |
| `ta.volatility.keltner_channel_hband_indicator(high, low, close, window=20, window_atr=10, original_version=True)` | 肯特纳通道上轨指示 |
| `ta.volatility.keltner_channel_lband(high, low, close, window=20, window_atr=10, original_version=True)` | 肯特纳通道下轨 |
| `ta.volatility.keltner_channel_lband_indicator(high, low, close, window=20, window_atr=10, original_version=True)` | 肯特纳通道下轨指示 |
| `ta.volatility.keltner_channel_mband(high, low, close, window=20, window_atr=10, original_version=True)` | 肯特纳通道中轨 |
| `ta.volatility.keltner_channel_pband(high, low, close, window=20, window_atr=10, original_version=True)` | 肯特纳通道 %B |
| `ta.volatility.keltner_channel_wband(high, low, close, window=20, window_atr=10, original_version=True)` | 肯特纳通道带宽 |
| `ta.volatility.ulcer_index(close, window=14)` | 溃疡指数 |

#### 自定义指标

非 ta 库的自定义因子用 callable：

```python
indicators={
    'ma5': lambda df: df['close'].rolling(5).mean(),
}
```

函数接收单只股票的 DataFrame（含 `open/high/low/close/volume`），返回添加了新列的 DataFrame。

### get()

`get(lazy=False, start_date=None, end_date=None) → pd.DataFrame`

调用后触发数据下载和指标计算，返回合并后的宽表。`Backtest.run()` 内部会调用它。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `lazy` | `bool` | `False` | 返回 `dask.DataFrame` 而非 `pd.DataFrame` |
| `start_date` | `str` | `None` | 起始日期 `'YYYY-MM-DD'`。有指标时自动向后扩展窗口确保预热数据充足 |
| `end_date` | `str` | `None` | 截止日期 `'YYYY-MM-DD'` |

```python
df = data.get()
df = data.get(start_date='2024-01-01', end_date='2024-12-31')
```

| 属性 | 说明 |
|------|------|
| 类型 | `pd.DataFrame`（`lazy=True` 时返回 `dask.DataFrame`） |
| 索引 | 日期索引，**索引名为 `"date"`**。`reset_index()` 后日期列名也是 `"date"` |
| 列名 | `{symbol}|{factor}` — 例如 `000001.SZ|close`、`000001.SZ|sma_5`、`600000.SH|volume` |
| 列值 | 全部为 `float64`，指标列的早期行可能含 `NaN` |
| 异常 | 无数据时抛出 `RuntimeError` |

```python
# 列名格式：{symbol}|{factor}
df.columns  # ['000001.SZ|open', '000001.SZ|close', '000001.SZ|sma_5',
            #  '600000.SH|open', '600000.SH|close', ...]

# 索引名为 "date"，reset_index 后转为 pd.Timestamp 列
df = df.reset_index()
df['date'].iloc[0]          # Timestamp('2024-01-02 00:00:00')

# 输出 JSON 前需转为字符串
df['date'] = df['date'].dt.strftime('%Y-%m-%d')
df['date'].iloc[0]          # '2024-01-02'
```

---

## Strategy

策略基类。所有交易策略必须继承 `qka.Strategy`，实现 `on_bar` 方法。

`broker` / `sizing` / `_data` 由 `Backtest.run()` 在执行时注入，策略 `__init__` 不需要创建它们。

### 构造

```python
from qka import Strategy

class MyStrategy(Strategy):
    def __init__(self):
        super().__init__()
        # 在这里定义自己的参数
        self.lookback = 20

    def on_bar(self, date):
        ...
```

| 约束 | 说明 |
|------|------|
| `__init__` | **必须**调用 `super().__init__()`。不需要传任何参数 |
| `on_bar` 签名 | 只有 `self` 和 `date`。**没有** `get` 参数（旧版 API，已废弃） |
| `self.params` | **不存在**。不要写 `self.params.get('fast', 5)`，直接用实例属性 |

`Backtest.run()` 在执行时注入以下属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| `self.broker` | `Broker` | 虚拟券商，执行买卖、管理资金和持仓 |
| `self.sizing` | `SizingAccessor` | 仓位计算，`self.sizing.percent(0.1, price)` |
| `self._data` | `DataAccessor` | 私有，供 `self.get()` / `self.history()` 使用，勿直接访问 |

### self.get()

`get(factor: str) → pd.Series`

获取当前 bar 的横截面数据。**只能在 `on_bar` 内调用**。

```python
close = self.get('close')   # pd.Series，index=股票代码，value=当前价格
high  = self.get('high')
sma5  = self.get('sma_5')   # indicators 中定义的指标列
```

| 属性 | 说明 |
|------|------|
| 返回类型 | `pd.Series` |
| index | 股票代码，如 `'000001.SZ'`、`'600000.SH'` |
| values | 当前 bar 的最新值，`float` |
| 空值 | 无数据时返回空 `pd.Series`，不是 `None` |

```python
# 安全访问
if '000001.SZ' in close.index:
    price = float(close['000001.SZ'])
```

### self.history()

`history(factor: str, window: int = 20) → pd.DataFrame`

获取因子的历史窗口数据。

```python
hist = self.history('close', 20)  # 最近 20 天的收盘价
```

| 属性 | 说明 |
|------|------|
| 返回类型 | `pd.DataFrame` |
| 行 | 日期（`pd.Timestamp`），最近的在最后 |
| 列 | 股票代码 |
| 异常 | 因子不存在时返回空 DataFrame（有索引无列），不抛异常 |

### self.broker

虚拟券商，管理资金和持仓。提供 `buy` / `sell` 两个交易方法。

| 属性 | 说明 |
|------|------|
| `self.broker.cash` | 当前可用现金 |
| `self.broker.positions` | `{symbol: {'size': int, 'avg_price': float}}` |

#### buy

`buy(symbol: str, price: float, size: int) → bool`

买入，`size` 必须是 100 的整数倍（A 股 1 手 = 100 股）。

```python
success = self.broker.buy('000001.SZ', float(close['000001.SZ']), 100)
```

- 实际成交价 = `price * (1 + slippage)`（默认滑点 0.1%）
- 自动扣佣金（万 2.5，最低 5 元）
- 资金不足返回 `False`
- `price <= 0` 返回 `False`（前复权可能导致早期价格为负）

#### sell

`sell(symbol: str, price: float, size: int) → bool`

卖出，`size` 必须是 100 的整数倍。

```python
success = self.broker.sell('000001.SZ', float(close['000001.SZ']), 100)
```

- 自动扣佣金 + 印花税（万 5，仅卖出）
- 持仓不足返回 `False`

### self.sizing

仓位计算。**返回值已经是按手取整（100 的倍数）**。

| 方法 | 说明 |
|------|------|
| `percent(ratio, price)` | 用可用现金的 `ratio` 比例买入。`ratio` 在 0~1 之间 |
| `fixed_amount(amount, price)` | 固定金额买入 |
| `fixed_shares(n)` | 固定股数 |
| `atr_risk(risk_ratio, price, atr_value, multiplier=2.0)` | ATR 风险仓位 |

```python
price = float(close['000001.SZ'])
size = self.sizing.percent(0.1, price)  # 10% 仓位，已按手取整
if size > 0:
    self.broker.buy('000001.SZ', price, size)
```

### 完整示例

```python
from qka import Strategy

class MyStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.position_pct = 0.2   # 每次买入用 20% 仓位

    def on_bar(self, date):
        close = self.get('close')
        sma_fast = self.get('sma_5')
        sma_slow = self.get('sma_20')

        for symbol in close.index:
            price = float(close[symbol])
            if symbol not in sma_fast.index or symbol not in sma_slow.index:
                continue

            if sma_fast[symbol] > sma_slow[symbol]:
                size = self.sizing.percent(self.position_pct, price)
                if size > 0:
                    self.broker.buy(symbol, price, size)
            elif sma_fast[symbol] < sma_slow[symbol]:
                pos = self.broker.positions.get(symbol, {}).get('size', 0)
                if pos > 0:
                    self.broker.sell(symbol, price, pos)
```

---

## Backtest

回测引擎，串联 Data 和 Strategy。在执行时注入 broker/sizing/data。

### 构造

```python
from qka import Backtest

bt = Backtest(data, strategy)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `data` | `Data` | 数据对象 |
| `strategy` | `Strategy` | 策略对象 |

构造时不执行任何操作，只绑定引用。

### run()

`run(cash=100000.0, start_date=None, end_date=None, benchmark=None)`

执行回测。注入 broker/sizing/data 后遍历每个交易日，调用 `strategy.on_bar(date)`。

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `cash` | `100000.0` | 初始资金 |
| `start_date` | `None` | 回测起始日期 `'YYYY-MM-DD'` |
| `end_date` | `None` | 回测截止日期 |
| `benchmark` | `None` | 基准指数代码，如 `'000300.SH'` |

> 500 bar 以上自动分块迭代，避免一次性加载全量数据。

```python
bt.run(cash=200000, start_date='2024-01-01')
```

执行后可通过 `bt.results` 和 `bt.trade_history` 获取结果，详见下方。

### bt.metrics

`dict`，绩效指标，`run()` 结束时计算并缓存。

| 字段 | 类型 | 说明 |
|------|------|------|
| `initial_cash` | `float` | 初始资金 |
| `final_equity` | `float` | 最终资产 |
| `total_return_pct` | `float` | 总收益率（%） |
| `annual_return_pct` | `float` | 年化收益率（%） |
| `annual_volatility_pct` | `float` | 年化波动率（%） |
| `sharpe_ratio` | `float` | 夏普比率（无风险利率 3%） |
| `max_drawdown_pct` | `float` | 最大回撤（%） |
| `calmar_ratio` | `float` | Calmar 比率 |
| `total_trades` | `int` | 交易总次数 |
| `win_rate_pct` | `float` | 胜率（%） |
| `profit_loss_ratio` | `float` | 盈亏比 |
| `total_commission` | `float` | 总手续费 |
| `n_days` | `int` | 回测天数 |

```python
bt.run()
print(bt.metrics['total_return_pct'])   # 15.3
print(bt.metrics['sharpe_ratio'])        # 1.25
```

### bt.results

`pd.DataFrame`，索引为日期。每行是当日收盘后的快照。

| 列 | 类型 | 说明 |
|------|------|------|
| `cash` | `float` | 可用现金 |
| `value` | `float` | 持仓总市值 |
| `total` | `float` | 总资产（cash + value） |
| `positions` | `dict` | 各持仓明细，`{symbol: {size, avg_price, current_price, market_value, profit_pct}}` |
| `trades` | `list[dict]` | 截止当日的全部交易记录 |

```python
bt.results.index        # DatetimeIndex
bt.results['total']     # 每日总资产序列
bt.results['cash']      # 每日现金序列
bt.results.iloc[-1]     # 最终状态
```

### bt.trade_history

`list[dict]`，逐笔交易明细，按成交顺序排列。

买入时含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | `str` | `'buy'` |
| `symbol` | `str` | 股票代码 |
| `price` | `float` | 下单价格（成交前） |
| `exec_price` | `float` | 实际成交价（滑点后） |
| `size` | `int` | 成交股数 |
| `amount` | `float` | 成交金额（exec_price × size） |
| `commission` | `float` | 佣金 |
| `total_cost` | `float` | 总支出（amount + commission） |
| `timestamp` | | 交易日 |

卖出时含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | `str` | `'sell'` |
| `symbol` | `str` | 股票代码 |
| `price` | `float` | 下单价格 |
| `exec_price` | `float` | 实际成交价（滑点后） |
| `size` | `int` | 成交股数 |
| `amount` | `float` | 成交金额 |
| `commission` | `float` | 佣金 |
| `stamp_duty` | `float` | 印花税 |
| `net_proceeds` | `float` | 净收入（amount - commission - stamp_duty） |
| `timestamp` | | 交易日 |

### 完整示例

```python
from qka import Data, Strategy, Backtest

data = Data(
    symbols=['000001.SZ'],
    indicators={
        'sma_5':  ('ta.trend.sma_indicator', 'close', 5),
        'sma_20': ('ta.trend.sma_indicator', 'close', 20),
    },
)

class MaCross(Strategy):
    def __init__(self):
        super().__init__()
        self.pct = 0.2

    def on_bar(self, date):
        close = self.get('close')
        fast = self.get('sma_5')
        slow = self.get('sma_20')
        for sym in close.index:
            price = float(close[sym])
            if fast[sym] > slow[sym]:
                size = self.sizing.percent(self.pct, price)
                if size > 0:
                    self.broker.buy(sym, price, size)
            else:
                pos = self.broker.positions.get(sym, {}).get('size', 0)
                if pos > 0:
                    self.broker.sell(sym, price, pos)

bt = Backtest(data, MaCross())
bt.run(cash=200000, start_date='2024-01-01')
print(bt.metrics['total_return_pct'])
```
