# RSI + ATR 风控

RSI 判断超买超卖，ATR 控制仓位大小。比固定股数更贴近实战。

---

```python
"""RSI 超卖买入 + ATR 仓位控制"""
from qka import Data, Strategy, Broker, Backtest


class RsiAtrStrategy(Strategy):
    def __init__(self, cash=1_000_000):
        super().__init__(cash=cash)

    def on_bar(self, date):
        close = self.get('close')
        if close is None or close.empty:
            return

        rsi = self.get('rsi_14')
        atr = self.get('atr_14')

        for sym in close.index:
            price = float(close[sym])
            if price <= 0:
                continue
            if sym not in rsi.index or sym not in atr.index:
                continue

            rsi_val = float(rsi[sym])
            atr_val = float(atr[sym])

            # 超卖（RSI < 30）且没有持仓 → 买入
            if rsi_val < 30 and sym not in self.broker.positions:
                # ATR 控制仓位：每笔风险不超总资金 2%
                size = self.sizing.atr_risk(0.02, price, atr_val)
                if size > 0:
                    self.broker.buy(sym, price, size)

            # 超买（RSI > 70）且有持仓 → 卖出
            elif rsi_val > 70 and sym in self.broker.positions:
                pos = self.broker.positions[sym]
                self.broker.sell(sym, price, pos['size'])


if __name__ == '__main__':
    data = Data(
        symbols=['000001.SZ', '600000.SH', '000002.SZ'],
        indicators={
            'rsi_14': ('rsi', 14),
            'atr_14': ('atr', 14),
        },
    )
    bt = Backtest(data, RsiAtrStrategy())
    bt.run(benchmark='000300.SH')
    bt.summary()
    bt.report(title='RSI + ATR 风控')
```
