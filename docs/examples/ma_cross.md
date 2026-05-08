# 均线交叉

5 日均线上穿 20 日均线买入，下穿卖出。经典的趋势跟踪策略。

---

## 单股票

```python
"""5 日线上穿 20 日线买入，下穿卖出"""
from qka import Data, Strategy, Broker, Backtest


class MaCross(Strategy):
    def __init__(self):
        super().__init__()
        self.broker = Broker(initial_cash=100_000)

    def on_bar(self, date):
        close = self.get('close')
        if close is None or close.empty:
            return
        if '000001.SZ' not in close.index:
            return

        # 取历史均线
        ma5 = self.history('sma_5', 3)
        ma20 = self.history('sma_20', 3)

        if len(ma5) < 2 or len(ma20) < 2:
            return

        price = float(close['000001.SZ'])
        if price <= 0:
            return

        # 今日 5 日线 > 20 日线，且昨天 5 日线 <= 20 日线（上穿）
        if (ma5['000001.SZ'].iloc[-1] > ma20['000001.SZ'].iloc[-1] and
            ma5['000001.SZ'].iloc[-2] <= ma20['000001.SZ'].iloc[-2]):

            if '000001.SZ' not in self.broker.positions:
                size = self.sizing.percent(0.5, price)
                if size > 0:
                    self.broker.buy('000001.SZ', price, size)

        # 下穿卖出
        elif (ma5['000001.SZ'].iloc[-1] < ma20['000001.SZ'].iloc[-1] and
              ma5['000001.SZ'].iloc[-2] >= ma20['000001.SZ'].iloc[-2]):

            if '000001.SZ' in self.broker.positions:
                pos = self.broker.positions['000001.SZ']
                self.broker.sell('000001.SZ', price, pos['size'])


if __name__ == '__main__':
    data = Data(
        symbols=['000001.SZ'],
        indicators={
            'sma_5': ('sma', 5),
            'sma_20': ('sma', 20),
        },
    )
    bt = Backtest(data, MaCross())
    bt.run(benchmark='000300.SH')
    bt.summary()
    bt.report(title='均线交叉 - 平安银行')
```

---

## 多股票

每只股票独立判断，谁出信号买谁：

```python
"""多股票均线交叉，每只股票判断自己的信号"""
from qka import Data, Strategy, Broker, Backtest


class MultiMaCross(Strategy):
    def __init__(self):
        super().__init__()
        self.broker = Broker(initial_cash=1_000_000)

    def on_bar(self, date):
        close = self.get('close')
        if close is None or close.empty:
            return

        # 取历史均线（多股票的 DataFrame）
        ma5 = self.history('sma_5', 3)
        ma20 = self.history('sma_20', 3)

        if len(ma5) < 2 or len(ma20) < 2:
            return

        for sym in close.index:
            price = float(close[sym])
            if price <= 0:
                continue
            if sym not in ma5.columns or sym not in ma20.columns:
                continue

            # 上穿买入
            if (ma5[sym].iloc[-1] > ma20[sym].iloc[-1] and
                ma5[sym].iloc[-2] <= ma20[sym].iloc[-2]):

                if sym not in self.broker.positions:
                    size = self.sizing.percent(0.1, price)
                    if size > 0:
                        self.broker.buy(sym, price, size)

            # 下穿卖出
            elif (ma5[sym].iloc[-1] < ma20[sym].iloc[-1] and
                  ma5[sym].iloc[-2] >= ma20[sym].iloc[-2]):

                if sym in self.broker.positions:
                    pos = self.broker.positions[sym]
                    self.broker.sell(sym, price, pos['size'])


if __name__ == '__main__':
    data = Data(
        symbols=['000001.SZ', '600000.SH', '000002.SZ'],
        indicators={
            'sma_5': ('sma', 5),
            'sma_20': ('sma', 20),
        },
    )
    bt = Backtest(data, MultiMaCross())
    bt.run(benchmark='000300.SH')
    bt.summary()
    bt.report(title='多股票均线交叉')
```
