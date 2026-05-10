# 仓位

固定股数（如 100 股）无法适配不同资金规模。`self.sizing` 根据可用资金自动计算合理买入股数。

---

## 方法一览

| 方法 | 适用场景 |
|------|---------|
| `percent(ratio, price)` | 按可用资金比例买入 |
| `fixed_amount(amount, price)` | 每月固定金额定投 |
| `fixed_shares(n)` | 固定股数，自动按手取整 |
| `atr_risk(risk_ratio, price, atr)` | 波动率自适应仓位 |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率时的最优下注 |

---

## percent — 比例仓位

最常用的方式。用可用资金的一定比例买入：

```python
size = self.sizing.percent(0.1, price)
# 可用资金 10 万，price=10 → 1000 股
# 可用资金 1 万，price=10 → 100 股
```

## fixed_amount — 固定金额

适合定投场景，每次投入固定金额：

```python
size = self.sizing.fixed_amount(5000, price)
# price=10 → 500 股
```

## fixed_shares — 固定股数

```python
size = self.sizing.fixed_shares(100)
# 返回 100（现金充足时），不足时返回 0
```

## atr_risk — ATR 风控

根据波动率动态调整仓位。ATR 较大时减少买入股数，ATR 较小时增加：

```python
atr = float(self.get('atr_14')[sym])
size = self.sizing.atr_risk(0.02, price, atr)
```

ATR=0.5：`10万 × 2% / (0.5 × 2) = 2000 股`
ATR=1.0：`10万 × 2% / (1.0 × 2) = 1000 股`

波动率翻倍时仓位自动减半。

## kelly — 凯利公式

适合有历史统计数据的场景：

```python
size = self.sizing.kelly(0.6, 2.0, price)
# 胜率 60%，赔率 2，f* = (0.6×2 - 0.4)/2 = 0.4 → 40% 仓位
```

计算结果 ≤ 0 时返回 0（不下注）。

---

## 注意事项

**基于可用现金计算**，不含持仓市值。如需基于总资产：

```python
total = self.broker.cash
for sym, pos in self.broker.positions.items():
    total += pos['size'] * pos['cost_basis']
```

- ATR 为 0 时返回 0（新股或一字板）
- 价格必须大于 0，前复权可能出现负价格，此时不交易
