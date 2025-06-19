# 数据获取

QKA 提供了灵活的数据获取接口，支持多种数据源和格式。

## 数据源配置

在配置文件中设置数据源：

```json
{
  "data": {
    "default_source": "tushare",
    "cache_dir": "data/cache",
    "update_frequency": "daily",
    "sources": {
      "tushare": {
        "token": "your_tushare_token"
      },
      "akshare": {
        "enabled": true
      }
    }
  }
}
```

## 基本用法

### 获取股票数据

```python
import qka
from qka.core.data import get_stock_data

# 获取单只股票数据
data = get_stock_data('000001.SZ', start='2024-01-01', end='2024-12-31')
print(data.head())

# 获取多只股票数据
stocks = ['000001.SZ', '000002.SZ', '600000.SH']
data = get_stock_data(stocks, start='2024-01-01', end='2024-12-31')
```

### 获取指数数据

```python
from qka.core.data import get_index_data

# 获取上证指数数据
index_data = get_index_data('000001.SH', start='2024-01-01')
```

### 获取基本面数据

```python
from qka.core.data import get_fundamentals

# 获取财务数据
financial_data = get_fundamentals('000001.SZ', fields=['revenue', 'profit'])
```

## 数据预处理

### 数据清洗

```python
from qka.core.data import DataProcessor

processor = DataProcessor()

# 处理缺失值
clean_data = processor.handle_missing_data(data, method='forward_fill')

# 异常值处理
clean_data = processor.handle_outliers(clean_data, method='quantile', threshold=0.05)
```

### 数据标准化

```python
# 标准化数据
normalized_data = processor.normalize(data, method='z_score')

# 数据分片
train_data, test_data = processor.split_data(data, train_ratio=0.8)
```

## 缓存机制

QKA 自动缓存数据以提高性能：

```python
from qka.core.data import DataCache

cache = DataCache()

# 手动清理缓存
cache.clear()

# 设置缓存过期时间
cache.set_expiry(hours=24)
```

## 自定义数据源

### 实现数据源接口

```python
from qka.core.data import BaseDataSource

class CustomDataSource(BaseDataSource):
    def __init__(self, config):
        super().__init__(config)
    
    def get_stock_data(self, symbol, start, end):
        # 实现自定义数据获取逻辑
        pass
    
    def get_index_data(self, symbol, start, end):
        # 实现自定义指数数据获取
        pass
```

### 注册数据源

```python
from qka.core.data import register_data_source

register_data_source('custom', CustomDataSource)
```

## 数据质量检查

```python
from qka.core.data import DataQualityChecker

checker = DataQualityChecker()

# 检查数据完整性
quality_report = checker.check_completeness(data)

# 检查数据一致性
consistency_report = checker.check_consistency(data)

# 生成数据质量报告
report = checker.generate_report(data)
print(report)
```

## 常用数据字段

| 字段名 | 描述 | 类型 |
|--------|------|------|
| open | 开盘价 | float |
| high | 最高价 | float |
| low | 最低价 | float |
| close | 收盘价 | float |
| volume | 成交量 | int |
| amount | 成交额 | float |
| turnover_rate | 换手率 | float |
| pe_ratio | 市盈率 | float |
| pb_ratio | 市净率 | float |

## 错误处理

```python
from qka.core.data import DataError

try:
    data = get_stock_data('INVALID_CODE')
except DataError as e:
    print(f"数据获取失败: {e}")
```

## 最佳实践

1. **合理设置缓存**：对于不经常变化的数据，设置较长的缓存时间
2. **分批获取**：对于大量股票数据，分批获取以避免API限制
3. **错误重试**：网络请求失败时自动重试
4. **数据验证**：获取数据后进行基本的质量检查

## API 参考

数据处理的详细API参考请查看 [Data API文档](../api/core/data.md)。

### 主要模块功能

- 数据获取接口
- 数据清洗和预处理
- 数据缓存和存储
- 数据格式转换

更多详细信息请参考API文档页面。
