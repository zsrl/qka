# 回测分析

回测是量化策略开发的核心环节。QKA 提供完整的回测功能，覆盖从策略执行到结果分析的完整流程。

---

## 基本用法

```python
from qka import Data, Strategy, Broker, Backtest

class MyStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.broker = Broker(initial_cash=1_000_000)

    def on_bar(self, date):
        close = self.get('close')
        if close is None or close.empty:
            return
        # 你的交易逻辑

data = Data(symbols=['000001.SZ', '600000.SH'])
bt = Backtest(data, MyStrategy())
bt.run()
```

---

## 费用模型

### 默认费率

| 费用 | 方向 | 费率 | 最低 |
|------|------|------|------|
| 佣金 | 买卖双向 | 万2.5 | 5 元 |
| 印花税 | 卖出时 | 万5 | 无 |
| 滑点 | 买卖双向 | 0.1% | — |

### 自定义费率

```python
from qka import Broker

self.broker = Broker(
    initial_cash=1_000_000,
    commission_rate=0.0001,      # 万1 佣金
    stamp_duty_rate=0.0005,      # 万5 印花税
    slippage=0.0005,             # 0.05% 滑点
)
```

### 费用说明

- **佣金**：买入和卖出都收取，计算公式为 `成交额 × commission_rate`，不足 5 元按 5 元收
- **印花税**：仅卖出时收取，A 股固定万5，`成交额 × stamp_duty_rate`
- **滑点**：买入价上移 `price × (1 + slippage)`，卖出价下移 `price × (1 - slippage)`，模拟实际成交的偏差

---

## 基准对比

在 `run()` 时传入基准代码即可自动对比：

```python
bt.run(benchmark='000300.SH')   # 沪深300
```

支持的基准代码：

| 代码 | 含义 |
|------|------|
| `000300.SH` | 沪深300指数 |
| `000001.SH` | 上证指数 |
| `399001.SZ` | 深证成指 |

基准数据通过 akshare 自动下载，在报告中会以归一化后的虚线展示。

---

## 绩效指标

### 通过 `summary()` 查看

```python
metrics = bt.summary()
```

输出示例：

```
=======================================================
           回测绩效报告
=======================================================
  初始资金:         RMB 1,000,000.00
  最终资产:         RMB 2,356,182.73
  总收益率:          +135.62%
  年化收益率:        +18.34%
  年化波动率:        32.15%
  夏普比率:           0.48
  最大回撤:          -28.73%
  Calmar比率:         0.64
  交易次数:            156
  胜率:              42.31%
  盈亏比:             2.15
  总手续费:         RMB 12,456.18
=======================================================
```

### 指标说明

| 指标 | 计算方式 |
|------|----------|
| **总收益率** | `(最终资产 / 初始资金 - 1) × 100%` |
| **年化收益率** | `(最终资产 / 初始资金) ^ (252 / 交易日数) - 1` |
| **年化波动率** | 日收益率标准差 × √252 |
| **夏普比率** | `(年化收益率 - 3%) / 年化波动率` |
| **最大回撤** | 净值从峰值回落到谷底的最大幅度 |
| **胜率** | 盈利交易次数 / 总交易次数 |
| **盈亏比** | 平均盈利 / 平均亏损（绝对值） |

---

## HTML 报告

### 快速生成

```python
bt.report()
# 自动保存到 reports/ 目录
```

### 自定义标题和路径

```python
bt.report(
    title='双均线策略',
    output_path='~/my_report.html'
)
```

### 报告内容

报告是一个**自包含的 HTML 文件**，可直接在浏览器打开，包含：

- **8 个指标卡片**：总收益率、年化收益率、夏普比率、最大回撤、胜率、盈亏比、交易次数、总手续费
- **净值曲线图**：策略资产变化 + 基准对比（虚线），下方叠加回撤曲线
- **月度收益率热力图**：按月查看收益分布，绿色正收益、红色负收益
- **交易明细表**：每笔交易的日期、方向、代码、数量、价格、金额、手续费
- **回撤分析表**：Top 5 最大回撤区间，含起止日期和持续天数

### 移动端适配

报告自动适配手机屏幕：

| 屏幕宽度 | 效果 |
|----------|------|
| >768px | 4 列指标卡，完整表格 |
| 481-768px | 2 列指标卡，表格横向滚动 |
| <=480px | 2 列指标卡，表格变为堆叠卡片（每行一个独立卡片） |

---

## 完整示例：5 日动量策略

以下是使用 `self.history()` 实现的 5 日动量策略——选过去 5 天涨幅最大的 2 只等权买入。

```python
from qka import Data, Strategy, Broker, Backtest
import numpy as np

class MomentumStrategy(Strategy):
    """5日动量策略"""
    def __init__(self):
        super().__init__()
        self.broker = Broker(initial_cash=1_000_000)
        self.holding = set()

    def on_bar(self, date):
        # 获取过去 5 天收盘价
        hist = self.history('close', 5)
        if len(hist) < 5:
            return   # 数据不足

        # 计算每只股票的 5 日涨幅
        first = hist.iloc[0]    # 5 日前
        last  = hist.iloc[-1]   # 今日
        valid = (first > 0) & (last > 0)
        momentum = pd.Series(index=hist.columns, dtype=float)
        momentum[valid] = last[valid] / first[valid] - 1
        momentum = momentum.dropna()

        if len(momentum) < 2:
            return

        # 动量最强的 2 只
        targets = set(momentum.nlargest(2).index)

        # 卖出不在选股池的持仓
        for sym in list(self.holding):
            close = self.get('close')
            if close is None or sym not in close.index or sym in targets:
                continue
            price = float(close[sym])
            if price > 0 and sym in self.broker.positions:
                self.broker.sell(sym, price, self.broker.positions[sym]['size'])
                self.holding.discard(sym)

        # 买入选中股票
        for sym in targets:
            if sym in self.holding:
                continue
            close = self.get('close')
            if close is None or sym not in close.index:
                continue
            price = float(close[sym])
            if price <= 0:
                continue
            cash_per = self.broker.cash * 0.48 / price
            size = int(cash_per // 100) * 100
            if size > 0:
                self.broker.buy(sym, price, size)
                self.holding.add(sym)


# 运行
data = Data(symbols=['000001.SZ', '000002.SZ', '600000.SH'])
bt = Backtest(data, MomentumStrategy())
bt.run(benchmark='000300.SH')
bt.summary()
bt.report(title='5日动量策略')
```

---

## 大规模回测（300+ 只股票）

QKA 内置 **dask 分区迭代引擎**，可高效处理数百只股票数年数据：

```python
from qka import Data, Strategy, Backtest

# 甚至 300 只也行
symbols = ['000001.SZ', '600000.SH', ...]  # 300 只
data = Data(symbols=symbols, source='baostock')

class MyStrategy(Strategy):
    def on_bar(self, date):
        close = self.get('close')
        if close is None or close.empty:
            return
        # ... 你的逻辑不会因股票数量增加而变慢

bt = Backtest(data, MyStrategy())
bt.run()        # 自动使用 dask 分区迭代
```

底层原理是：

1. dask 按时间将数据切分为约 500 bar/分区
2. 逐分区 compute() 到内存
3. DataAccessor 跨分区缓存历史数据
4. 内存峰值 = 单分区 + 滚动窗口，与总数据量无关

详见 [性能优化](../advanced/performance.md)。
