# 快速开始

15 分钟，从零跑到第一个回测结果。

---

## 装

```bash
pip install qka
```

需要 Python 3.10 以上。就这样，没别的。

---

## 写策略

新建一个文件，比如 `my_strategy.py`：

```python
from qka import Data, Strategy, Broker, Backtest

class BuyAndHold(Strategy):
    """买入平安银行，一直持有"""

    def __init__(self):
        super().__init__()
        self.broker = Broker(initial_cash=100_000)
        self.bought = False

    def on_bar(self, date):
        """每来一根 K 线，调用一次"""
        close = self.get('close')
        if close is None or close.empty:
            return

        if not self.bought and '000001.SZ' in close.index:
            price = float(close['000001.SZ'])
            if price > 0:
                # 用 20% 的资金买入
                size = self.sizing.percent(0.2, price)
                if size > 0:
                    self.broker.buy('000001.SZ', price, size)
                    self.bought = True
```

- `on_bar(self, date)` — 每根 K 线调一次，date 是当天日期
- `self.get('close')` — 取当天所有股票的收盘价
- `self.sizing.percent(0.2, price)` — 拿 20% 的可用资金买，自动按手取整
- `self.broker.buy(symbol, price, size)` — 买入

---

## 跑回测

```python
data = Data(symbols=['000001.SZ'])
bt = Backtest(data, BuyAndHold())
bt.run(benchmark='000300.SH')
```

数据会自动从 baostock 下载，存到本地缓存，下次直接读。

---

## 看结果

```python
bt.summary()
```

终端输出长这样：

```
QKA 回测报告 — BuyAndHold
────────────────────────────────────────
初始资金:        ¥100,000.00
最终资产:        ¥178,233.45
总收益率:        +78.23%
年化收益率:      +11.34%
最大回撤:        -32.15%
夏普比率:        0.68
交易次数:        1
胜率:            100.00%
────────────────────────────────────────
```

换个好看点的：

```python
bt.report(title='买入持有策略')
```

浏览器会自动打开一个 HTML 页面，有净值曲线、月度收益热力图、交易明细，手机上也能看。

---

## 完整代码

上面三步凑在一起就是这样，复制就能跑：

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

## 接下来

- [数据获取与缓存](../concepts/data.md) — 看看数据是怎么取的、怎么加指标
- [策略开发](../concepts/strategy.md) — 写更复杂的策略
- [策略示例](../examples/buy_and_hold.md) — 直接抄别人写好的策略
