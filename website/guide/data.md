# 多源行情与智能缓存

`qka.Data` 是 QKA 框架的数据中枢，负责多数据源的拉取、本地 Parquet 落盘缓存、除权除息复权计算以及因子向量化预计算。

---

## 构造与核心参数

```python
from qka import Data

data = Data(
    symbols=['000001.SZ', '600000.SH'],
    period='1d',
    adjust='qfq',
    source='tickflow',
    benchmark='000300.SH',
    factors=None,
    warmup=0,
)
```

### 参数详解

| 参数名 | 类型 | 默认值 | 详细说明 |
|--------|------|--------|----------|
| `symbols` | `list[str \| Simulate]` | `None` | 标的列表。支持 **`代码.市场`**（如 `'000001.SZ'`、`'600000.SH'`）或旧写法（`'sz.000001'`），支持与 `Simulate` 模拟标的混排 |
| `period` | `str` | `'1d'` | 数据周期，当前支持 `'1d'` 日线数据 |
| `adjust` | `str` | `'qfq'` | 复权方式：`'qfq'` 前复权（回测推荐）、`'hfq'` 后复权、`'bfq'` 不复权 |
| `source` | `str` | `'tickflow'` | 数据源：`'tickflow'`、`'baostock'`、`'tdx'`（详见下文） |
| `benchmark` | `str` | `None` | 基准指数代码，如 `'000300.SH'`。将在结果宽表中自动追加 `benchmark|returns` |
| `factors` | `dict \| Callable` | `None` | 因子与技术指标预计算字典（旧名 `indicators` 完全兼容） |
| `extra_fields` | `list[str]` | `None` | 扩展财务与估值字段（仅 `source='baostock'` 支持） |
| `warmup` | `int` | `0` | 因子预热天数。自动多读历史数据用于指标计算，回测首日即具备有效值 |
| `factor_cache` | `bool` | `False` | 是否将计算出的因子持久化落盘缓存 |
| `fill_suspended` | `bool` | `False` | 是否将停牌日的行情按前收盘价前向补齐 |

---

## 数据源对比与选型

QKA 内置了三个开箱即用的数据源，只需更改 `source=` 参数即可一键平滑切换：

| 数据源 | 参数值 | 适用场景与优势 | 限制与说明 |
|--------|--------|----------------|------------|
| **tickflow** *(默认)* | `'tickflow'` | 覆盖 A 股全市场历史数据，**含全量 ETF、可转债历史行情**；速度快，无须注册 | 仅基础 OHLCV 与成交额行情 |
| **baostock** | `'baostock'` | 提供丰富的财务估值、换手率、ST 标记等扩展指标 | 仅支持股票，网络请求需建立连接会话 |
| **通达信 (TDX)** | `'tdx'` | 直接读取本地通达信「TQ 版」客户端的高速行情通道 | 仅限 Windows 平台，需本地启动通达信 |

### 1. 默认数据源：tickflow
对于绝大多数股票、ETF 与可转债回测，使用默认的 `tickflow` 即可享受毫秒级的获取体验：
```python
data = Data(symbols=['510300.SH', '159915.SZ'], source='tickflow')
df = data.get()
```

### 2. 估值与基本面：baostock
当需要结合市盈率（PE）、市净率（PB）、换手率选股时，设置 `source='baostock'` 并传入 `extra_fields`：
```python
data = Data(
    symbols=['000001.SZ', '600000.SH'],
    source='baostock',
    extra_fields=['peTTM', 'pbMRQ', 'turnover', 'isST'],
)
df = data.get()
```

`baostock` 支持的扩展字段包括：
- `peTTM`：滚动市盈率
- `pbMRQ`：市净率
- `turnover`：换手率
- `isST`：是否 ST 股票（`1` 为是，`0` 为否）
- `pctChg`：涨跌幅
- `psTTM`：市销率
- `pcfNcfTTM`：市现率

### 3. 通达信本地源：tdx
Windows 用户若安装了通达信 TQ 客户端，可直接读取通达信的高速行情：
```python
data = Data(symbols=['000001.SZ'], source='tdx')
```

---

## 宽表数据结构

调用 `data.get()` 会返回标准 `pandas.DataFrame`：
- **Index**：`pd.DatetimeIndex`（日期升序排列）
- **Columns**：以 `{symbol}|{field}` 组织

```text
               000001.SZ|open  000001.SZ|close  000001.SZ|returns  000001.SZ|sma_20
date                                                                               
2024-01-02              9.38             9.35          -0.004260             9.28
2024-01-03              9.32             9.29          -0.006417             9.27
```

::: tip 常驻内置列
不论你在 `factors` 中传入什么，`Data.get()` 始终会自动为每个标的计算 `{symbol}|returns`（日收益率列：`close.diff() / close.shift(1)`），无需手动重复定义。
:::

---

## 智能分级缓存机制

为了避免重复网络请求并加速策略回测，QKA 配备了自动化的本地缓存系统：
1. **隔离存储**：缓存文件按 `数据源 / 复权口径 / 周期` 分目录持久化存储在用户主目录下的 `.qka/` 或项目缓存目录中。
2. **增量补齐**：首次运行自动下载全部历史；后续再次调用时，若本地缓存时间落后于最新交易日，框架将自动只下载增量区间并追加合并。
3. **复权独立**：前复权（qfq）、后复权（hfq）与不复权（bfq）采用独立的缓存文件，切换复权口径绝不会造成数据污染。
