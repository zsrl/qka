# 仓位管理

写死 "买入 100 股" 太粗糙了。你手里 10 万和 100 万，买的股数应该不一样。

`self.sizing` 帮你算"该买多少股"，按你的资金和规则自动算。

---

## 有什么方法

### 1. `percent(ratio, price)` — 按比例

最常用。用**可用资金**的一定比例买入。

```python
size = self.sizing.percent(0.1, price)
# 可用资金 10 万，price=10，买入 1000 股
# 可用资金 1 万，price=10，买入 100 股
```

### 2. `fixed_amount(amount, price)` — 固定金额

每月定投 5000 块的场景：

```python
size = self.sizing.fixed_amount(5000, price)
# price=10，买入 500 股（5000/10=500）
```

### 3. `fixed_shares(n)` — 固定股数

就像写死 100 股一样，但自动按手取整：

```python
size = self.sizing.fixed_shares(100)
# 返回 100（如果 cash 够买的话）
```

### 4. `atr_risk(risk_ratio, price, atr[, multiplier])` — 波动率控险

根据 ATR（平均真实波幅）自动调节仓位。波动大的时候少买，波动小的时候多买。

```python
# 每笔亏损不超过总资金的 2%
atr = float(self.get('atr_14')[sym])   # ATR 需要预计算
size = self.sizing.atr_risk(0.02, price, atr)
```

ATR=0.5，multiplier=2 的时候：`10万 × 2% / (0.5 × 2) = 2000 股`
ATR=1.0，multiplier=2 的时候：`10万 × 2% / (1.0 × 2) = 1000 股`

波动翻倍，仓位减半——自动的。

### 5. `kelly(win_rate, wl_ratio, price)` — 凯利公式

知道历史胜率和赔率的时候，算最优下注比例。

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6×2 - 0.4)/2 = 0.4 → 40% 仓位
```

如果公式结果 ≤ 0（说明不该下注），返回 0。

---

## 什么时候用哪个

| 方法 | 适合的场景 |
|------|-----------|
| `percent` | 大多数情况，按比例分配资金 |
| `fixed_amount` | 定投、每月固定金额买入 |
| `fixed_shares` | 测试用、手工算好股数 |
| `atr_risk` | 想做波动率自适应仓位，有止损逻辑 |
| `kelly` | 有历史回测统计的胜率和赔率 |

---

## 需要注意的

**只算可用资金。** 所有方法都是基于 `broker.cash`（账户里还剩多少钱）算的，不包括已经持仓的市值。

```python
# 如果想基于总资产（现金+持仓市值）
total = self.broker.cash
for sym, pos in self.broker.positions.items():
    total += pos['size'] * pos['cost_basis']
# 再手动算比例
```

**ATR 为 0 时返回 0。** 新股或一字板时 ATR 可能是 0，这时候不买。

**价格必须 > 0。** 配股、除权可能导致前复权价格为负，这时不交易。
