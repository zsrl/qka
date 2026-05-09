# 三行代码跑回测

```python
from qka import Data, Strategy, Broker, Backtest

class MyStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.broker = Broker(100_000)
    def on_bar(self, date):
        close = self.get('close')
        if close is not None and '000001.SZ' in close.index:
            self.broker.buy('000001.SZ', float(close['000001.SZ']), 100)

bt = Backtest(Data(['000001.SZ']), MyStrategy())
bt.run(benchmark='000300.SH')
bt.report()
```

---

## 安装

```bash
pip install qka
```

需要 Python 3.10 以上。

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
        """每根 K 线调用一次"""
        close = self.get('close')
        if close is None or close.empty:
            return

        if not self.bought and '000001.SZ' in close.index:
            price = float(close['000001.SZ'])
            if price > 0:
                # 用 20% 的资金买入，自动按手取整
                size = self.sizing.percent(0.2, price)
                if size > 0:
                    self.broker.buy('000001.SZ', price, size)
                    self.bought = True
```

- `on_bar(self, date)` — 每根 K 线调一次，date 是当天日期
- `self.get('close')` — 取当天所有股票的收盘价
- `self.sizing.percent(0.2, price)` — 用可用资金的 20% 买入，自动按手取整
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

使用 HTML 报告：

```python
bt.report(title='买入持有策略')
```

浏览器打开一个包含净值曲线、月度收益热力图、交易明细的交互页面，手机上也能正常查看。

---

## 完整代码

上面几步凑在一起就是：

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

复制即可运行。

---

## 接下来

- [数据](guides/data.md) — 数据是怎么取的、怎么加指标
- [策略](guides/strategy.md) — 写更复杂的策略
- [策略示例](examples/buy_and_hold.md) — 直接抄别人写好的策略
