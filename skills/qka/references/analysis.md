## Analysis

分析模块，收纳常用的分析方法。

### 导入

```python
from qka import Analysis
```

构造无参数：

```python
analysis = Analysis()
```

### zigzag()

`zigzag(series, threshold=0.3, min_days=90, lamb=1600) → list[Segment]`

HP 滤波 + Zigzag 趋势分段。对价格序列做 Hodrick–Prescott 滤波去噪后，在趋势线上识别交替的上行/下行段。

⚠️ 包含未来函数，仅供事后分析，禁止用于回测策略。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `series` | `pd.Series` | 必填 | 价格序列，index 为日期，values 为价格 |
| `threshold` | `float` | `0.3` | 反转阈值。峰顶回落 30% 确认顶，谷底反弹 30% 确认底 |
| `min_days` | `int` | `90` | 最小段长（自然日）。短于此的段被前后段合并吸收 |
| `lamb` | `int` | `1600` | HP 滤波平滑参数，日线数据标准值 |

返回值 `list[Segment]`，每个 `Segment` 是 namedtuple：

| 字段 | 类型 | 说明 |
|------|------|------|
| `start` | `pd.Timestamp` | 段起始日期 |
| `end` | `pd.Timestamp` | 段结束日期 |
| `direction` | `str` | `'上行'` 或 `'下行'` |
| `change` | `float` | 段内涨跌幅（百分比） |

### alpha_beta()

`alpha_beta(returns, bench_returns, rf=0.0, periods_per_year=252) → AlphaBeta`

OLS 回归，一次返回 α 和 β。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `returns` | array-like | 必填 | 资产收益率序列 |
| `bench_returns` | array-like | 必填 | 基准收益率序列 |
| `rf` | `float` | `0.0` | 年化无风险利率 |
| `periods_per_year` | `int` | `252` | 年化周期数，日线=252，周线=52 |

返回值 `AlphaBeta` namedtuple：

| 字段 | 类型 | 说明 |
|------|------|------|
| `alpha` | `float` | 詹森 α（已年化）。正值 = 跑赢 CAPM 预测 |
| `beta` | `float` | 市场敏感度 β = Cov(Rp,Rm) / Var(Rm) |

```python
# 用法
from qka import Analysis

analysis = Analysis()
result = analysis.alpha_beta(
    df['sz.000001|returns'].dropna(),
    df['benchmark|returns'].dropna(),
)
print(f'α={result.alpha:.2%}, β={result.beta:.2f}')
```

### sharpe_ratio()

`sharpe_ratio(returns, rf=0.0, periods_per_year=252) → float`

夏普比率（年化）。公式：`(mean(Rp) - rf_period) / std(Rp) × √N`。

### max_drawdown()

`max_drawdown(returns) → float`

最大回撤，返回正数（0.35 = 35% 回撤）。

### information_ratio()

`information_ratio(returns, bench_returns, periods_per_year=252) → float`

信息比率（年化）。公式：`mean(Rp-Rm) / std(Rp-Rm) × √N`。衡量跑赢基准的稳定性。

### 示例

```python
from qka import Data, Analysis

data = Data(symbols=['sz.000001'], benchmark='sh.000300')
df = data.get()

analysis = Analysis()

# 趋势分段
segs = analysis.zigzag(df['sz.000001|close'], threshold=0.3, min_days=90)
for s in segs:
    print(f'{s.start.date()} ~ {s.end.date()}  {s.direction}  {s.change:+.1f}%')

# 单次指标（标量，非滚动）
ab = analysis.alpha_beta(
    df['sz.000001|returns'].dropna(),
    df['benchmark|returns'].dropna(),
)
print(f'α={ab.alpha:.2%}, β={ab.beta:.2f}')

sharpe  = analysis.sharpe_ratio(df['sz.000001|returns'])
mdd     = analysis.max_drawdown(df['sz.000001|returns'])
ir      = analysis.information_ratio(df['sz.000001|returns'], df['benchmark|returns'])
print(f'夏普={sharpe:.2f}, 最大回撤={mdd:.1%}, IR={ir:.2f}')
```
