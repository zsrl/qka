# Backtest 模块

回测引擎，管理策略生命周期和数据加载流程。

## 用法

```python
from qka import Data, Backtest

data = Data(symbols=['000001.SZ'], indicators={'sma_5': ('sma', 5)})
bt = Backtest(data, MyStrategy(cash=100000))
bt.run(benchmark='000300.SH')   # 沪深300 为基准
```

- `data`: Data 实例（已配置 symbol 和 indicators）
- `MyStrategy(cash=...)`: 策略实例，cash 为初始资金
- `benchmark`: 基准指数代码，如 `'000300.SH'`（沪深300）、`'000001.SH'`（上证）

## Backtest 参数

```python
bt = Backtest(
    data,                         # Data 实例
    strategy,                     # Strategy 实例
    start_date='2023-01-01',      # 可选，数据过滤起始
    end_date='2024-12-31',        # 可选，数据过滤结束
)
```

## 回测结果

### summary() -> dict

```python
metrics = bt.summary()
```

返回的字典包含：
- `总收益率` — 策略总收益百分比
- `年化收益率` — 年化收益率
- `最大回撤` — 最大回撤百分比（负值）
- `夏普比率` — 年化夏普比率
- `胜率` — 盈利交易占比
- `交易次数` — 总交易笔数
- `benchmark_收益` — 基准总收益百分比
- `benchmark_年化` — 基准年化收益率

### report(output_path) -> str

```python
report_path = bt.report()                         # 默认 ./reports/
report_path = bt.report(output_path='my_rpt.html') # 指定路径
```

生成 Plotly HTML 报告，包含：
- 累计收益率曲线（含 benchmark）
- 每日收益率柱状图
- 最大回撤曲线
- 月度收益率热力图
- 交易记录表
- 换手率
- 综合指标面板

## 完整回测流程

```python
from qka import Data, Strategy, Backtest

class MyStrategy(Strategy):
    def on_bar(self, date):
        close = self.get('close')
        for sym in close.index:
            price = float(close[sym])
            if price <= 0:
                continue
            if sym not in self.broker.positions:
                size = self.sizing.percent(0.1, price)
                if size >= 100:
                    self.broker.buy(sym, price, size)

data = Data(symbols=['000001.SZ', '600000.SH'])
bt = Backtest(data, MyStrategy(cash=100000))
bt.run(benchmark='000300.SH')
print(bt.summary())
bt.report()
```
