# QKA — 快量化
## Quant Kit for A-shares

<p align="center">
  <a href="https://pypi.org/project/qka/">
    <img src="https://img.shields.io/pypi/v/qka?color=blue" alt="PyPI">
  </a>
  <a href="https://github.com/zsrl/qka">
    <img src="https://img.shields.io/badge/python-3.10+-blue" alt="Python">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </a>
</p>

简洁易用的 A 股量化回测框架。

---

## 安装

### 包安装

```bash
pip install qka
```

需要 Python 3.10+。

### AI 技能安装

为 Claude Code、Cursor 等 AI 编程工具安装 QKA 技能：

```bash
npx skills add zsrl/qka
```

安装后，AI 助手即可自动加载 QKA 框架的 API 文档，生成符合规范的量化策略代码。

## 快速上手

### 数据

```python
from qka import Data

data = Data(
    symbols=['sz.000001', 'sh.600000'],
    indicators={
        'sma_5':  ('ta.trend.sma_indicator', 'close', 5),
        'rsi_14': ('ta.momentum.rsi', 'close', 14),
    },
)
df = data.get()  # 返回宽表 DataFrame，列名 {symbol}|{factor}
```

### 策略

```python
from qka import Strategy

class MyStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.lookback = 20  # 自定义参数

    def on_bar(self, date):
        close = self.get('close')            # 当前横截面
        hist = self.history('close', 20)     # 历史窗口
        # 交易逻辑：self.broker.buy / self.broker.sell
        # 仓位计算：self.sizing.percent / self.sizing.fixed_shares
```

### 回测

```python
from qka import Backtest

strategy = MyStrategy()
bt = Backtest(data, strategy)
bt.run(cash=200000, start_date='2024-01-01', benchmark='sh.000300')
print(bt.metrics['total_return_pct'])   # 总收益率
print(bt.metrics['sharpe_ratio'])        # 夏普比率
```

## 核心能力

- **数据获取** — 写个股票代码就能取到本地，自动缓存、自动补齐最新数据，重复使用秒读
- **技术指标** — 均线、MACD、RSI、ATR 等 ta 库全部指标，外加 α/β、夏普、最大回撤等内置指标，声明一下即可，策略里不用自己 rolling
- **估值字段** — 换手率、涨跌幅、停牌与 ST 标记、市盈率、市净率等，需要哪些就取哪些
- **模拟行情** — 一条 `Simulate` 就能造出单边上涨、单边下跌、来回震荡的走势，不必等真实行情，用来验证策略是不是真在按逻辑交易
- **多标的回测** — 一次传一篮子股票，`self.get()` 取当日横截面，`self.history()` 取历史窗口
- **仓位管理** — 按资金比例、按金额、按股数、按 ATR 风险四种算法
- **交易成本** — 佣金、印花税、滑点均已内置，也可自行调整
- **绩效指标** — 总收益、年化、夏普、最大回撤、Calmar、胜率、盈亏比等 13 项，跑完即有
- **回测报告** — 净值曲线、回撤曲线、月度收益热力图、逐笔交易明细，一键生成 HTML，浏览器直接打开
- **基准对比** — 传入基准指数即可对比收益、计算 β / α

## 文档

框架 API 完整文档见 [skills/qka/SKILL.md](skills/qka/SKILL.md)——所有类的方法签名、参数、返回值和约束都在里面。

## 完整示例

```python
from qka import Data, Strategy, Backtest

data = Data(
    symbols=['sz.000001'],
    indicators={
        'sma_5':  ('ta.trend.sma_indicator', 'close', 5),
        'sma_20': ('ta.trend.sma_indicator', 'close', 20),
    },
)

class MaCross(Strategy):
    def __init__(self):
        super().__init__()
        self.pct = 0.2

    def on_bar(self, date):
        close = self.get('close')
        fast = self.get('sma_5')
        slow = self.get('sma_20')
        for sym in close.index:
            price = float(close[sym])
            if price <= 0:
                continue
            if fast[sym] > slow[sym]:
                size = self.sizing.percent(self.pct, price)
                if size > 0:
                    self.broker.buy(sym, price, size)
            else:
                pos = self.broker.positions.get(sym, {}).get('size', 0)
                if pos > 0:
                    self.broker.sell(sym, price, pos)

strategy = MaCross()
bt = Backtest(data, strategy)
bt.run(cash=200000, start_date='2024-01-01')
print(bt.metrics['total_return_pct'])
```

## 许可证

[MIT](LICENSE)

## 致谢

- [baostock](http://baostock.com) — 免费 A 股数据
- [ta](https://github.com/bukosabino/ta) — 技术指标库

---

> ⚠️ 量化交易存在风险，请充分了解后再使用本框架。
