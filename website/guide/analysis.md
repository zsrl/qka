# 常用分析工具 (Analysis)

`qka.Analysis` 模块收纳了量化研究中常用的事后统计、回归度量与时序形态分析方法。

---

## 实例化

```python
from qka import Analysis

analysis = Analysis()
```

`Analysis` 类无需传入任何构造参数，直接实例化后调用方法即可。

---

## 核心分析方法

### 1. `zigzag()` 趋势分段算法

基于 **Hodrick–Prescott (HP) 滤波平滑** 与 **Zigzag 摆动指标**，对资产价格序列进行趋势去噪，自动识别价格交替的上行波段与下行波段。

::: danger 包含未来函数警告
`zigzag()` 算法基于全历史时间序列进行双向滤波与极值点确认，**包含未来函数**，严格仅供事后复盘、市场周期划分与策略特征归因使用，**禁止放入策略 `on_bar` 中作为买卖信号**！
:::

```python
segments = analysis.zigzag(
    series=df['000001.SZ|close'],
    threshold=0.3,   # 峰顶回落 30% 确认转折，谷底反弹 30% 确认见底
    min_days=90,     # 单段最短持续 90 个自然日（过短的被前后段合并）
    lamb=1600        # HP 滤波平滑参数，日线标准值 1600
)

for seg in segments:
    print(f"[{seg.start.strftime('%Y-%m-%d')} ~ {seg.end.strftime('%Y-%m-%d')}] "
          f"方向: {seg.direction} | 幅度: {seg.change:+.2%}")
```

#### 返回值结构 (`Segment`)
- `start` (`pd.Timestamp`)：波段起始日期
- `end` (`pd.Timestamp`)：波段结束日期
- `direction` (`str`)：`'上行'` 或 `'下行'`
- `change` (`float`)：波段内价格累计涨跌幅百分比

---

### 2. `alpha_beta()` 资本资产定价回归

通过普通最小二乘法（OLS）回归模型，一次性计算投资组合相对基准市场的 **詹森阿尔法（Jensen's $\alpha$）** 与 **贝塔系数（$\beta$）**：

$$R_p - R_f = \alpha + \beta (R_m - R_f) + \epsilon$$

```python
result = analysis.alpha_beta(
    returns=df['000001.SZ|returns'].dropna(),
    bench_returns=df['benchmark|returns'].dropna(),
    rf=0.03,               # 年化无风险利率（如 3%）
    periods_per_year=252   # 日线数据按每年 252 交易日年化
)

print(f"年化 Jensen's Alpha: {result.alpha:.2%}")
print(f"市场敏感度 Beta:     {result.beta:.2f}")
```

- **$\alpha > 0$**：跑赢 CAPM 理论预测，展现出主动获取超额收益的能力。
- **$\beta \approx 1$**：与大盘波动幅度相当；$\beta > 1$ 属于高弹性进攻型资产；$\beta < 1$ 属于防御型资产。

---

### 3. 单项绩效统计方法

对于任意收益率序列（如单只股票、回测净值序列），`Analysis` 提供了轻量级的快捷计算函数：

#### `sharpe_ratio()`
计算年化夏普比率：
```python
sr = analysis.sharpe_ratio(returns=series, rf=0.03, periods_per_year=252)
```

#### `max_drawdown()`
计算最大回撤幅度（返回正数，例如 `0.235` 代表最大回撤为 23.5%）：
```python
mdd = analysis.max_drawdown(returns=series)
print(f"最大回撤: {mdd:.2%}")
```

#### `information_ratio()`
计算年化信息比率（Information Ratio）：
$$\text{IR} = \frac{\text{mean}(R_p - R_m)}{\text{std}(R_p - R_m)} \times \sqrt{252}$$
衡量策略相对基准获取超额收益的稳定性，IR 越高代表超额收益波动越小。
```python
ir = analysis.information_ratio(
    returns=strategy_returns,
    bench_returns=benchmark_returns
)
```
