# qka.Data

数据获取和因子预计算类。

```python
from qka import Data
```

---

## 构造函数

```python
Data(
    symbols: list[str | Simulate] | None = None,
    period: str = '1d',
    adjust: str = 'qfq',
    source: str = 'tickflow',
    benchmark: str | None = None,
    factors: dict | Callable | None = None,
    extra_fields: list[str] | None = None,
    warmup: int = 0,
    factor_cache: bool = False,
    fill_suspended: bool = False,
    datadir: str | Path | None = None,
)
```

### 参数说明

| 参数 | 类型 | 默认值 | 详细说明 |
|------|------|--------|----------|
| `symbols` | `list[str \| Simulate]` | `None` | 标的列表。元素可以是 A 股代码（推荐 **`代码.市场`**，如 `'000001.SZ'`，亦兼容 `'sz.000001'`），也可以是 `Simulate` 模拟标的对象，支持混排 |
| `period` | `str` | `'1d'` | 数据周期，当前支持 `'1d'` 日线数据 |
| `adjust` | `str` | `'qfq'` | 复权方式：`'qfq'` 前复权、`'hfq'` 后复权、`'bfq'` 不复权 |
| `source` | `str` | `'tickflow'` | 行情源：`'tickflow'`（全市场，含 ETF/转债）、`'baostock'`（含财务估值）、`'tdx'`（通达信本地源） |
| `benchmark` | `str` | `None` | 基准指数代码，如 `'000300.SH'`。加载后在宽表中自动追加 `benchmark|returns` 列 |
| `factors` | `dict \| Callable` | `None` | 因子预计算配置（旧名 `indicators` 完全兼容） |
| `extra_fields` | `list[str]` | `None` | 扩展字段（如 `peTTM`, `pbMRQ`, `turnover`, `isST`），仅 `source='baostock'` 生效 |
| `warmup` | `int` | `0` | 因子预热天数。自动在回测开始日前多读历史天数以完成因子预热 |
| `factor_cache` | `bool` | `False` | 是否将计算出的因子纵向落盘缓存 |
| `fill_suspended` | `bool` | `False` | 是否按前收盘价前向补齐停牌日 |
| `datadir` | `str \| Path` | `None` | 自定义本地缓存存储根路径 |

---

## 方法

### `get(start_date=None, end_date=None) -> pd.DataFrame`

获取并计算全量标的的宽表数据。

- **`start_date`** (`str`, 可选)：起始日期 `'YYYY-MM-DD'`。
- **`end_date`** (`str`, 可选)：截止日期 `'YYYY-MM-DD'`。
- **返回值**：`pd.DataFrame`，行索引为 `pd.DatetimeIndex`，列索引采用 `{symbol}|{field}` 复合命名。

```python
data = Data(symbols=['000001.SZ'], factors={'sma_20': ('ta.trend.sma_indicator', 'close', 20)})
df = data.get(start_date='2024-01-01', end_date='2024-06-30')
```

#### 常驻列
返回的宽表中，除了基本量价字段（`open`, `high`, `low`, `close`, `volume`, `amount`）之外，始终包含：
- **`{symbol}|returns`**：日收益率序列（公式：`close.diff() / close.shift(1)`）。

---

## 缓存口径与行为

| 复权模式 | 增量策略 | 机制说明 |
|----------|----------|----------|
| `bfq` / `hfq` | 增量更新 | 历史价格恒定，若本地已有部分缓存，只向网络请求缺失的最新日期 |
| `qfq` | 全量更新 | 前复权以最新收盘价为基准基点，发生除权除息时会倒推重写整段历史，因此需要新数据时全量重新获取 |
