# QKA — Quant Kit for A-shares

<p align="center">
  <a href="https://qka.quantai.chat" target="_blank">
    <img src="https://img.shields.io/badge/文档站-qka.quantai.chat-blue?style=flat" alt="文档站">
  </a>
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

**QKA（Quant Kit for A-shares）** — 简洁易用的 A 股量化回测框架。

```python
from qka import Data, Strategy, Backtest

class MyStrategy(Strategy):
    def on_bar(self, date):
        close = self.get('close')
        for sym in close.index:
            if sym not in self.broker.positions:
                price = float(close[sym])
                if price > 0:
                    size = self.sizing.percent(0.1, price)
                    if size >= 100:
                        self.broker.buy(sym, price, size)

bt = Backtest(Data(['000001.SZ']), MyStrategy(cash=100_000))
bt.run(benchmark='000300.SH')
bt.report()
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
    indicators={'sma_5': ('sma', 5), 'rsi_14': ('rsi', 14)},
)
df = data.get()  # 触发下载，返回宽表 DataFrame
```

### 策略

```python
from qka import Strategy

class MyStrategy(Strategy):
    def __init__(self, cash=100_000):
        super().__init__(cash=cash)
        # 自定义状态放这里

    def on_bar(self, date):
        close = self.get('close')
        hist = self.history('close', 20)
        # 写你的交易逻辑
```

### 回测

```python
from qka import Backtest

bt = Backtest(data, MyStrategy(cash=100_000))
bt.run(benchmark='000300.SH')
print(bt.summary())    # 输出绩效指标
bt.report()            # 生成 HTML 报告
```

### 更多示例

| 策略 | 说明 |
|------|------|
| [买入持有与定投](https://qka.quantai.chat/examples/buy_and_hold/) | 买入不动 + 每月定投 |
| [均线交叉](https://qka.quantai.chat/examples/ma_cross/) | 5日线上穿/下穿20日线 |
| [RSI + ATR 风控](https://qka.quantai.chat/examples/rsi_atr/) | RSI 超卖买入，ATR 止损 |
| [动量排序选股](https://qka.quantai.chat/examples/momentum/) | 月度动量排序，Top 5 等权 |
| [多因子打分](https://qka.quantai.chat/examples/multi_factor/) | PE/ROE/动量/波动率打分选股 |

## 核心能力

- **多数据源** — baostock（默认）、akshare、QMT，自动缓存
- **预计算指标** — sma/ema/macd/rsi/bbands/atr + 自定义因子
- **事件驱动回测** — 按日推进，`self.get()` 横截面 + `self.history()` 窗口序列
- **仓位管理** — `self.sizing.percent()` / `self.sizing.fixed_amount()` / `self.sizing.fixed_shares()` / `self.sizing.atr_risk()`
- **交易模拟** — 佣金万2.5、印花税万5、滑点0.1%，最低佣金5元
- **HTML 报告** — Plotly 交互图表，累计收益、回撤、月度热力图、交易明细
- **基准对比** — 自动下载沪深300（或指定指数）做对比

## 文档

完整教程、API 参考、示例代码：

👉 **[qka.quantai.chat](https://qka.quantai.chat)**

## 下一步规划

- [ ] 分钟级数据支持
- [ ] 自适应参数优化
- [ ] 实盘交易（QMT 接口）

## 许可证

[MIT](LICENSE)

## 致谢

- [baostock](http://baostock.com) — 免费 A 股数据
- [Akshare](https://github.com/akfamily/akshare) — 补充数据源
- [Plotly](https://plotly.com/python/) — 交互式图表
- [xtquant](https://github.com/ShiMiaoYS/xtquant) — QMT 接口

---

> ⚠️ 量化交易存在风险，请充分了解后再使用本框架。
