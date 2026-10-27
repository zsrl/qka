# 技术指标与因子计算

QKA 拥有强大而灵活的因子声明系统，完整集成了知名 Python 技术分析库 `ta` 的全部指标，同时支持内置高级量化指标与用户自定义函数。

---

## 因子声明语法

在 `Data` 构造函数中，通过 `factors` 字典传入需要计算的因子（旧名 `indicators` 完全兼容）：

```python
data = Data(
    symbols=['000001.SZ'],
    factors={
        '因子名': 因子声明表达式,
    }
)
```

QKA 支持三种声明形态：

---

### 1. `ta` 库全部技术指标（元组语法）

QKA 支持以三元组（或多元组）格式无缝调用 `ta` 库的任意指标函数：

$$\text{('ta.模块.函数', '取值列', *参数, **命名参数)}$$

#### 常用技术指标示例

```python
factors = {
    # 1. 均线系统 (Trend)
    'sma_5':       ('ta.trend.sma_indicator', 'close', 5),
    'sma_20':      ('ta.trend.sma_indicator', 'close', 20),
    'ema_12':      ('ta.trend.ema_indicator', 'close', 12),
    'macd_diff':   ('ta.trend.macd_diff', 'close', 12, 26, 9),

    # 2. 动量震荡 (Momentum)
    'rsi_14':      ('ta.momentum.rsi', 'close', 14),
    'kdj_k':       ('ta.momentum.stoch', 'high', 'low', 'close', 14, 3),

    # 3. 波动通道 (Volatility)
    'boll_upper':  ('ta.volatility.bollinger_hband', 'close', 20, 2),
    'boll_lower':  ('ta.volatility.bollinger_lband', 'close', 20, 2),
    'atr_14':      ('ta.volatility.average_true_range', 'high', 'low', 'close', 14),

    # 4. 成交量指标 (Volume)
    'obv':         ('ta.volume.on_balance_volume', 'close', 'volume'),
}
```

::: tip 支持多列输入
如果 `ta` 指标需要多个字段（如 ATR 需要 high, low, close），在元组中依次传入字符串字段名即可，框架会自动提取对应列传入函数。
:::

---

### 2. QKA 内置高级金融指标

QKA 内置了常用的高级滚动金融指标，免去手写复杂数学公式：

```python
factors = {
    # 滚动夏普比率 (年化，252个交易日)
    'sharpe_60':      ('qka.sharpe', 60),

    # 滚动最大回撤 (窗口 60 天)
    'mdd_60':         ('qka.max_drawdown', 60),

    # 相对沪深 300 的滚动 Alpha 与 Beta
    'alpha_60':       ('qka.alpha', '000300.SH', 60),
    'beta_60':        ('qka.beta', '000300.SH', 60),
}
```

---

### 3. 自定义 Lambda / 函数计算

如果需要计算特殊因子（如价格相对位置、动量乖离率），可直接传入一个接收单标的 `df` 并返回 `pd.Series` 的函数：

```python
factors = {
    # 20日动量：(close - close.shift(20)) / close.shift(20)
    'mom_20': lambda df: df['close'].pct_change(20),

    # 收盘价在过去 60 天的相对分位数
    'pos_60': lambda df: (df['close'] - df['low'].rolling(60).min()) / (df['high'].rolling(60).max() - df['low'].rolling(60).min()),
}
```

---

## 因子预热机制 (warmup)

### 为什么需要 warmup？
当策略需要使用 60 日均线或 200 日动量时，如果不进行预热，回测从第 1 天开始的前 60 天因子都是 `NaN`。传统回测框架中，用户不得不写各种防御代码：
```python
# 传统框架的丑陋写法（容易引起逻辑漏洞）
if len(hist) < 60:
    continue
```

### QKA 的优雅解决方案
QKA 提供了原生的 `warmup` 参数。当你设置 `warmup=60` 时：
1. 框架会在实际回测起始日（`start_date`）之前，**额外多读取 60 个交易日的数据**。
2. 在包含预热期的完整历史数据上向量化计算出所有指标。
3. 计算完成后，**将多读的预热期截断**，回测严格从 `start_date` 开始执行。

```python
data = Data(
    symbols=['000001.SZ'],
    factors={
        'sma_60': ('ta.trend.sma_indicator', 'close', 60),
    },
    warmup=60,  # 预热 60 个交易日
)

# 在策略 on_bar 中：
# 第 1 天即刻拥有有效的 sma_60 数值，无需任何 continue 判定！
```

---

## 停牌日平滑补齐 (`fill_suspended`)

在 A 股市场中，个股停牌是常态。停牌期间缺少行情条目，会导致滚动窗口计算出现大量 `NaN`。

设置 `fill_suspended=True`，QKA 会自动识别交易日历，在停牌日将前一个交易日的收盘价进行前向填充（Forward Fill），成交量置为 0，确保指标滚动计算连续完整：

```python
data = Data(
    symbols=['000001.SZ'],
    factors={'sma_20': ('ta.trend.sma_indicator', 'close', 20)},
    fill_suspended=True,  # 自动按前收平滑补齐停牌日
)
```
