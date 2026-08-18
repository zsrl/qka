## Data

数据获取和指标预计算。

### 构造

创建一个数据对象，配置数据源、股票代码和预计算指标。此时数据尚未下载，调用 `get()` 时才真正获取。

```python
from qka import Data

data = Data(
    symbols=['sz.000001', 'sh.600000'],
    period='1d',
    adjust='qfq',
    benchmark=None,
    indicators=None,
)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `symbols` | `list[str]` | `None` | A 股代码，baostock 格式 `sz.000001`、`sh.600000` |
| `period` | `str` | `'1d'` | 数据周期，当前仅支持 `'1d'` |
| `adjust` | `str` | `'qfq'` | 复权方式：`'qfq'` 前复权，`'hfq'` 后复权，`'bfq'` 不复权 |
| `benchmark` | `str` | `None` | 基准指数代码，如 `'sh.000300'`。下载后在 `get()` 结果中追加 `benchmark|returns` 列 |
| `indicators` | `dict` | `None` | 预计算指标，见下方 |

`get()` 返回的 DataFrame 除了 `open/high/low/close/volume/amount` 六大基本列外，还自动内置一列：

| 常驻列 | 公式 | 说明 |
|------|------|------|
| `returns` | `close.diff() / close.shift(1)` | 日收益率，始终存在，无需在 indicators 中声明 |

### indicators

在构造 `Data` 时传入，利用数据加载过程一次性预计算所有指标。**不能**在构造后补充。

#### 内置指标

直接透传 [ta](https://github.com/bukosabino/ta) 库的全部指标函数，格式为：`{'列名': ('ta.路径.函数名', '计算列', 参数...)}`。每个条目独立产一列，第二个参数固定为计算列名（不设默认值）。

```python
data = Data(
    symbols=['sz.000001'],
    indicators={
        'sma_5':       ('ta.trend.sma_indicator', 'close', 5),
        'sma_20':      ('ta.trend.sma_indicator', 'close', 20),
        'ema_20':      ('ta.trend.ema_indicator', 'close', 20),
        'rsi_14':      ('ta.momentum.rsi', 'close', 14),
        'macd_line':   ('ta.trend.macd', 'close', 26, 12),
        'macd_signal': ('ta.trend.macd_signal', 'close', 26, 12, 9),
        'macd_hist':   ('ta.trend.macd_diff', 'close', 26, 12, 9),
        'bb_upper':    ('ta.volatility.bollinger_hband', 'close', 20, 2),
        'bb_middle':   ('ta.volatility.bollinger_mavg', 'close', 20),
        'bb_lower':    ('ta.volatility.bollinger_lband', 'close', 20, 2),
        'atr_14':      ('ta.volatility.average_true_range', 'high', 'low', 'close', 14),
        'adx_14':      ('ta.trend.adx', 'high', 'low', 'close', 14),
    },
)
```

- `spec[0]`: ta 函数完整路径
- `spec[1]`: 计算列名（`'close'`/`'high'`/`'low'`/`'open'`/`'volume'`）
- `spec[2:]`: 原样传给该函数

可用的 ta 函数：

#### trend

| 签名 | 说明 |
|------|------|
| `ta.trend.adx(high, low, close, window=14)` | 平均趋向指数 |
| `ta.trend.adx_neg(high, low, close, window=14)` | ADX 负向指标 |
| `ta.trend.adx_pos(high, low, close, window=14)` | ADX 正向指标 |
| `ta.trend.aroon_down(high, low, window=25)` | Aroon 下轨 |
| `ta.trend.aroon_up(high, low, window=25)` | Aroon 上轨 |
| `ta.trend.cci(high, low, close, window=20, constant=0.015)` | 商品通道指数 |
| `ta.trend.dpo(close, window=20)` | 去趋势价格振荡器 |
| `ta.trend.ema_indicator(close, window=12)` | 指数移动平均 |
| `ta.trend.ichimoku_a(high, low, window1=9, window2=26, visual=False)` | 一目均衡表 A 线（先行带） |
| `ta.trend.ichimoku_b(high, low, window2=26, window3=52, visual=False)` | 一目均衡表 B 线（先行带） |
| `ta.trend.ichimoku_base_line(high, low, window1=9, window2=26, visual=False)` | 一目均衡表基准线 |
| `ta.trend.ichimoku_conversion_line(high, low, window1=9, window2=26, visual=False)` | 一目均衡表转换线 |
| `ta.trend.kst(close, roc1=10, roc2=15, roc3=20, roc4=30, window1=10, window2=10, window3=10, window4=15)` | 确然指标（KST） |
| `ta.trend.kst_sig(close, roc1=10, roc2=15, roc3=20, roc4=30, window1=10, window2=10, window3=10, window4=15, nsig=9)` | KST 信号线 |
| `ta.trend.macd(close, window_slow=26, window_fast=12)` | MACD 线（DIF） |
| `ta.trend.macd_diff(close, window_slow=26, window_fast=12, window_sign=9)` | MACD 柱（HIST） |
| `ta.trend.macd_signal(close, window_slow=26, window_fast=12, window_sign=9)` | MACD 信号线（DEA） |
| `ta.trend.mass_index(high, low, window_fast=9, window_slow=25)` | 质量指数 |
| `ta.trend.psar_down(high, low, close, step=0.02, max_step=0.2)` | 抛物线 SAR（下方） |
| `ta.trend.psar_down_indicator(high, low, close, step=0.02, max_step=0.2)` | 抛物线 SAR 下方指示 |
| `ta.trend.psar_up(high, low, close, step=0.02, max_step=0.2)` | 抛物线 SAR（上方） |
| `ta.trend.psar_up_indicator(high, low, close, step=0.02, max_step=0.2)` | 抛物线 SAR 上方指示 |
| `ta.trend.sma_indicator(close, window=12)` | 简单移动平均 |
| `ta.trend.stc(close, window_slow=50, window_fast=23, cycle=10, smooth1=3, smooth2=3)` | 沙夫趋势周期 |
| `ta.trend.trix(close, window=15)` | 三重指数平滑平均线 |
| `ta.trend.vortex_indicator_neg(high, low, close, window=14)` | 漩涡指标负向 |
| `ta.trend.vortex_indicator_pos(high, low, close, window=14)` | 漩涡指标正向 |
| `ta.trend.wma_indicator(close, window=9)` | 加权移动平均 |

#### momentum

| 签名 | 说明 |
|------|------|
| `ta.momentum.awesome_oscillator(high, low, window1=5, window2=34)` | 动量振荡器 |
| `ta.momentum.kama(close, window=10, pow1=2, pow2=30)` | 考夫曼自适应移动平均 |
| `ta.momentum.ppo(close, window_slow=26, window_fast=12, window_sign=9)` | 价格百分比振荡器 |
| `ta.momentum.ppo_hist(close, window_slow=26, window_fast=12, window_sign=9)` | PPO 柱 |
| `ta.momentum.ppo_signal(close, window_slow=26, window_fast=12, window_sign=9)` | PPO 信号线 |
| `ta.momentum.pvo(volume, window_slow=26, window_fast=12, window_sign=9)` | 成交量百分比振荡器 |
| `ta.momentum.pvo_hist(volume, window_slow=26, window_fast=12, window_sign=9)` | PVO 柱 |
| `ta.momentum.pvo_signal(volume, window_slow=26, window_fast=12, window_sign=9)` | PVO 信号线 |
| `ta.momentum.roc(close, window=12)` | 变动率 |
| `ta.momentum.rsi(close, window=14)` | 相对强弱指数 |
| `ta.momentum.stoch(high, low, close, window=14, smooth_window=3)` | 随机指标 %K |
| `ta.momentum.stoch_signal(high, low, close, window=14, smooth_window=3)` | 随机指标 %D |
| `ta.momentum.stochrsi(close, window=14, smooth1=3, smooth2=3)` | 随机 RSI |
| `ta.momentum.stochrsi_d(close, window=14, smooth1=3, smooth2=3)` | 随机 RSI %D |
| `ta.momentum.stochrsi_k(close, window=14, smooth1=3, smooth2=3)` | 随机 RSI %K |
| `ta.momentum.tsi(close, window_slow=25, window_fast=13)` | 真实强度指数 |
| `ta.momentum.ultimate_oscillator(high, low, close, window1=7, window2=14, window3=28, weight1=4.0, weight2=2.0, weight3=1.0)` | 终极振荡器 |
| `ta.momentum.williams_r(high, low, close, lbp=14)` | 威廉指标 |

#### volatility

| 签名 | 说明 |
|------|------|
| `ta.volatility.average_true_range(high, low, close, window=14)` | 平均真实波幅 |
| `ta.volatility.bollinger_hband(close, window=20, window_dev=2)` | 布林带上轨 |
| `ta.volatility.bollinger_hband_indicator(close, window=20, window_dev=2)` | 布林带上轨指示 |
| `ta.volatility.bollinger_lband(close, window=20, window_dev=2)` | 布林带下轨 |
| `ta.volatility.bollinger_lband_indicator(close, window=20, window_dev=2)` | 布林带下轨指示 |
| `ta.volatility.bollinger_mavg(close, window=20)` | 布林带中轨 |
| `ta.volatility.bollinger_pband(close, window=20, window_dev=2)` | 布林带 %B |
| `ta.volatility.bollinger_wband(close, window=20, window_dev=2)` | 布林带带宽 |
| `ta.volatility.donchian_channel_hband(high, low, close, window=20, offset=0)` | 唐奇安通道上轨 |
| `ta.volatility.donchian_channel_lband(high, low, close, window=20, offset=0)` | 唐奇安通道下轨 |
| `ta.volatility.donchian_channel_mband(high, low, close, window=10, offset=0)` | 唐奇安通道中轨 |
| `ta.volatility.donchian_channel_pband(high, low, close, window=10, offset=0)` | 唐奇安通道 %B |
| `ta.volatility.donchian_channel_wband(high, low, close, window=10, offset=0)` | 唐奇安通道带宽 |
| `ta.volatility.keltner_channel_hband(high, low, close, window=20, window_atr=10, original_version=True)` | 肯特纳通道上轨 |
| `ta.volatility.keltner_channel_hband_indicator(high, low, close, window=20, window_atr=10, original_version=True)` | 肯特纳通道上轨指示 |
| `ta.volatility.keltner_channel_lband(high, low, close, window=20, window_atr=10, original_version=True)` | 肯特纳通道下轨 |
| `ta.volatility.keltner_channel_lband_indicator(high, low, close, window=20, window_atr=10, original_version=True)` | 肯特纳通道下轨指示 |
| `ta.volatility.keltner_channel_mband(high, low, close, window=20, window_atr=10, original_version=True)` | 肯特纳通道中轨 |
| `ta.volatility.keltner_channel_pband(high, low, close, window=20, window_atr=10, original_version=True)` | 肯特纳通道 %B |
| `ta.volatility.keltner_channel_wband(high, low, close, window=20, window_atr=10, original_version=True)` | 肯特纳通道带宽 |
| `ta.volatility.ulcer_index(close, window=14)` | 溃疡指数 |

#### 自定义指标

非 ta 库的自定义因子用 callable：

```python
indicators={
    'ma5': lambda df: df['close'].rolling(5).mean(),
}
```

函数接收单只股票的 DataFrame（含 `open/high/low/close/volume`），返回添加了新列的 DataFrame。

#### qka 内置指标

qka 框架内置的滚动窗口指标，格式为 `{'列名': ('qka.函数名', 窗口, ...)}`。所有函数使用 `returns` 列计算，部分需要基准数据（`benchmark|returns`）。

```python
data = Data(
    symbols=['sz.000001', 'sh.600000'],
    benchmark='sh.000300',  # alpha/beta/information_ratio 必需
    indicators={
        'sma_20':   ('ta.trend.sma_indicator', 'close', 20),
        'beta_60':  ('qka.beta', 60),
        'alpha_60': ('qka.alpha', 60),
        'sharpe_60':('qka.sharpe', 60),
        'mdd_60':   ('qka.max_drawdown', 60),
        'ir_60':    ('qka.information_ratio', 60),
        'zigzag_60':('rolling_zigzag', 60, 0.3, 1600),
    },
)
```

| 函数 | 需要 benchmark | 说明 |
|------|:---:|------|
| `qka.beta` | ✅ | 滚动 β，公式 `Cov(Rp,Rm) / Var(Rm)` |
| `qka.alpha` | ✅ | 滚动詹森 α（年化），公式 `Rp - [Rf + β·(Rm-Rf)]` |
| `qka.sharpe` | ❌ | 滚动夏普比率（年化），公式 `(Rp-Rf) / σp` |
| `qka.max_drawdown` | ❌ | 滚动窗口最大回撤，返回负数（如 -0.15） |
| `qka.information_ratio` | ✅ | 滚动信息比率（年化），公式 `mean(Rp-Rm) / std(Rp-Rm)` |
| `rolling_zigzag` | ❌ | 滚动窗口 Zigzag 趋势方向，HP 滤波+Zigzag 状态机，输出 1（上行）/-1（下行）/NaN |

- `rolling_zigzag` 签名：`('rolling_zigzag', window, threshold, lamb)`，默认 `threshold=0.3` `lamb=1600`，需要 `{symbol}|close` 列
- 无 `rf` 参数时默认 `0`，无 `periods_per_year` 时默认 `252`
- 需要 benchmark 的函数在 `Data` 未设 `benchmark` 时抛 `ValueError`
- 每个函数独立计算，即使 α 和 β 内部都跑 OLS 也不共享结果（与 ta 库 BBands 三函数一致）

### get()

`get(lazy=False, start_date=None, end_date=None) → pd.DataFrame`

调用后触发数据下载和指标计算，返回合并后的宽表。`Backtest.run()` 内部会调用它。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `lazy` | `bool` | `False` | 返回 `dask.DataFrame` 而非 `pd.DataFrame` |
| `start_date` | `str` | `None` | 起始日期 `'YYYY-MM-DD'`。有指标时自动向后扩展窗口确保预热数据充足 |
| `end_date` | `str` | `None` | 截止日期 `'YYYY-MM-DD'` |

```python
df = data.get()
df = data.get(start_date='2024-01-01', end_date='2024-12-31')
```

| 属性 | 说明 |
|------|------|
| 类型 | `pd.DataFrame`（`lazy=True` 时返回 `dask.DataFrame`） |
| 索引 | 日期索引，**索引名为 `"date"`**。`reset_index()` 后日期列名也是 `"date"` |
| 列名 | `{symbol}|{factor}` — 例如 `sz.000001|close`、`sz.000001|sma_5`、`sh.600000|volume` |
| 常驻列 | 除 `open/high/low/close/volume/amount` 外，自动内置 `{symbol}|returns` |
| 基准列 | 若构造时设了 `benchmark`，追加 `benchmark|returns`（无 `{symbol}|` 前缀） |
| 列值 | 全部为 `float64`，指标列的早期行可能含 `NaN` |
| 异常 | 无数据时抛出 `RuntimeError` |

**返回的宽表示例：**

```python
data = Data(symbols=['sz.000001', 'sh.600000'], indicators={
    'sma_5': ('ta.trend.sma_indicator', 'close', 5),
})
df = data.get(start_date='2024-01-02', end_date='2024-01-05')
```

返回的 DataFrame 结构（行=日期，列=每只股票的完整字段堆叠）：

```
            sz.000001|open  sz.000001|close  ...  sz.000001|sma_5  sh.600000|open  sh.600000|close  ...  sh.600000|sma_5
2024-01-02           10.0             10.2  ...            NaN            15.0             15.3  ...            NaN
2024-01-03           10.1             10.5  ...            NaN            15.2             15.6  ...            NaN
2024-01-04           10.3             10.8  ...            NaN            14.9             15.1  ...            NaN
2024-01-05           10.2             10.6  ...            NaN            15.4             15.9  ...            NaN
```

- 每只股票独占一组列，列前缀 = symbol
- `returns` 列自动存在，无需在 indicators 中声明
- 前 4 行 SMA 为 NaN（窗口=5，不足）
- 若设了 `benchmark='sh.000300'`，末尾多一列 `benchmark|returns`

```python
# 列名格式：{symbol}|{factor}
df.columns  # ['sz.000001|open', 'sz.000001|close', 'sz.000001|returns',
            #  'sz.000001|sma_5', 'sh.600000|open', 'sh.600000|close',
            #  'sh.600000|returns', 'sh.600000|sma_5']

# 索引名为 "date"，reset_index 后转为 pd.Timestamp 列
df = df.reset_index()
df['date'].iloc[0]          # Timestamp('2024-01-02 00:00:00')

# 输出 JSON 前需转为字符串
df['date'] = df['date'].dt.strftime('%Y-%m-%d')
df['date'].iloc[0]          # '2024-01-02'
```
