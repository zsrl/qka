# 第一个策略

本指南带你从零跑通第一个策略——5 日均线买入持有。整个过程只需要几步。

---

## 步骤 1：获取数据

```python
from qka.core.data import Data

data = Data(symbols=['000001.SZ'])   # 平安银行
```

`Data` 会自动从 akshare 下载数据并缓存到本地（`datadir/` 目录），下次运行直接读缓存，不用重复下载。

---

## 步骤 2：定义策略

所有策略都继承 `Strategy` 基类，实现 `on_bar` 方法：

```python
from qka.core.strategy import Strategy
from qka.core.broker import Broker

class BuyAndHold(Strategy):
    """买入 100 股平安银行并持有"""
    def __init__(self):
        super().__init__(cash=100_000)
        self.broker = Broker(initial_cash=100_000)  # 10万元本金
        self.bought = False

    def on_bar(self, date, get):
        """
        每个交易日调用一次。

        Args:
            date: 当前日期
            get: 获取因子数据的函数
                 get('close')  → 返回 pd.Series, index=股票代码
                 get('volume') → 返回 pd.Series
        """
        close = get('close')
        if not self.bought and '000001.SZ' in close.index:
            price = float(close['000001.SZ'])
            self.broker.buy('000001.SZ', price, 100)
            self.bought = True
```

### 关键规则

- `get('close')` 返回**当前 bar 的横截面数据**（所有股票的最新收盘价），不是历史序列
- `self.broker.buy(symbol, price, size)` 自动计算佣金和滑点
- broker 有 **仓位限制** 和 **资金检查**，资金不够会自动拒绝

---

## 步骤 3：运行回测

```python
from qka.core.backtest import Backtest

bt = Backtest(data, BuyAndHold())
bt.run(benchmark='000300.SH')   # 对比沪深300
```

`bt.run()` 会：
1. 按日期遍历所有数据
2. 每天调用策略的 `on_bar` 方法
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
# 自动保存到 examples/charts/ 下
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
from qka.core.data import Data
from qka.core.strategy import Strategy
from qka.core.broker import Broker
from qka.core.backtest import Backtest

class BuyAndHold(Strategy):
    def __init__(self):
        super().__init__(cash=100_000)
        self.broker = Broker(initial_cash=100_000)
        self.bought = False

    def on_bar(self, date, get):
        close = get('close')
        if not self.bought and '000001.SZ' in close.index:
            self.broker.buy('000001.SZ', float(close['000001.SZ']), 100)
            self.bought = True

data = Data(symbols=['000001.SZ'])
bt = Backtest(data, BuyAndHold())
bt.run(benchmark='000300.SH')
bt.summary()
bt.report(title='买入持有策略')
```

---

## 下一步

- 学习 [回测分析](../user-guide/backtest.md) — 手续费设置、绩效指标详解
- 了解 [核心概念](concepts.md) — 架构设计、数据流
- 查看 [API 参考](../api/core.md) — 完整接口说明
