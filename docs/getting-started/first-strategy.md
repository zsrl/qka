# 第一个策略

本指南带你从零跑通第一个策略。整个过程只需要几步。

---

## 步骤 1：获取数据

```python
from qka import Data

data = Data(symbols=['000001.SZ'])   # 平安银行
```

`Data` 会自动从 **baostock** 下载数据并缓存到本地（`datadir/` 目录），下次直接读缓存，不用重复下载。

---

## 步骤 2：定义策略

所有策略都继承 `Strategy` 基类，实现 `on_bar(self, date)` 方法：

```python
from qka import Strategy, Broker

class BuyAndHold(Strategy):
    """买入 100 股平安银行并持有"""
    def __init__(self):
        super().__init__()
        self.broker = Broker(initial_cash=100_000)  # 10万元本金
        self.bought = False

    def on_bar(self, date):
        """
        每个交易日调用一次。

        用 self.get() 获取当前行情，self.history() 获取历史序列。

        Args:
            date: 当前交易日（pd.Timestamp）
        """
        close = self.get('close')
        if close is None or close.empty:
            return
        if not self.bought and '000001.SZ' in close.index:
            price = float(close['000001.SZ'])
            if price > 0:
                self.broker.buy('000001.SZ', price, 100)
                self.bought = True
```

### 关键 API

| 方法 | 功能 | 返回 |
|------|------|------|
| `self.get('close')` | 当前 bar 所有股票收盘价 | `pd.Series`（index=股票代码） |
| `self.history('close', 20)` | 过去 N 日收盘价历史 | `pd.DataFrame`（行=日期，列=股票代码） |
| `self.ta.sma('close', 20)` | 简单移动平均线 | `pd.Series` |
| `self.ta.rsi('close', 14)` | 相对强弱指标 | `pd.Series` |
| `self.ta.macd('close')` | MACD 三线 | `pd.DataFrame` |

!!! tip "不再是闭包"
    与旧版本不同，`on_bar` 不再接收 `get` 参数。所有数据通过 `self.get()` 和 `self.history()` 访问，代码更简洁一致。

---

## 步骤 3：运行回测

```python
from qka import Backtest

bt = Backtest(data, BuyAndHold())
bt.run(benchmark='000300.SH')   # 对比沪深300
```

`bt.run()` 会：
1. 按日期遍历所有数据
2. 每天调用策略的 `on_bar(date)` 方法
3. 自动记录资金、持仓和交易历史
4. 如果指定了 `benchmark`，自动下载基准数据

---

## 步骤 4：查看结果

### 绩效指标

```python
bt.summary()
```

输出示例：

```
=======================================================
           回测绩效报告
=======================================================
  初始资金:         RMB 100,000.00
  最终资产:         RMB 156,283.45
  总收益率:          +56.28%
  年化收益率:        +8.34%
  夏普比率:           0.52
  最大回撤:          -42.37%
  胜率:              100.00%
  总手续费:          RMB 67.50
=======================================================
```

### HTML 报告

```python
bt.report(title='买入持有策略')
# 自动保存到 reports/ 下
```

报告包含：
- 8 个核心指标卡片
- 净值曲线（含基准对比）+ 回撤曲线
- 月度收益率热力图
- 交易明细表
- 回撤分析表

在手机上也能正常查看——窄屏下表格自动变为堆叠卡片布局。

---

## 完整代码

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
                self.broker.buy('000001.SZ', price, 100)
                self.bought = True

data = Data(symbols=['000001.SZ'])
bt = Backtest(data, BuyAndHold())
bt.run(benchmark='000300.SH')
bt.summary()
bt.report(title='买入持有策略')
```

---

## 进阶：用 `self.history()` 计算均线

用 `self.history()` 获取过去 N 天的收盘价序列：

```python
from qka import Strategy, Broker
import numpy as np

class MaCross(Strategy):
    """5日均线上穿20日均线买入"""
    def __init__(self):
        super().__init__()
        self.broker = Broker(initial_cash=100_000)
        self.bought = False

    def on_bar(self, date):
        hist = self.history('close', 20)
        if len(hist) < 20:
            return   # 数据不足，跳过

        # hist 是 DataFrame，行=日期，列=股票代码
        ma5 = hist.iloc[-5:].mean()
        ma20 = hist.mean()

        for sym in hist.columns:
            close = self.get('close')
            if close is None or sym not in close.index:
                continue
            price = float(close[sym])
            if price <= 0:
                continue

            if ma5[sym] > ma20[sym] and not self.bought:
                self.broker.buy(sym, price, 100)
                self.bought = True
            elif ma5[sym] < ma20[sym] and self.bought:
                if sym in self.broker.positions:
                    self.broker.sell(sym, price, self.broker.positions[sym]['size'])
                self.bought = False
```

## 进阶 2：用 `self.ta` 调用技术指标

`self.ta` 提供了内置技术指标，基于 `ta` 库，一行代码即可计算：

```python
from qka import Strategy, Broker

class RsiStrategy(Strategy):
    """RSI 超卖买入，超买卖出"""
    def __init__(self):
        super().__init__()
        self.broker = Broker(initial_cash=100_000)

    def on_bar(self, date):
        close = self.get('close')
        if close is None or close.empty:
            return

        # 一行计算 RSI
        rsi = self.ta.rsi('close', length=14)

        for sym in close.index:
            if sym not in rsi.index:
                continue
            price = float(close[sym])
            if price <= 0:
                continue

            if rsi[sym] < 30 and sym not in self.broker.positions:
                # RSI 低于 30，超卖，买入
                self.broker.buy(sym, price, 100)
            elif rsi[sym] > 70 and sym in self.broker.positions:
                # RSI 高于 70，超买，卖出
                pos = self.broker.positions[sym]
                self.broker.sell(sym, price, pos['size'])
```

所有支持的指标：

| 方法 | 说明 | 返回 |
|------|------|------|
| `self.ta.sma(factor, length)` | 简单移动平均 | `pd.Series` |
| `self.ta.ema(factor, length)` | 指数移动平均 | `pd.Series` |
| `self.ta.rsi(factor, length)` | 相对强弱指标 | `pd.Series` |
| `self.ta.atr(high, low, close, length)` | 平均真实波幅 | `pd.Series` |
| `self.ta.macd(factor, fast, slow, signal)` | MACD 三线 | `pd.DataFrame` |
| `self.ta.bbands(factor, length, std)` | 布林带三轨 | `pd.DataFrame` |
| `self.ta.custom(factor, func, ...)` | 自定义指标 | `pd.Series` |
```

---

## 下一步

- 学习 [核心概念](concepts.md) — 架构设计、DataAccessor 数据流
- 学习 [回测分析](../user-guide/backtest.md) — 费用设置、绩效指标详解
- 探索 [性能优化](../advanced/performance.md) — dask 分区迭代原理
