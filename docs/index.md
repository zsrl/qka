# 三行代码，跑个回测

```python
from qka import Data, Strategy, Broker, Backtest

bt = Backtest(Data(['000001.SZ', '600000.SH']), MyStrategy())
bt.run(benchmark='000300.SH')
bt.report()
```

---

## QKA 是什么

写 A 股量化策略的工具。从拿数据、写策略、跑回测、到看报告，一条龙。

装完就能用，不用配数据库，不用搭环境，不用折腾数据源。

---

## 就三件事

| 你想要 | QKA 给你 |
|--------|---------|
| **数据** | 自动下载 A 股日线数据，本地缓存，下次不用重下。支持 baostock 和 akshare 双数据源。 |
| **回测** | 日线级别回测，几百只股票也能跑。佣金、印花税、滑点默认全开，结果贴近实盘。 |
| **报告** | 自动生成 HTML 报告——净值曲线、月度收益热力图、交易明细，手机上也能看。 |

---

## 跑起来

```bash
pip install qka
```

然后新建一个文件，贴进去跑：

```python
from qka import Data, Strategy, Broker, Backtest

class MyStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.broker = Broker(initial_cash=100_000)

    def on_bar(self, date):
        close = self.get('close')
        if close is None or close.empty:
            return
        if '000001.SZ' in close.index:
            price = float(close['000001.SZ'])
            size = self.sizing.percent(0.1, price)
            if size > 0:
                self.broker.buy('000001.SZ', price, size)

data = Data(symbols=['000001.SZ', '600000.SH'])
bt = Backtest(data, MyStrategy())
bt.run(benchmark='000300.SH')
bt.report()
```

[开始用 &rarr;](getting-started/quickstart.md){ .md-button }
[看源码](https://github.com/zsrl/qka){ .md-button }
