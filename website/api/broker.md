# qka.Broker

虚拟交易经纪商类，负责交易撮合、资金结算与持仓管理。

```python
# 通常由 Backtest 自动注入到 self.broker，无需自行实例化
```

---

## 核心属性

| 属性名 | 类型 | 说明 |
|--------|------|------|
| `cash` | `float` | 当前账户可用现金余额（元） |
| `positions` | `dict` | 当前持仓字典：`{symbol: {'size': int, 'avg_price': float}}` |
| `commission_rate` | `float` | 佣金费率，默认万 2.5 (`0.00025`) |
| `stamp_duty_rate` | `float` | 印花税率，默认万 5 (`0.0005`)，仅卖出时收取 |
| `slippage` | `float` | 滑点比率，默认 0.1% (`0.001`) |
| `total_commission` | `float` | 累计扣除的佣金总额 |
| `total_stamp_duty` | `float` | 累计扣除的印花税总额 |
| `total_slippage_cost` | `float` | 累计滑点带来的摩擦成本 |
| `trades` | `pd.DataFrame` | 逐日资金与权益历史流水快照 |
| `trade_history` | `list[dict]` | 逐笔交易成交明细流水列表 |

---

## 交易执行方法

### `buy(symbol: str, price: float, size: int) -> bool`

买入操作。考虑买入滑点（价格上浮 `1 + slippage`）与佣金（最低 5 元起）。

- **`symbol`**：标的代码（如 `'000001.SZ'`）。
- **`price`**：基准委托价格。
- **`size`**：买入股数，**必须为 100 的整数倍且大于 0**。
- **返回值**：`bool`，买入成功返回 `True`，资金不足或参数非法返回 `False`。

```python
ok = self.broker.buy('000001.SZ', price=10.0, size=500)
```

---

### `sell(symbol: str, price: float, size: int) -> bool`

卖出操作。考虑卖出滑点（价格下浮 `1 - slippage`）、佣金（最低 5 元起）与卖出印花税（万 5）。

- **`symbol`**：标的代码。
- **`price`**：基准委托价格。
- **`size`**：卖出股数，**必须为 100 的整数倍且大于 0**。
- **返回值**：`bool`，卖出成功返回 `True`，持仓不足或参数非法返回 `False`。

```python
ok = self.broker.sell('000001.SZ', price=11.2, size=500)
```

---

### `estimate_buy_cost(price: float, size: int) -> float`

预估买入指定股数所需的总成本（含滑点上浮与最低 5 元佣金）。

- **`price`**：市价。
- **`size`**：拟买入股数。
- **返回值**：预估所需总花费。

---

### `get(factor: str, timestamp=None) -> Any`

从 `trades` DataFrame 历史流水中查询特定字段（`'cash'`, `'value'`, `'total'`, `'positions'`, `'trades'`）。
