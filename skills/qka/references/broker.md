## Broker

虚拟券商，由 `Backtest.run()` 在执行时创建并注入到 `strategy.broker`。用户不直接构造。

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `broker.cash` | `float` | 当前可用现金 |
| `broker.positions` | `dict` | `{symbol: {'size': int, 'avg_price': float}}` |

### buy()

`buy(symbol: str, price: float, size: int) → bool`

买入，`size` 必须是 100 的整数倍（A 股 1 手 = 100 股）。

```python
success = self.broker.buy('sz.000001', float(close['sz.000001']), 100)
```

- 实际成交价 = `price * (1 + slippage)`（默认滑点 0.1%）
- 自动扣佣金（万 2.5，最低 5 元）
- 资金不足返回 `False`
- `price <= 0` 返回 `False`（前复权可能导致早期价格为负）

### sell()

`sell(symbol: str, price: float, size: int) → bool`

卖出，`size` 必须是 100 的整数倍。

```python
success = self.broker.sell('sz.000001', float(close['sz.000001']), 100)
```

- 自动扣佣金 + 印花税（万 5，仅卖出）
- 持仓不足返回 `False`
