# qka.Analysis

量化分析与统计模块。

```python
from qka import Analysis
```

---

## 构造函数

```python
Analysis()
```
无参数。

---

## 方法

### `zigzag(series, threshold=0.3, min_days=90, lamb=1600) -> list[Segment]`

HP 滤波 + Zigzag 趋势分段识别。

::: danger 警告
包含未来函数，仅供事后分析与市场风格划分，**严禁放入策略实盘/回测买卖信号**。
:::

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `series` | `pd.Series` | 必填 | 价格序列（索引为日期，值为价格） |
| `threshold` | `float` | `0.3` | 反转确认阈值（如 `0.3` 表示回落 30% 确认顶，反弹 30% 确认底） |
| `min_days` | `int` | `90` | 最小段长（自然日），短于此的波动将被平滑吸收 |
| `lamb` | `int` | `1600` | HP 滤波平滑参数（日线标准建议 1600） |

**返回值**：`list[Segment]`，每个 `Segment` 是包含以下字段的 namedtuple：
- `start` (`pd.Timestamp`): 段起始日期
- `end` (`pd.Timestamp`): 段结束日期
- `direction` (`str`): `'上行'` 或 `'下行'`
- `change` (`float`): 段内累计涨跌幅百分比

---

### `alpha_beta(returns, bench_returns, rf=0.0, periods_per_year=252) -> AlphaBeta`

基于 OLS 回归计算年化詹森 $\alpha$ 与 $\beta$。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `returns` | array-like | 必填 | 资产日收益率序列 |
| `bench_returns` | array-like | 必填 | 基准日收益率序列 |
| `rf` | `float` | `0.0` | 年化无风险利率 |
| `periods_per_year` | `int` | `252` | 年化周期数（日线=252） |

**返回值**：`AlphaBeta` namedtuple：
- `alpha` (`float`): 年化超额收益率 $\alpha$
- `beta` (`float`): 市场敏感度 $\beta = \frac{\text{Cov}(R_p, R_m)}{\text{Var}(R_m)}$

---

### `sharpe_ratio(returns, rf=0.0, periods_per_year=252) -> float`

计算年化夏普比率。

$$\text{Sharpe} = \frac{\text{mean}(R_p) - R_{f,\text{period}}}{\text{std}(R_p)} \times \sqrt{N}$$

---

### `max_drawdown(returns) -> float`

计算收益率序列的最大历史回撤幅度（正数，如 `0.35` 代表 35% 回撤）。

---

### `information_ratio(returns, bench_returns, periods_per_year=252) -> float`

计算年化信息比率（Information Ratio）。

$$\text{IR} = \frac{\text{mean}(R_p - R_m)}{\text{std}(R_p - R_m)} \times \sqrt{N}$$
