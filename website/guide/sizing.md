# 仓位算法 (Sizing)

量化交易界有一句名言：“**择时决定输赢，仓位管理决定生死。**”

在实际回测和实盘中，直接手动计算买入股数极其容易出现两大问题：
1. **碎股问题**：计算结果出现 `153` 股，违反 A 股最小 100 股一手整倍数规则。
2. **穿仓/超支拒单**：计算买入股数时忽略了佣金与滑点，导致向券商下单时总费用超出账户可用现金，触发拒单。

QKA 将仓位管理提升为一等公民，提供 `SizingAccessor`（挂载在 `self.sizing`），**所有算法均已自动向下按 100 股一手取整，且内置费用与滑点预留机制**。

---

## 核心仓位算法一览

| 方法 | 说明 | 适用场景 |
|------|------|----------|
| `percent(ratio, price)` | 按可用现金比例计算股数 | 资金动态分配、多标的均衡配置 |
| `fixed_amount(amount, price)` | 按固定金额上限计算股数 | 定投策略、小额试单、网格交易 |
| `fixed_shares(n)` | 固定股数，自动一手整除 | 单一标的固定手数测试 |
| `atr_risk(risk_ratio, price, atr, multiplier)` | 基于波动率 ATR 的固定风险比例模型 | 海龟交易法则、趋势跟踪波动率平价 |
| `kelly(win_rate, win_loss_ratio, price)` | 经典凯利公式最优下注比例 | 高胜率或高赔率成熟策略的最优资金利用 |

---

## 1. 资金百分比模型 (`percent`)

使用可用现金的 `ratio`（0 ~ 1）比例买入：

```python
# 动用当前可用现金的 20%
size = self.sizing.percent(ratio=0.2, price=price)
if size > 0:
    self.broker.buy(sym, price, size)
```

::: tip 预留费用安全设计
当设置 `ratio=1.0`（满仓买入）时，`self.sizing.percent` 不会天真地以 `cash / price` 计算，而是先以含滑点价格初算，再动态调用 Broker 预估总成本（含佣金最低 5 元），若超出预算则自动减去 1 手（100 股），保证百分之百不会因为佣金不足被拒单！
:::

---

## 2. 固定金额模型 (`fixed_amount`)

指定投入金额上限（如每次定投 10,000 元）：

```python
size = self.sizing.fixed_amount(amount=10000.0, price=price)
if size > 0:
    self.broker.buy(sym, price, size)
```

同样自动预留滑点与佣金，确保 `成交额 + 佣金 <= amount`。

---

## 3. 固定股数模型 (`fixed_shares`)

指定买入股数，自动向下按 100 股取整（若不足 100 股则返回 0）：

```python
size = self.sizing.fixed_shares(350)  # 返回 300 股
```

---

## 4. ATR 风险平价模型 (`atr_risk`)

源自经典**海龟交易法则（Turtle Trading）**。该模型根据标的近期波动幅度（ATR）反推仓位：波动剧烈时减少股数，波动平缓时放大股数，确保单笔止损所承受的资金损失恒定在 `risk_ratio` 比例内。

$$\text{Risk per Share} = \text{ATR} \times \text{multiplier}$$
$$\text{Shares} = \left\lfloor \frac{\text{Cash} \times \text{risk\_ratio}}{\text{Risk per Share}} \right\rfloor_{100}$$

```python
# 假设当前可用现金 100,000，限制单笔最大风险暴露为 1%（1000元），止损位设为 2 倍 ATR
atr_value = float(self.get('atr_14')[sym])

size = self.sizing.atr_risk(
    risk_ratio=0.01,
    price=price,
    atr_value=atr_value,
    multiplier=2.0
)
```

---

## 5. 凯利公式 (`kelly`)

根据策略历史表现统计的胜率与盈亏比，计算数学期望最大化的理论下注比例：

$$f^* = \frac{p \cdot b - q}{b}$$

其中 $p$ 为胜率，$b$ 为盈亏比（平均盈利/平均亏损），$q = 1 - p$ 为败率。当 $f^* \le 0$ 时说明期望收益为负，函数返回 0（不下注）。

```python
# 假设策略胜率 55%，盈亏比 1.8
size = self.sizing.kelly(win_rate=0.55, win_loss_ratio=1.8, price=price)
```
