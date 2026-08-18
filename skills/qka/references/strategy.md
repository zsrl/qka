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
| index | 股票代码，如 `'sz.000001'`、`'sh.600000'` |
| values | 当前 bar 的最新值，`float` |
| 空值 | 无数据时返回空 `pd.Series`，不是 `None` |

```python
# 安全访问
if 'sz.000001' in close.index:
    price = float(close['sz.000001'])
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

### self.broker / self.sizing

由 `Backtest.run()` 注入（见上方注入表），通过 `self.broker.buy()` / `self.broker.sell()` 和 `self.sizing.percent()` 等方法使用。详见 [Broker](#broker) 和 [SizingAccessor](#sizingaccessor) 独立章节。

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
