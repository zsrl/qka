## SizingAccessor

仓位计算器，由 `Backtest.run()` 在执行时创建并注入到 `strategy.sizing`。返回值已按手取整（100 的倍数）。

| 方法 | 说明 |
|------|------|
| `percent(ratio, price)` | 用可用现金的 `ratio` 比例买入。`ratio` 在 0~1 之间 |
| `fixed_amount(amount, price)` | 固定金额买入 |
| `fixed_shares(n)` | 固定股数 |
| `atr_risk(risk_ratio, price, atr_value, multiplier=2.0)` | ATR 风险仓位 |

```python
price = float(close['sz.000001'])
size = self.sizing.percent(0.1, price)  # 10% 仓位，已按手取整
if size > 0:
    self.broker.buy('sz.000001', price, size)
```
