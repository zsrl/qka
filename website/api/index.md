# API 概览与速查

QKA 框架遵循“少即是多”的 API 设计哲学，全框架仅包含 **7 个核心公开类**。

---

## 核心类一览

| 类名 | 完整引入路径 | 核心职责 | 详细文档 |
|------|--------------|----------|----------|
| **Data** | `from qka import Data` | 负责多源行情获取、缓存落盘与因子向量化预计算 | [查看 API](/api/data) |
| **Simulate** | `from qka import Simulate` | 现场合成单边上涨/下跌/震荡行情，用于逻辑白盒测试 | [查看 API](/api/simulate) |
| **Strategy** | `from qka import Strategy` | 策略抽象基类，实现 `on_bar(self, date)` 核心方法 | [查看 API](/api/strategy) |
| **Broker** | `qka.core.broker.Broker` | 虚拟券商，管理账户资金、持仓并执行带税费滑点的撮合 | [查看 API](/api/broker) |
| **SizingAccessor** | `qka.core.sizing.SizingAccessor` | 仓位算法工具（挂载在 `strategy.sizing`），全部自动按手取整 | [查看 API](/api/sizing) |
| **Backtest** | `from qka import Backtest` | 回测引擎，调度推进时间流并生成绩效度量与报告 | [查看 API](/api/backtest) |
| **Analysis** | `from qka import Analysis` | 常用分析工具，提供 Zigzag 趋势分段、OLS $\alpha/\beta$ 与夏普度量 | [查看 API](/api/analysis) |

---

## 快速速查表

```python
# 1. 数据准备
data = Data(
    symbols=['000001.SZ', '600000.SH'],
    source='tickflow',                  # 'tickflow' / 'baostock' / 'tdx'
    adjust='qfq',                       # 'qfq' / 'hfq' / 'bfq'
    factors={
        'sma_5':  ('ta.trend.sma_indicator', 'close', 5),
        'rsi_14': ('ta.momentum.rsi', 'close', 14),
    },
    warmup=20
)

# 2. 策略定义
class MyStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.param = 0.2

    def on_bar(self, date):
        close = self.get('close')       # 当日横截面 pd.Series
        hist = self.history('close', 20)# 过去 20 天滑动窗口 pd.DataFrame
        price = float(close['000001.SZ'])
        if price > 0:
            size = self.sizing.percent(self.param, price)
            if size > 0:
                self.broker.buy('000001.SZ', price, size)

# 3. 回测运行
bt = Backtest(data, MyStrategy())
bt.run(cash=100000, start_date='2024-01-01', benchmark='000300.SH')

# 4. 绩效与大屏
print(bt.metrics['total_return_pct'])
bt.report(title="策略报告", output_path="report.html")

# 5. 分析工具
analysis = Analysis()
sr = analysis.sharpe_ratio(bt.results['total'].pct_change().dropna())
```
