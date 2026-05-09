# QKA — 三行代码跑回测

```python
from qka import Data, Strategy, Broker, Backtest

bt = Backtest(Data(['000001.SZ', '600000.SH']), MyStrategy())
bt.run(benchmark='000300.SH')
bt.report()
```

---

## 装

```bash
pip install qka
```

需要 Python 3.10 以上。就这样，没别的。

---

## 写策略

```python
from qka import Data, Strategy, Broker, Backtest

class BuyAndHold(Strategy):
    def __init__(self):
        super().__init__()
        self.broker = Broker(initial_cash=100_000)
        self.bought = False

    def on_bar(self, date):
        close = self.get('close')
        if close is None or close.empty:
            return
        if not self.bought and '000001.SZ' in close.index:
            price = float(close['000001.SZ'])
            if price > 0:
                size = self.sizing.percent(0.2, price)
                if size > 0:
                    self.broker.buy('000001.SZ', price, size)
                    self.bought = True

data = Data(symbols=['000001.SZ'])
bt = Backtest(data, BuyAndHold())
bt.run(benchmark='000300.SH')
bt.summary()
bt.report()
```

---

## QKA 是什么

A 股量化策略工具。从拿数据、写策略、跑回测、到看报告，一条龙。

装完就能用，不用配数据库，不用搭环境。

---

## 接下来

- [数据](guides/data.md) — 数据是怎么取的
- [策略](guides/strategy.md) — 写更复杂的策略
- [策略示例](examples/buy_and_hold.md) — 直接抄写好的策略
