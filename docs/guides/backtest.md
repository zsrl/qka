# 回测

使用 `Backtest` 运行策略并获取回测结果。

---

## 基本用法

```python
from qka import Backtest

bt = Backtest(data, MyStrategy())
bt.run(benchmark='000300.SH')
```

`Backtest` 的参数：

| 参数 | 说明 |
|------|------|
| `data` | Data 实例 |
| `strategy` | 策略实例（可在构造函数中传入 cash 等参数） |

## run 方法

```python
bt.run(benchmark='000300.SH')   # 带沪深 300 基准对比
```

执行流程：按时间排序数据 → 逐日调用 `on_bar(date)` → 记录每日资产变化 → 下载基准数据。

大规模回测（数百只股票、数年数据）时，QKA 采用分批计算策略，避免一次性加载全部数据到内存。

## 查看结果

- `summary()` — 终端输出绩效指标
- `report()` — 生成 HTML 报告

详见[报告](report.md)。

## 基准对比

A 股最常使用沪深 300 指数：

```python
bt.run(benchmark='000300.SH')
```

启用基准后，summary 和 report 中会增加超额收益、超额夏普等指标。
