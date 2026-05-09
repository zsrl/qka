# 回测

写好了策略，准备数据，用 `Backtest` 跑起来。

---

## 一句话

```python
from qka import Backtest

bt = Backtest(data, MyStrategy())
bt.run(benchmark='000300.SH')
```

就两行。`Backtest` 的参数：

| 参数 | 说明 |
|------|------|
| `data` | Data 实例 |
| `strategy` | 策略实例（可在构造函数传 cash 等参数） |

## run

```python
bt.run(benchmark='000300.SH')   # 带沪深 300 对比
```

做的事：按时间排序数据 → 每天调 `on_bar(date)` → 记录资产变化 → 下载基准数据。

几百只股票跑 5 年？QKA 默认分批算，不会一次加载所有数据到内存。

## 看结果

`summary()` 看终端概览，`report()` 看 HTML 报告。详见[报告](report.md)。

## benchmark

A 股最常用沪深 300：

```python
bt.run(benchmark='000300.SH')
```

加了之后，summary 和 report 里会多出超额收益、超额夏普等指标。
