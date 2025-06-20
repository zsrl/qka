# 数据获取

QKA 提供了统一的数据获取接口，目前支持QMT和Akshare两种数据源。

## 支持的数据源

- **QMT** - 迅投QMT数据源，支持历史数据和实时数据
- **Akshare** - 开源财经数据接口，支持历史数据（默认数据源）

## 快速开始

### 设置默认数据源

```python
import qka

# 查看可用的数据源
print(qka.get_available_sources())  # ['qmt', 'akshare']

# 设置默认数据源（推荐在程序开始时设置）
qka.set_source('akshare')  # 或 'qmt'

# 查看当前默认数据源
print(qka.get_source())  # akshare
```

### 简化的数据获取

设置默认数据源后，创建数据对象更加简洁：

```python
import qka

# 设置默认数据源
qka.set_source('akshare')

# 创建数据对象（自动使用默认数据源）
data_obj = qka.data(stocks=['000001', '600000'])

# 获取历史数据
hist_data = data_obj.get(
    start_time='2023-01-01',
    end_time='2023-12-31'
)
```

## 基本用法

### 使用QMT数据源

```python
import qka

# 方式1：设置为默认数据源
qka.set_source('qmt')
data_obj = qka.data(stocks=['000001.SZ', '600000.SH'])

# 方式2：临时指定数据源
data_obj = qka.data(stocks=['000001.SZ', '600000.SH'], source='qmt')

# 获取历史数据
hist_data = data_obj.get(
    period='1d',
    start_time='2023-01-01', 
    end_time='2023-12-31'
)

# 订阅实时数据（需要QMT环境）
def on_data(code, item):
    print(f"{code}: 价格={item['lastPrice']}")

data_obj.subscribe(on_data)
```

### 使用Akshare数据源

```python
import qka

# 方式1：使用默认数据源（akshare为默认）
data_obj = qka.data(stocks=['000001', '600000'])

# 方式2：显式指定数据源
data_obj = qka.data(stocks=['000001', '600000'], source='akshare')

# 获取历史数据
hist_data = data_obj.get(
    start_time='2023-01-01',
    end_time='2023-12-31'
)

# 注意：Akshare不支持实时数据订阅
```

### 板块数据获取

```python
import qka

# 使用QMT获取板块股票
qka.set_source('qmt')
data_obj = qka.data(sector='沪深A股主板')

# 使用Akshare获取沪深A股（限制前100只）
qka.set_source('akshare')
data_obj = qka.data(sector='沪深A股')

# 获取板块内所有股票的历史数据
hist_data = data_obj.get(start_time='2023-01-01')
```

## 扩展数据源

QKA支持注册自定义数据源：

```python
import qka
from qka.core.data.base import DataSource

# 自定义数据源示例
class TushareData(DataSource):
    def get_historical_data(self, period='1d', start_time='', end_time=''):
        # 实现tushare数据获取逻辑
        pass
    
    def subscribe_realtime(self, callback):
        # 实现实时数据订阅逻辑
        pass

# 注册新数据源
qka.register_data_source('tushare', TushareData)

# 使用新数据源
qka.set_source('tushare')
data_obj = qka.data(stocks=['000001'])
```

## 数据格式

QKA统一了不同数据源的数据格式，返回标准的pandas DataFrame：

```python
# 查看数据结构
print(hist_data.keys())  # 获取股票列表
print(hist_data['000001'].head())  # 查看具体股票数据

# 标准数据列
# open: 开盘价
# high: 最高价  
# low: 最低价
# close: 收盘价
# volume: 成交量
# amount: 成交额（Akshare提供）
```

## 数据源差异

### QMT数据源特点
- ✅ 支持历史数据和实时数据
- ✅ 数据质量高，延迟低
- ✅ 支持多种周期（日线、分钟线等）
- ❗ 需要安装QMT软件环境

### Akshare数据源特点  
- ✅ 免费开源，无需授权
- ✅ 支持前复权数据调整
- ✅ 安装简单，依赖较少
- ❌ 不支持实时数据订阅
- ❗ 仅支持日线数据

## 股票代码格式

不同数据源的股票代码格式：

| 数据源 | 格式示例 | 说明 |
|--------|----------|------|
| QMT | `000001.SZ` | 带交易所后缀 |
| QMT | `600000.SH` | 沪市股票 |
| Akshare | `000001` | 不带后缀 |
| Akshare | `600000` | 6位数字代码 |

## 常用数据字段

基础数据字段（所有数据源共有）：

| 字段名 | 描述 | 类型 |
|--------|------|------|
| open | 开盘价 | float |
| high | 最高价 | float |
| low | 最低价 | float |
| close | 收盘价 | float |
| volume | 成交量 | int |

Akshare额外提供的字段：

| 字段名 | 描述 | 类型 |
|--------|------|------|
| amount | 成交额 | float |

## 错误处理

```python
try:
    # 使用新的API方式
    qka.set_source('qmt')
    data_obj = qka.data(stocks=['000001.SZ'])
    hist_data = data_obj.get(start_time='2023-01-01')
except ImportError as e:
    print(f"数据源依赖缺失: {e}")
except Exception as e:
    print(f"数据获取失败: {e}")
```

## 注意事项

1. **默认数据源设置**：建议在程序开始时设置默认数据源，避免重复指定
2. **QMT环境依赖**：使用QMT数据源需要安装QMT软件和xtquant库
3. **Akshare限制**：仅支持日线数据，不支持实时数据订阅
4. **股票代码格式**：QMT需要带交易所后缀，Akshare使用6位数字代码
5. **数据获取频率**：避免过于频繁的API调用
6. **数据源扩展**：可以通过`register_data_source()`注册自定义数据源

## API参考

### 配置函数

- `qka.set_source(source)` - 设置默认数据源
- `qka.get_source()` - 获取当前默认数据源
- `qka.get_available_sources()` - 获取所有可用数据源
- `qka.register_data_source(name, class)` - 注册新数据源

### 工厂函数

- `qka.data(stocks=None, sector=None, source=None)` - 创建数据对象

### Data对象方法

- `data_obj.get(period='1d', start_time='', end_time='')` - 获取历史数据
- `data_obj.subscribe(callback)` - 订阅实时数据
- `data_obj.stocks` - 获取股票列表

## 完整示例

### 基础使用流程

```python
import qka

# 1. 设置默认数据源
qka.set_source('akshare')

# 2. 创建数据对象
data_obj = qka.data(stocks=['000001', '600000'])

# 3. 获取历史数据
hist_data = data_obj.get(start_time='2023-01-01', end_time='2023-12-31')

# 4. 查看数据
for stock_code, df in hist_data.items():
    print(f"\n{stock_code} 数据概览:")
    print(df.head())
    print(f"数据行数: {len(df)}")
```

### 混合使用多个数据源

```python
import qka

# 设置默认数据源为akshare
qka.set_source('akshare')

# 大部分使用默认数据源
data_ak = qka.data(stocks=['000001', '600000'])
hist_data_ak = data_ak.get(start_time='2023-01-01')

# 临时使用QMT获取实时数据
data_qmt = qka.data(stocks=['000001.SZ'], source='qmt')
def on_realtime_data(code, item):
    print(f"实时数据 - {code}: {item['lastPrice']}")

data_qmt.subscribe(on_realtime_data)
```
