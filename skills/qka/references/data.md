# Data 模块

数据获取、缓存和指标预计算。

## Data 构造函数

```python
from qka import Data

data = Data(
    symbols=['000001.SZ', '600000.SH'],  # 股票代码
    period='1d',                          # 周期：'1d'
    adjust='qfq',                         # 复权：'qfq'/'hfq'/'bfq'
    source='baostock',                    # 数据源：'baostock'/'akshare'/'qmt'
    pool_size=10,                         # 并发线程数（仅 akshare）
    datadir=None,                         # 缓存目录，默认 ./datadir
    indicators=None,                      # 预计算指标
)
```

- `symbols`: A 股代码 `000001.SZ`（深市）或 `600000.SH`（沪市）
- `period`: 目前仅支持 `'1d'`（日线）
- `adjust`: `'qfq'`（前复权，默认）、`'hfq'`（后复权）、`'bfq'`（不复权）
- `source`: `'baostock'`（默认，串行下载）、`'akshare'`（HTTP 并发）、`'qmt'`（QMT）
- `datadir`: 默认当前目录的 `datadir/`，缓存 parquet 文件

## indicators 参数

两种格式：

### 格式一：字典（推荐）

```python
data = Data(symbols=['000001.SZ'], indicators={
    'sma_5': ('sma', 5),                   # (指标名, 参数...)
    'sma_20': ('sma', 20),                 # 默认用 close 计算
    'rsi_14': ('rsi', 14),
    'macd': ('macd', 12, 26, 9),
    'bbands': ('bbands', 20, 2),
    'atr_14': ('atr', 14),
    'ma5_custom': lambda df: df['close'].rolling(5).mean(),  # 自定义因子
    'sma_on_high': ('sma', 'high', 20),    # 指定用 high 列计算
})
```

支持的 TA 指标名：`sma`, `ema`, `wma`, `rsi`, `macd`, `bbands`, `atr`

- `macd` 产生 3 列：`macd`, `macd_signal`, `macd_diff`
- `bbands` 产生 3 列：`bbands_upper`, `bbands_middle`, `bbands_lower`

### 格式二：函数

```python
data = Data(symbols=['000001.SZ'], indicators=lambda df:
    df.assign(
        ma5=df['close'].rolling(5).mean(),
        ma20=df['close'].rolling(20).mean()
    )
)
```

函数接收单只股票的 DataFrame，返回添加了额外列的 DataFrame。

## 获取数据

```python
data = Data(symbols=['000001.SZ', '600000.SH'], indicators={'sma_5': ('sma', 5)})

# 下载并返回全部数据（触发下载）
df = data.get()

# 懒加载模式（大数据用 dask，分块迭代）
ddf = data.get(lazy=True)
```

- `get()` 返回 `pd.DataFrame`，列名格式 `{symbol}|{factor}`
- 示例列名：`000001.SZ|close`, `000001.SZ|sma_5`, `600000.SH|volume`
- `get(lazy=True)` 返回 `dask.DataFrame`，计算前操作延迟执行

## 常见错误

```python
# ✅ 正确：传 indicators 到 Data 构造函数
Data(symbols=['000001.SZ'], indicators={'sma_5': ('sma', 5)})

# ❌ 错误：Data() 后不能动态加指标
data = Data(['000001.SZ'])
data.indicators = {...}  # 没用
```
