# 策略

写一个策略就是写一个类，继承 `Strategy`，实现 `on_bar` 方法。

---

## 骨架

```python
from qka import Strategy, Broker

class MyStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.broker = Broker(initial_cash=100_000)

    def on_bar(self, date):
        close = self.get('close')
        if close is None or close.empty:
            return
        # 你的交易逻辑写在这
```

## 生命周期

回测按天跑。每天调用一次 `on_bar(date)`，告诉你今天是哪一天，你根据今天的数据决定要不要交易。

## 取数据

**`self.get(factor)`** — 今天所有股票的横截面：

```python
close = self.get('close')
# 000001.SZ    10.50
# 600000.SH     8.32

price = float(close['000001.SZ'])

for sym in close.index:
    price = float(close[sym])
```

**`self.history(factor, window)`** — 过去 N 天的历史：

```python
hist = self.history('close', 20)
#              000001.SZ  600000.SH
# 2024-01-02      10.2       8.12
# 2024-01-03      10.5       8.32

avg = hist['000001.SZ'].mean()
```

能取什么字段取决于 `Data` 里有什么。基础字段（`open`/`high`/`low`/`close`/`volume`）自动有，指标字段需要在 `indicators` 里声明。

## 交易

```python
self.broker.buy('000001.SZ', price, size)    # 买入
self.broker.sell('000001.SZ', price, size)   # 卖出
```

`size` 是股数。该买多少用 `self.sizing` 算。

## 仓位

```python
size = self.sizing.percent(0.1, price)           # 可用资金 10%
size = self.sizing.fixed_amount(10000, price)    # 固定 1 万
size = self.sizing.atr_risk(0.02, price, atr)    # ATR 风控
```

详见[仓位](sizing.md)。

## 状态管理

在 `__init__` 里定义变量，整个回测过程中都有效：

```python
class MyStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.broker = Broker(initial_cash=100_000)
        self.bought = False
        self.entry_prices = {}
```

## 多股票

`self.get('close')` 返回所有股票的横截面，遍历处理：

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

## 不要做的事

| 不要做 | 为什么 |
|--------|--------|
| `on_bar` 里下载数据 | 每根 bar 都下载，慢到崩溃 |
| `on_bar` 里 print | 几千根 bar 刷屏，用 `logger.debug` |
| 访问回测引擎内部 | 策略只跟 broker 和 sizing 打交道 |
