# 策略

策略是一个继承 `Strategy` 基类的 Python 类，核心是实现 `on_bar` 方法。

---

## 基本结构

```python
from qka import Strategy

class MyStrategy(Strategy):
    def __init__(self, cash=100_000):
        super().__init__(cash=cash)

    def on_bar(self, date):
        close = self.get('close')
        if close is None or close.empty:
            return
        # 交易逻辑写在这里
```

## 生命周期

回测按时间顺序逐日推进。每个交易日调用一次 `on_bar(date)`，策略根据当日数据决定是否交易。

## 数据获取

**`self.get(factor)`** — 当日所有股票的横截面数据：

```python
close = self.get('close')
# 返回 pd.Series:
# 000001.SZ    10.50
# 600000.SH     8.32

price = float(close['000001.SZ'])

for sym in close.index:
    price = float(close[sym])
```

**`self.history(factor, window)`** — 过去 N 个交易日的历史数据：

```python
hist = self.history('close', 20)
# 返回 pd.DataFrame:
#              000001.SZ  600000.SH
# 2024-01-02      10.2       8.12
# 2024-01-03      10.5       8.32

avg = hist['000001.SZ'].mean()
```

可访问的字段由 `Data` 配置决定。基础字段（`open`/`high`/`low`/`close`/`volume`）自动可用，指标字段需在 `indicators` 中声明。

## 交易

```python
self.broker.buy('000001.SZ', price, size)    # 买入
self.broker.sell('000001.SZ', price, size)   # 卖出
```

`size` 为股数。使用 `self.sizing` 计算合理仓位。

## 仓位计算

```python
size = self.sizing.percent(0.1, price)           # 可用资金的 10%
size = self.sizing.fixed_amount(10000, price)    # 固定金额 1 万元
size = self.sizing.atr_risk(0.02, price, atr)    # ATR 风控仓位
```

详见[仓位](sizing.md)。

## 状态管理

在 `__init__` 中定义的自定义属性在整个回测过程中持续有效：

```python
class MyStrategy(Strategy):
    def __init__(self, cash=100_000):
        super().__init__(cash=cash)
        self.bought = False          # 自定义状态
        self.entry_prices = {}        # 入场价格记录
```

## 多股票处理

`self.get('close')` 返回所有股票的横截面，遍历处理即可：

```python
def on_bar(self, date):
    close = self.get('close')
    if close is None or close.empty:
        return
    for sym in close.index:
        price = float(close[sym])
        if price <= 0 or sym in self.broker.positions:
            continue
        size = self.sizing.percent(0.1, price)
        if size > 0:
            self.broker.buy(sym, price, size)
```

## 注意事项

| 行为 | 原因 |
|------|------|
| 不要在 `on_bar` 中下载数据 | 每根 bar 都下载会导致性能严重下降 |
| 不要在 `on_bar` 中使用 print | 数千根 bar 的输出量过大，应使用 `logger.debug` |
| 不要访问回测引擎内部 | 策略只需与 broker 和 sizing 交互 |
