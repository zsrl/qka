# 买入持有与定投

最简单的策略：买入，然后不动。

---

## 买入持有

```python
"""买入平安银行，一直持有到回测结束"""
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
                size = self.sizing.percent(0.5, price)
                if size > 0:
                    self.broker.buy('000001.SZ', price, size)
                    self.bought = True


if __name__ == '__main__':
    data = Data(symbols=['000001.SZ'])
    bt = Backtest(data, BuyAndHold())
    bt.run(benchmark='000300.SH')
    bt.summary()
    bt.report(title='买入持有 - 平安银行')
```

---

## 定投

每月固定时间买入固定金额：

```python
"""每月 1 号买入 5000 块"""
from qka import Data, Strategy, Broker, Backtest


class MonthlyDCA(Strategy):
    def __init__(self):
        super().__init__()
        self.broker = Broker(initial_cash=100_000)

    def on_bar(self, date):
        # 每月 1 号买入
        if date.day != 1:
            return

        close = self.get('close')
        if close is None or close.empty:
            return
        if '000001.SZ' in close.index:
            price = float(close['000001.SZ'])
            if price > 0:
                size = self.sizing.fixed_amount(5000, price)
                if size > 0:
                    self.broker.buy('000001.SZ', price, size)


if __name__ == '__main__':
    data = Data(symbols=['000001.SZ'])
    bt = Backtest(data, MonthlyDCA())
    bt.run(benchmark='000300.SH')
    bt.summary()
    bt.report(title='定投 - 每月 1 号 5000 元')
```
