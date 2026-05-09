# 仓位

写死"买入 100 股"太粗糙了。`self.sizing` 帮你算该买多少，按你的资金自动算。

---

## 方法一览

| 方法 | 适合场景 |
|------|---------|
| `percent(ratio, price)` | 按可用资金比例买入 |
| `fixed_amount(amount, price)` | 定投，每月固定金额 |
| `fixed_shares(n)` | 固定股数，自动按手取整 |
| `atr_risk(risk_ratio, price, atr)` | 波动率自适应仓位 |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率时最优下注 |

---

## percent — 按比例

最常用。用可用资金的一定比例买入：

```python
size = self.sizing.percent(0.1, price)
# 可用 10 万，price=10，买入 1000 股
# 可用 1 万，price=10，买入 100 股
```

## fixed_amount — 固定金额

每月定投 5000 块：

```python
size = self.sizing.fixed_amount(5000, price)
# price=10，买入 500 股
```

## fixed_shares — 固定股数

```python
size = self.sizing.fixed_shares(100)
# 返回 100（如果现金够买的话）
```

## atr_risk — ATR 风控

根据波动率自动调节仓位。ATR 大时少买，ATR 小时多买：

```python
atr = float(self.get('atr_14')[sym])
size = self.sizing.atr_risk(0.02, price, atr)
```

ATR=0.5：`10万 × 2% / (0.5 × 2) = 2000 股`
ATR=1.0：`10万 × 2% / (1.0 × 2) = 1000 股`

波动翻倍，仓位减半——自动的。

## kelly — 凯利公式

```python
size = self.sizing.kelly(0.6, 2.0, price)
# 胜率 60%，赔率 2，f* = (0.6×2 - 0.4)/2 = 0.4 → 40% 仓位
```

结果 ≤ 0 时返回 0（不该下注）。

---

## 注意事项

**基于可用现金计算**，不包括持仓市值。如果想基于总资产：

```python
total = self.broker.cash
for sym, pos in self.broker.positions.items():
    total += pos['size'] * pos['cost_basis']
```

**ATR 为 0 时返回 0**（新股或一字板）。**价格必须 > 0**，前复权可能出现负价格，这时不交易。
