# qka.Simulate

现场行情合成引擎，用于生成特定几何特性的虚拟行情。

```python
from qka import Simulate
```

---

## 构造函数

```python
Simulate(
    symbol: str,
    drift: float = 0.0,
    reversion: float = 0.0,
    vol: float = 0.012,
)
```

### 参数说明

| 参数 | 类型 | 默认值 | 约束 | 说明 |
|------|------|--------|------|------|
| `symbol` | `str` | 必填 | 不能为空 | 标的代码标识符（如 `'sim.bull'`、`'sim.test'`），作为 DataFrame 列的前缀 |
| `drift` | `float` | `0.0` | 无限制 | 日漂移率 $\mu$。正数=上涨趋势，负数=下跌趋势，`0.0`=无方向 |
| `reversion` | `float` | `0.0` | $\ge 0$ | 均值回复强度 $\theta$。越大越围绕初始价格中枢震荡，为 `0.0` 时不回复 |
| `vol` | `float` | `0.012` | $> 0$ | 日波动率标准差 $\sigma$。例如 `0.015` 对应单日波动约 1.5% |

---

## 数学公式

序列按对数价格推进演化：

$$r_t = \text{drift} + \text{reversion} \times (\log P_{\text{anchor}} - \log P_{t-1}) + \text{vol} \times \epsilon_t, \quad \epsilon_t \sim \mathcal{N}(0, 1)$$

- **半衰期**：当 `reversion > 0` 时，价格偏离中枢回复一半所需的天数：
  $$T_{1/2} = \frac{\ln 2}{\text{reversion}}$$

---

## 使用范例

```python
from qka import Data, Simulate

data = Data(symbols=[
    '600000.SH',                                               # 真实标的
    Simulate('sim.bull', drift=0.002, reversion=0.0, vol=0.01), # 单边上涨
    Simulate('sim.bear', drift=-0.002, reversion=0.0, vol=0.01),# 单边下跌
    Simulate('sim.mean_rev', reversion=0.08, vol=0.02),        # 均值回归中枢震荡
])
df = data.get('2024-01-01', '2024-12-31')
```
