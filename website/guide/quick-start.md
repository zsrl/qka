# 快速上手

本章节将带领你从安装 QKA 开始，在 5 分钟内完成一个经典的 **双均线动量择时策略**，并生成专业的可视化回测报告。

---

## 环境准备与安装

QKA 需要 **Python 3.10** 及以上版本。

### 1. 安装 Python 包

```bash
pip install qka
```

### 2. 为 AI 编程工具安装技能（强烈推荐）

如果你使用 **Claude Code**、**Cursor**、**Windsurf** 等具备技能扩展的 AI 编程助手，建议在项目目录下执行：

```bash
npx skills add zsrl/qka
```

安装后，AI 助手将自动加载 QKA 框架的完整接口规范与设计约束，生成符合最佳实践的量化代码。

---

## 5 分钟构建首个策略

量化回测通常由三个阶段构成：**准备数据** $\rightarrow$ **定义策略** $\rightarrow$ **执行回测**。

### 第一步：准备数据 (`qka.Data`)

创建 `Data` 对象，声明你要研究的标的股票列表，以及需要预计算的技术指标。

```python
from qka import Data

# 声明标的与预计算技术指标
data = Data(
    symbols=['000001.SZ'],  # 平安银行（支持 000001.SZ 或 sz.000001）
    adjust='qfq',            # 前复权（回测默认推荐）
    factors={
        'sma_5':  ('ta.trend.sma_indicator', 'close', 5),   # 5 日短期均线
        'sma_20': ('ta.trend.sma_indicator', 'close', 20),  # 20 日长期均线
    },
)
```

> **提示**：调用 `Data(...)` 时并不会立即下载全量历史数据，只有在调用 `data.get()` 或传入 `Backtest` 启动时才会按需下载并落盘缓存。二次执行将直接秒级读取本地缓存。

---

### 第二步：编写策略 (`qka.Strategy`)

继承 `qka.Strategy`，并在 `on_bar(self, date)` 方法中编写核心交易逻辑。

```python
from qka import Strategy

class DualMaStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.pct = 0.2  # 每次买入占用当前可用现金的 20%

    def on_bar(self, date):
        # 1. 获取当前交易日全标的横截面数据
        close = self.get('close')
        fast = self.get('sma_5')
        slow = self.get('sma_20')

        for sym in close.index:
            price = float(close[sym])
            if price <= 0:
                continue

            # 2. 交易逻辑判断：短期均线上穿长期均线（金叉）买入
            if fast[sym] > slow[sym]:
                # 使用内置仓位计算器，自动按手（100 股）向下取整
                size = self.sizing.percent(self.pct, price)
                if size > 0:
                    self.broker.buy(sym, price, size)

            # 3. 短期均线下穿长期均线（死叉）平仓
            else:
                pos = self.broker.positions.get(sym, {}).get('size', 0)
                if pos > 0:
                    self.broker.sell(sym, price, pos)
```

::: tip 策略核心规范
- **`__init__`**：必须调用 `super().__init__()`，不要传递参数。
- **`on_bar(self, date)`**：参数只有 `self` 和 `date`（字符串 `'YYYY-MM-DD'`）。
- **`self.get('factor')`**：返回一个 `pd.Series`，索引为股票代码，值为该因子在当天的数值。
- **`self.sizing` 与 `self.broker`**：无需手动实例化，回测引擎在启动时会自动注入。
:::

---

### 第三步：启动回测与查看绩效 (`qka.Backtest`)

将 `data` 和策略实例传入 `Backtest`，调用 `run()` 即可完成回测。

```python
from qka import Backtest

# 实例化策略与回测引擎
strategy = DualMaStrategy()
bt = Backtest(data, strategy)

# 启动回测：初始资金 20 万，起始日期 2023-01-01，对比沪深 300 基准
bt.run(
    cash=200000,
    start_date='2023-01-01',
    end_date='2024-12-31',
    benchmark='000300.SH'
)

# 打印核心绩效指标
print("=== 回测绩效报告 ===")
print(f"总收益率:     {bt.metrics['total_return_pct']:.2%}")
print(f"年化收益率:   {bt.metrics['annual_return_pct']:.2%}")
print(f"夏普比率:     {bt.metrics['sharpe_ratio']:.2f}")
print(f"最大回撤:     {bt.metrics['max_drawdown_pct']:.2%}")
print(f"胜率:         {bt.metrics['win_rate_pct']:.2%}")
print(f"交易笔数:     {bt.metrics['total_trades']}")
```

---

### 第四步：输出交互式 HTML 诊断大屏

只需调用 `bt.report()`，即可将回测结果导出为包含 Plotly 动态交互图表的自包含 HTML 报告：

```python
bt.report(output='backtest_report.html', open_browser=True)
```

报告将自动在默认浏览器中打开，包含：
- 📈 **净值走势与基准对比曲线**
- 📉 **动态水下回撤曲线与主要回撤区间定位**
- 🗓️ **月度收益率热力图矩阵**
- 📋 **逐笔成交流水与持仓分析**

---

## 完整可运行代码

新建一个 `demo.py` 文件并粘贴以下内容即可直接运行：

```python
from qka import Data, Strategy, Backtest

def run_quickstart():
    # 1. 准备数据
    data = Data(
        symbols=['000001.SZ'],
        adjust='qfq',
        factors={
            'sma_5':  ('ta.trend.sma_indicator', 'close', 5),
            'sma_20': ('ta.trend.sma_indicator', 'close', 20),
        },
    )

    # 2. 策略定义
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

    # 3. 运行回测
    strategy = MaCross()
    bt = Backtest(data, strategy)
    bt.run(cash=200000, start_date='2023-01-01', benchmark='000300.SH')

    print(f"回测完成！总收益率: {bt.metrics['total_return_pct']:.2%}, 夏普: {bt.metrics['sharpe_ratio']:.2f}")

    # 4. 生成报告
    bt.report('report.html')
    print("报告已生成: report.html")

if __name__ == '__main__':
    run_quickstart()
```
