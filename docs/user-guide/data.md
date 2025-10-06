# 数据获取

QKA 提供统一的数据获取接口，支持多种数据源和灵活的数据处理。

## 基本用法

### 创建数据对象

```python
import qka

# 最简单的数据获取
data = qka.Data(symbols=['000001.SZ', '600000.SH'])
df = data.get()
```

### 参数说明

```python
data = qka.Data(
    symbols=['000001.SZ', '600000.SH'],  # 股票代码列表
    period='1d',                         # 数据周期
    adjust='qfq',                        # 复权方式
    source='akshare',                    # 数据源
    pool_size=10,                        # 并发线程数
    datadir='./mydata'                   # 缓存目录
)
```

## 数据周期

支持多种数据周期：

```python
# 日线数据
daily_data = qka.Data(symbols=['000001.SZ'], period='1d')

# 分钟线数据（如果数据源支持）
minute_data = qka.Data(symbols=['000001.SZ'], period='1m')

# 周线数据
weekly_data = qka.Data(symbols=['000001.SZ'], period='1w')
```

## 复权方式

支持三种复权方式：

```python
# 前复权（推荐）
qfq_data = qka.Data(symbols=['000001.SZ'], adjust='qfq')

# 后复权
hfq_data = qka.Data(symbols=['000001.SZ'], adjust='hfq')

# 不复权
bfq_data = qka.Data(symbols=['000001.SZ'], adjust='bfq')
```

## 数据源配置

### Akshare 数据源

Akshare 是默认的数据源，提供丰富的 A 股数据：

```python
data = qka.Data(
    symbols=['000001.SZ', '600000.SH'],
    source='akshare'
)
```

### 自定义数据源

你可以扩展 Data 类来支持其他数据源：

```python
class MyData(qka.Data):
    def _get_from_custom_source(self, symbol: str):
        # 实现自定义数据获取逻辑
        pass
```

## 因子计算

### 内置因子

数据获取时自动包含基础因子：

- `open`: 开盘价
- `high`: 最高价  
- `low`: 最低价
- `close`: 收盘价
- `volume`: 成交量
- `amount`: 成交额

### 自定义因子

可以通过 `factor` 参数添加自定义因子：

```python
def add_technical_indicators(df):
    """添加技术指标"""
    # 移动平均
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    
    # 相对强弱指标 (RSI)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df

data = qka.Data(
    symbols=['000001.SZ'],
    factor=add_technical_indicators
)
```

## 并发下载

使用多线程并发下载提高效率：

```python
# 设置并发线程数
data = qka.Data(
    symbols=large_stock_list,  # 大量股票
    pool_size=20               # 增加并发数
)
```

## 数据缓存

### 自动缓存

数据会自动缓存到本地，避免重复下载：

```python
# 第一次下载数据
data1 = qka.Data(symbols=['000001.SZ'])
df1 = data1.get()  # 下载并缓存

# 第二次使用相同参数，直接从缓存读取
data2 = qka.Data(symbols=['000001.SZ'])  
df2 = data2.get()  # 从缓存读取
```

### 自定义缓存目录

```python
from pathlib import Path

data = qka.Data(
    symbols=['000001.SZ'],
    datadir=Path('/path/to/cache')  # 自定义缓存目录
)
```

## 数据格式

### 返回数据格式

`data.get()` 返回 Dask DataFrame，每只股票的列名格式为 `{symbol}_{column}`：

```python
df = data.get()
print(df.columns)
# 输出: ['000001.SZ_open', '000001.SZ_high', '000001.SZ_low', 
#        '000001.SZ_close', '000001.SZ_volume', '000001.SZ_amount',
#        '600000.SH_open', ...]
```

### 数据访问

```python
# 获取特定股票的数据
stock_000001 = df[['000001.SZ_open', '000001.SZ_close']]

# 获取特定因子的所有股票数据
all_close = df[[col for col in df.columns if col.endswith('_close')]]
```

## 高级用法

### 批量处理大量股票

```python
# 获取A股所有股票列表（需要akshare）
import akshare as ak
stock_list = ak.stock_info_a_code_name()['code'].tolist()

# 分批处理
batch_size = 100
for i in range(0, len(stock_list), batch_size):
    batch = stock_list[i:i+batch_size]
    data = qka.Data(symbols=batch, pool_size=10)
    df_batch = data.get()
    # 处理这批数据...
```

### 数据更新

```python
# 强制更新缓存（重新下载）
import shutil
shutil.rmtree('datadir')  # 删除缓存目录

# 或者指定新的缓存目录
data = qka.Data(symbols=['000001.SZ'], datadir='./new_cache')
```

## 性能优化建议

1. **合理设置并发数**: 根据网络情况和系统资源调整 `pool_size`
2. **使用缓存**: 充分利用数据缓存避免重复下载
3. **分批处理**: 对于大量股票，分批处理避免内存不足
4. **选择合适的周期**: 根据策略需求选择合适的数据周期

## 常见问题

### Q: 数据下载失败怎么办？

A: 检查网络连接，确认股票代码格式正确，可以尝试：
- 减少并发数
- 更换数据源
- 检查股票代码是否有效

### Q: 如何获取实时数据？

A: 目前主要支持历史数据，实时数据可以通过 QMT 接口获取。

### Q: 数据包含哪些时间段？

A: 默认包含该股票的所有可用历史数据。

## 下一步

- 学习 [回测分析](backtest.md) 了解如何使用数据进行策略回测
- 查看 [API 文档](../api/core/data.md) 了解完整的数据接口
- 参考 [示例教程](../examples/basic/data-fetching.md) 获取更多代码示例