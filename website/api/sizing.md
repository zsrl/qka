# qka.SizingAccessor

仓位计算工具类，挂载在 `strategy.sizing`。

所有方法**均严格按 A 股一手（100 股）向下取整**，并已预先考虑滑点与手续费，确保计算出的股数在执行 `broker.buy()` 时不会因费用超支拒单。

```python
# 通常由 Backtest 注入到 self.sizing，无需自行实例化
```

---

## 方法一览

### `percent(ratio: float, price: float) -> int`

使用可用现金的 `ratio`（0.0 ~ 1.0）比例买入。

- **`ratio`** (`float`): 比例，如 `0.2` 表示 20%。
- **`price`** (`float`): 每股价格。
- **返回值** (`int`): 可买入股数（100 的整数倍）。若现金不足 1 手则返回 `0`。

```python
size = self.sizing.percent(0.2, price=9.5)
```

---

### `fixed_amount(amount: float, price: float) -> int`

按固定投入金额上限计算可买入股数。

- **`amount`** (`float`): 投入金额上限（含费用与滑点）。
- **`price`** (`float`): 每股价格。
- **返回值** (`int`): 可买入股数（100 的整数倍）。

```python
size = self.sizing.fixed_amount(20000.0, price=9.5)
```

---

### `fixed_shares(n: int) -> int`

固定股数转换。若 `n` 不足 100 股返回 0，否则向下截断到最接近的 100 整倍数。

- **`n`** (`int`): 计划股数。
- **返回值** (`int`): 取整后的合法股数。

```python
size = self.sizing.fixed_shares(480)  # 返回 400
```

---

### `atr_risk(risk_ratio: float, price: float, atr_value: float, multiplier: float = 2.0) -> int`

海龟 ATR 风险平价仓位。确保单笔交易触发止损（`multiplier * ATR`）时的损失不超过当前账户可用现金的 `risk_ratio` 比例。

$$\text{Shares} = \left\lfloor \frac{\text{Cash} \times \text{risk\_ratio}}{\text{atr\_value} \times \text{multiplier}} \right\rfloor_{100}$$

- **`risk_ratio`** (`float`): 0.0 ~ 1.0 单笔最大亏损占可用现金的比例。
- **`price`** (`float`): 每股价格。
- **`atr_value`** (`float`): 当前 ATR（真实波幅均值）数值。
- **`multiplier`** (`float`, 默认 `2.0`): 止损倍数。
- **返回值** (`int`): 可买入股数（100 的整数倍）。

```python
size = self.sizing.atr_risk(risk_ratio=0.01, price=price, atr_value=atr, multiplier=2.0)
```

---

### `kelly(win_rate: float, win_loss_ratio: float, price: float) -> int`

经典凯利公式（Kelly Criterion）计算理论最优买入股数。

$$f^* = \frac{p \cdot b - q}{b}$$

- **`win_rate`** (`float`): 胜率 $p$（0.0 ~ 1.0）。
- **`win_loss_ratio`** (`float`): 盈亏比 $b$（平均盈利 / 平均亏损）。
- **`price`** (`float`): 每股价格。
- **返回值** (`int`): 建议买入股数（100 的整数倍），当 $f^* \le 0$ 时返回 `0`。

```python
size = self.sizing.kelly(win_rate=0.55, win_loss_ratio=1.5, price=price)
```
