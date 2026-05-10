# 动量排序选股

每月末按过去 N 日收益率排序，选前几名买入。最经典的量化策略之一。

---

```python
"""每月末按动量排序，选前 20% 的股票买入"""
from qka import Data, Strategy, Broker, Backtest


class Momentum(Strategy):
    def __init__(self):
        super().__init__()
        self.broker = Broker(initial_cash=1_000_000)
        self.last_month = None

    def on_bar(self, date):
        # 月末附近调仓
        if date.day < 28:
            return

        # 本月已调仓，跳过
        month_key = (date.year, date.month)
        if self.last_month == month_key:
            return
        self.last_month = month_key

        close = self.get('close')
        if close is None or close.empty:
            return

        # 过去 60 个交易日的动量
        hist = self.history('close', 60)
        if hist is None or hist.empty:
            return

        # 计算每只股票的阶段收益率
        ret = {}
        for sym in hist.columns:
            prices = hist[sym].dropna()
            if len(prices) >= 40:  # 至少 40 个有效数据
                ret[sym] = prices.iloc[-1] / prices.iloc[0] - 1

        if not ret:
            return

        # 排序，选前 20%
        sorted_syms = sorted(ret, key=ret.get, reverse=True)
        top_n = max(1, len(sorted_syms) // 5)
        buy_list = sorted_syms[:top_n]

        # 卖出不在列表里的持仓
        for sym in list(self.broker.positions.keys()):
            if sym not in buy_list:
                pos = self.broker.positions[sym]
                price = float(close.get(sym, 0))
                if price > 0:
                    self.broker.sell(sym, price, pos['size'])

        # 买入列表中的新标的
        cash_per_sym = self.broker.cash / len(buy_list)
        for sym in buy_list:
            if sym in self.broker.positions:
                continue
            price = float(close.get(sym, 0))
            if price > 0:
                size = self.sizing.fixed_amount(cash_per_sym, price)
                if size > 0:
                    self.broker.buy(sym, price, size)


if __name__ == '__main__':
    data = Data(
        symbols=['000001.SZ', '600000.SH', '000002.SZ',
                 '600036.SH', '601166.SH'],
    )
    bt = Backtest(data, Momentum())
    bt.run(benchmark='000300.SH')
    bt.summary()
    bt.report(title='动量排序选股')
```
