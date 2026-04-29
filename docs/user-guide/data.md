# 数据获取

`Data` 负责从数据源下载 A 股行情数据并缓存到本地。

---

## 基本用法

```python
from qka.core.data import Data

data = Data(symbols=['000001.SZ', '600000.SH'])
df = data.get()   # 返回 dask DataFrame
```

默认从 **akshare** 获取数据，自动缓存到 `datadir/` 目录（parquet 格式）。下次运行直接读缓存。

---

## 参数说明

```python
Data(
    symbols=['000001.SZ', '600000.SH'],   # 股票代码列表
    period='1d',                            # 数据周期：'1d'（日线）、'1m'（分钟）
    adjust='qfq',                           # 复权方式：'qfq'（前复权）、'hfq'、'bfq'
    source='akshare',                       # 数据来源
    pool_size=10,                           # 并发下载线程数
)
```

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

# 在策略中可以直接 get('ma5') 获取
```

---

## 数据格式

`Data.get()` 返回的 DataFrame 格式为：

| 列名 | 含义 |
|------|------|
| `000001.SZ_close` | 平安银行收盘价 |
| `000001.SZ_open` | 平安银行开盘价 |
| `000001.SZ_high` | 平安银行最高价 |
| `000001.SZ_low` | 平安银行最低价 |
| `000001.SZ_volume` | 平安银行成交量 |
| `600000.SH_close` | 浦发银行收盘价 |
| ... | ... |

---

## 缓存管理

数据缓存目录结构：

```
datadir/
└── akshare/
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
