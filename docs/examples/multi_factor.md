# 多因子打分

用多个因子综合打分，选分最高的买。多因子策略的骨架。

---

```python
"""PE + 动量 + 波动率三因子打分选股"""
from qka import Data, Strategy, Broker, Backtest


class MultiFactor(Strategy):
    def __init__(self, cash=1_000_000):
        super().__init__(cash=cash)
        self.last_month = None

    def on_bar(self, date):
        close = self.get('close')
        if close is None or close.empty:
            return

        # 每月末调仓
        if date.day < 28:
            return

        month_key = (date.year, date.month)
        if self.last_month == month_key:
            return
        self.last_month = month_key

        rsi = self.get('rsi_14')
        hist = self.history('rsi_14', 20)
        if hist is None or hist.empty:
            return

        scores = {}
        for sym in close.index:
            price = float(close[sym])
            if price <= 0:
                continue
            if sym not in rsi.index or sym not in hist.columns:
                continue

            rsi_val = float(rsi[sym])
            hist_series = hist[sym].dropna()

            # 因子 1：RSI 适中（30-70 之间最好，太高中性，太低扣分）
            score1 = 1.0 if 30 < rsi_val < 70 else 0.0
            if rsi_val < 30:
                score1 = -0.5

            # 因子 2：RSI 趋势（最近 20 天 RSI 上升趋势）
            if len(hist_series) >= 10:
                recent = hist_series.iloc[-5:].mean()
                earlier = hist_series.iloc[-10:-5].mean()
                score2 = (recent - earlier) / earlier
                score2 = max(-1, min(1, score2))  # 限制到 [-1, 1]
            else:
                score2 = 0

            # 因子 3：波动率（低波动加分）
            if len(hist_series) >= 10:
                vol = hist_series.std()
                score3 = max(-1, min(1, -vol / 20))  # 波动越低分越高
            else:
                score3 = 0

            # 综合打分
            scores[sym] = 0.4 * score1 + 0.4 * score2 + 0.2 * score3

        if not scores:
            return

        # 选前 3 名
        sorted_syms = sorted(scores, key=scores.get, reverse=True)
        buy_list = sorted_syms[:3]

        # 卖出不在名单里的
        for sym in list(self.broker.positions.keys()):
            if sym not in buy_list:
                pos = self.broker.positions[sym]
                price = float(close[sym])
                if price > 0:
                    self.broker.sell(sym, price, pos['size'])

        # 买入名单里的新标的
        cash_per_sym = self.broker.cash / len(buy_list)
        for sym in buy_list:
            if sym in self.broker.positions:
                continue
            price = float(close[sym])
            if price > 0:
                size = self.sizing.fixed_amount(cash_per_sym, price)
                if size > 0:
                    self.broker.buy(sym, price, size)


if __name__ == '__main__':
    data = Data(
        symbols=['000001.SZ', '600000.SH', '000002.SZ',
                 '600036.SH', '601166.SH', '600519.SH',
                 '000858.SZ', '002415.SZ', '300750.SZ'],
        indicators={
            'rsi_14': ('rsi', 14),
        },
    )
    bt = Backtest(data, MultiFactor())
    bt.run(benchmark='000300.SH')
    bt.summary()
    bt.report(title='多因子打分选股')
```
