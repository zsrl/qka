# QKA — 快捷量化助手

<p align="center" style="font-size: 18px; color: #666;">
Quick Quantitative Assistant — 简洁易用的 A 股量化交易框架
</p>

---

## 三行代码跑回测

```python
import qka

bt = qka.Backtest(qka.Data(['000001.SZ', '000002.SZ']), MyStrategy())
bt.run(benchmark='000300.SH')   # 带沪深300基准对比
bt.report()                     # 生成 HTML 报告（手机也能看）
```

---

## 核心特性

| 特性 | 说明 |
|------|------|
| **数据** | 基于 akshare，自动缓存，多只股票并发下载 |
| **策略** | 继承 `Strategy` 基类，实现 `on_bar` 即可 |
| **回测** | 日线级别，多标的横截面，支持自定义因子 |
| **费用** | 佣金（万2.5，最低5元）+ 印花税（万5）+ 滑点（0.1%） |
| **基准** | 一键对比沪深300 |
| **报告** | 自包含 HTML，指标卡片 + 净值曲线 + 月度热力图 + 交易明细，适配手机 |
| **绩效** | 夏普比率、最大回撤、胜率、盈亏比… 一行输出 |

---

## 快速体验

```bash
pip install qka

# 或者从源码安装
git clone https://github.com/zsrl/qka.git
cd qka
uv sync
```

```python
from qka.core.data import Data
from qka.core.strategy import Strategy
from qka.core.backtest import Backtest
from qka.core.broker import Broker

# 1. 写策略
class MyStrategy(Strategy):
    def __init__(self):
        super().__init__(cash=100_000)
        self.broker = Broker(initial_cash=100_000)

    def on_bar(self, date, get):
        close = get('close')
        if '000001.SZ' in close.index:
            self.broker.buy('000001.SZ', close['000001.SZ'], 1000)

# 2. 跑回测
data = Data(symbols=['000001.SZ', '600000.SH'])
bt = Backtest(data, MyStrategy())
bt.run(benchmark='000300.SH')

# 3. 看结果
bt.summary()   # 终端输出绩效指标
bt.report()    # 浏览器打开 HTML 报告
```

[开始使用 &rarr;](getting-started/installation.md){ .md-button }
[查看源码](https://github.com/zsrl/qka){ .md-button }
