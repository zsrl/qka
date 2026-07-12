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

**QKA（快量化 / Quant Kit for A-shares）** — 简洁易用的 A 股量化回测框架。

```python
from qka import Data, Strategy, Backtest

data = Data(
    symbols=['000001.SZ'],
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

---

## 安装

```bash
pip install qka
```

需要 Python 3.10+。

## 快速上手

### 数据

```python
from qka import Data

data = Data(
    symbols=['000001.SZ', '600000.SH'],
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
bt.run(cash=200000, start_date='2024-01-01', benchmark='000300.SH')
print(bt.metrics['total_return_pct'])   # 总收益率
print(bt.metrics['sharpe_ratio'])        # 夏普比率
```

## 核心能力

- **多数据源** — baostock（默认）、akshare、QMT
- **预计算指标** — ta 库全部 60+ 指标，`('ta.trend.sma_indicator', 'close', 5)` 格式直接透传
- **事件驱动回测** — 按日推进，`self.get()` 横截面 + `self.history()` 窗口序列
- **仓位管理** — `sizing.percent()` / `sizing.fixed_amount()` / `sizing.fixed_shares()` / `sizing.atr_risk()`
- **交易模拟** — 佣金万 2.5、印花税万 5（仅卖出）、滑点 0.1%，最低佣金 5 元
- **绩效指标** — 总收益率、年化、夏普比率、最大回撤、Calmar、胜率、盈亏比等 13 项
- **基准对比** — 支持沪深 300（或指定指数）对比

## 文档

框架 API 完整文档见 [skills/qka/SKILL.md](skills/qka/SKILL.md)——所有类的方法签名、参数、返回值和约束都在里面。

## 下一步规划

- [ ] 分钟级数据支持
- [ ] 自适应参数优化
- [ ] 实盘交易（QMT 接口）

## 许可证

[MIT](LICENSE)

## 致谢

- [baostock](http://baostock.com) — 免费 A 股数据
- [Akshare](https://github.com/akfamily/akshare) — 补充数据源
- [ta](https://github.com/bukosabino/ta) — 技术指标库

---

> ⚠️ 量化交易存在风险，请充分了解后再使用本框架。
