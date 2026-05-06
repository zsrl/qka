# 数据获取

`Data` 负责从数据源下载 A 股行情数据并缓存到本地。

---

## 基本用法

```python
from qka import Data

data = Data(symbols=['000001.SZ', '600000.SH'])
df = data.get()        # 返回 pandas DataFrame（立即加载）
lazy = data.get(lazy=True)  # 返回 dask DataFrame（懒加载）
```

默认从 **baostock** 获取数据，自动缓存到 `datadir/` 目录（parquet 格式）。下次运行直接读缓存。

---

## 参数说明

```python
Data(
    symbols=['000001.SZ', '600000.SH'],   # 股票代码列表
    period='1d',                            # 数据周期：'1d'（日线）、'1m'（分钟）
    adjust='qfq',                           # 复权方式：'qfq'（前复权）、'hfq'、'bfq'
    source='baostock',                      # 数据来源：'baostock'（默认）、'akshare'、'qmt'
    pool_size=10,                           # 并发下载线程数（仅 akshare 有效）
)
```

### 数据源对比

| 数据源 | 默认 | 特点 |
|--------|------|------|
| **baostock** | ✅ 默认 | 稳定，登录后串行下载，适合首次全量下载 |
| akshare | 备选 | HTTP 协议支持并发，但个股接口常被限流 |
| qmt | QMT 专用 | 实盘交易数据源，通过 xtquant 获取 |

!!! tip "baostock 登录"
    baostock 使用 C/S 架构，首次使用需要登录。QKA 在 `Data` 初次调用 `get()` 时自动完成登录。

---

## 懒加载模式（Lazy Mode）

`Data.get(lazy=True)` 返回 dask DataFrame，此时只是构建了**计算图**，不会真正加载数据到内存。

```python
data = Data(symbols=['000001.SZ', '600000.SH'], source='baostock')
lazy_df = data.get(lazy=True)
# lazy_df 是 dd.DataFrame — 尚未读取任何 parquet
```

这个模式的主要用途：

1. **大规模回测** — Backtest.run() 内部会自动使用 lazy 模式
2. **自定义分区** — 可自行操作 dask DataFrame 后再传给 Backtest
3. **内存控制** — 数百只股票数年的数据不会一次性加载

---

## 自定义因子

通过 `factor` 参数扩展自定义技术指标：

```python
import pandas as pd

def add_moving_average(df: pd.DataFrame) -> pd.DataFrame:
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    return df

data = Data(
    symbols=['000001.SZ'],
    factor=add_moving_average,
)

# 在策略中可以通过 self.get('ma5') 获取
```

!!! note "自定义因子与 dask"
    自定义因子函数接收 **单只股票的 pandas DataFrame**，返回添加了额外列的 DataFrame。
    与 dask 模式完全兼容。

---

## 数据格式

`Data.get()` 返回的 DataFrame 列名格式为 `{symbol}_{factor}`：

| 列名 | 含义 |
|------|------|
| `000001.SZ_close` | 平安银行收盘价 |
| `000001.SZ_open` | 平安银行开盘价 |
| `000001.SZ_high` | 平安银行最高价 |
| `000001.SZ_low` | 平安银行最低价 |
| `000001.SZ_volume` | 平安银行成交量 |
| `600000.SH_close` | 浦发银行收盘价 |
| ... | ... |

这种命名方式避免了 MultiIndex 在 dask 计算中的兼容性问题，同时通过前缀保留了股票代码信息。

---

## 缓存管理

数据缓存目录结构：

```
datadir/
└── baostock/
    └── 1d/
        └── qfq/
            ├── 000001.SZ.parquet
            ├── 600000.SH.parquet
            └── ...
```

如需清除缓存，删除 `datadir/` 目录即可：

```bash
rm -rf datadir/
```
