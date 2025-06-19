# Tools API 参考

::: qka.utils.tools
    options:
      show_root_heading: true
      show_source: true
      heading_level: 2
      members_order: source
      show_signature_annotations: true
      separate_signature: true

## 工具类使用指南

### 缓存装饰器

#### 基本缓存

```python
from qka.utils.tools import cache

# 简单缓存（内存）
@cache()
def expensive_function(x, y):
    # 模拟耗时计算
    import time
    time.sleep(2)
    return x + y

# 第一次调用需要2秒
result1 = expensive_function(1, 2)  # 耗时：2秒

# 第二次调用直接返回缓存结果
result2 = expensive_function(1, 2)  # 耗时：几乎为0
```

#### 带TTL的缓存

```python
# 缓存有效期为5分钟
@cache(ttl=300)
def get_stock_price(symbol):
    # 模拟API调用
    return fetch_price_from_api(symbol)

# 5分钟内重复调用返回缓存结果
# 5分钟后会重新调用API
price = get_stock_price('AAPL')
```

#### 文件缓存

```python
# 使用文件缓存（持久化）
@cache(cache_type='file', cache_dir='cache')
def process_large_dataset(file_path):
    # 处理大型数据集
    return expensive_data_processing(file_path)

# 结果会保存到文件，程序重启后仍然有效
result = process_large_dataset('data/large_file.csv')
```

#### Redis缓存

```python
# 使用Redis缓存（分布式）
@cache(cache_type='redis', redis_url='redis://localhost:6379/0')
def get_user_profile(user_id):
    return fetch_user_from_database(user_id)

# 多个进程/服务器可以共享缓存
profile = get_user_profile(12345)
```

### 计时装饰器

#### 函数计时

```python
from qka.utils.tools import timeit

# 简单计时
@timeit
def data_processing():
    # 数据处理逻辑
    pass

# 执行后会打印执行时间
data_processing()  # 输出: data_processing 执行时间: 1.23秒
```

#### 详细计时信息

```python
# 详细计时信息
@timeit(detailed=True)
def complex_calculation(n):
    result = 0
    for i in range(n):
        result += i * i
    return result

# 输出更详细的时间信息
result = complex_calculation(1000000)
# 输出: complex_calculation(n=1000000) 执行时间: 0.15秒, 内存使用: +2.3MB
```

#### 性能监控

```python
# 性能监控和统计
@timeit(monitor=True, threshold=1.0)
def api_call(endpoint):
    # API调用
    return make_request(endpoint)

# 如果执行时间超过阈值，会记录警告
# 同时收集性能统计数据
api_call('/api/data')

# 获取性能统计
stats = timeit.get_statistics()
print(f"平均执行时间: {stats['avg_time']}")
print(f"最大执行时间: {stats['max_time']}")
```

### 重试装饰器

#### 基本重试

```python
from qka.utils.tools import retry

# 最多重试3次
@retry(max_attempts=3)
def unstable_api_call():
    # 可能失败的API调用
    response = requests.get('https://api.example.com/data')
    response.raise_for_status()
    return response.json()

# 如果失败会自动重试
data = unstable_api_call()
```

#### 指定异常类型和重试间隔

```python
import requests

# 只对特定异常重试，指定重试间隔
@retry(
    max_attempts=5,
    exceptions=(requests.RequestException, ConnectionError),
    delay=1.0,
    backoff=2.0
)
def robust_api_call():
    return requests.get('https://api.example.com/data').json()

# 重试间隔：1秒、2秒、4秒、8秒
data = robust_api_call()
```

#### 自定义重试条件

```python
# 自定义重试条件
def should_retry(exception):
    if isinstance(exception, requests.HTTPError):
        return exception.response.status_code >= 500
    return True

@retry(max_attempts=3, should_retry=should_retry)
def smart_api_call():
    response = requests.get('https://api.example.com/data')
    response.raise_for_status()
    return response.json()
```

### 文件操作工具

#### 基本文件操作

```python
from qka.utils.tools import FileHelper

helper = FileHelper()

# 确保目录存在
helper.ensure_dir('logs')
helper.ensure_dir('data/processed')

# 安全写入文件（原子操作）
data = {'key': 'value'}
helper.safe_write('config.json', data)

# 安全读取文件
config = helper.safe_read('config.json')

# 备份文件
helper.backup_file('important.txt')
```

#### 文件监控

```python
# 监控文件变化
def on_file_change(file_path):
    print(f"文件 {file_path} 已更改")

helper.watch_file('config.json', on_file_change)

# 监控目录变化
def on_dir_change(event_type, file_path):
    print(f"目录事件: {event_type} - {file_path}")

helper.watch_directory('data', on_dir_change)
```

#### 文件压缩和解压

```python
# 压缩文件
helper.compress_file('large_file.txt', 'compressed.gz')

# 压缩目录
helper.compress_directory('logs', 'logs_backup.tar.gz')

# 解压文件
helper.extract_file('backup.tar.gz', 'restore_dir')
```

### 格式化工具

#### 数据格式化

```python
from qka.utils.tools import FormatHelper

formatter = FormatHelper()

# 格式化数字
formatted = formatter.format_number(1234567.89)
print(formatted)  # 1,234,567.89

# 格式化百分比
percentage = formatter.format_percentage(0.1234)
print(percentage)  # 12.34%

# 格式化文件大小
size = formatter.format_size(1024*1024*1.5)
print(size)  # 1.5 MB

# 格式化时间段
duration = formatter.format_duration(3661)
print(duration)  # 1小时1分1秒
```

#### 货币格式化

```python
# 格式化货币
price = formatter.format_currency(1234.56, currency='USD')
print(price)  # $1,234.56

price_cny = formatter.format_currency(8888.88, currency='CNY')
print(price_cny)  # ¥8,888.88
```

#### 日期时间格式化

```python
from datetime import datetime

now = datetime.now()

# 不同格式的日期时间
print(formatter.format_datetime(now, 'full'))     # 2024年1月15日 星期一 14:30:25
print(formatter.format_datetime(now, 'date'))     # 2024-01-15
print(formatter.format_datetime(now, 'time'))     # 14:30:25
print(formatter.format_datetime(now, 'relative')) # 刚刚
```

### 数据验证工具

#### 基本验证

```python
from qka.utils.tools import ValidationHelper

validator = ValidationHelper()

# 验证邮箱
is_valid = validator.validate_email('user@example.com')
print(is_valid)  # True

# 验证手机号
is_valid = validator.validate_phone('13812345678')
print(is_valid)  # True

# 验证身份证号
is_valid = validator.validate_id_card('110101199001011234')
print(is_valid)  # False (示例号码)
```

#### 数据结构验证

```python
# 验证字典结构
schema = {
    'name': {'type': str, 'required': True},
    'age': {'type': int, 'min': 0, 'max': 150},
    'email': {'type': str, 'validator': validator.validate_email}
}

data = {
    'name': 'John Doe',
    'age': 30,
    'email': 'john@example.com'
}

is_valid, errors = validator.validate_dict(data, schema)
if not is_valid:
    print("验证失败:", errors)
```

#### 自定义验证器

```python
# 自定义验证函数
def validate_stock_symbol(symbol):
    return isinstance(symbol, str) and symbol.isupper() and len(symbol) <= 6

# 注册自定义验证器
validator.register_validator('stock_symbol', validate_stock_symbol)

# 使用自定义验证器
is_valid = validator.validate('AAPL', 'stock_symbol')
print(is_valid)  # True
```

### 配置管理工具

#### 环境配置

```python
from qka.utils.tools import ConfigHelper

config = ConfigHelper()

# 获取环境变量（带默认值）
debug_mode = config.get_env('DEBUG', default=False, cast=bool)
api_timeout = config.get_env('API_TIMEOUT', default=30, cast=int)

# 检查必需的环境变量
required_vars = ['DATABASE_URL', 'SECRET_KEY']
missing = config.check_required_env(required_vars)
if missing:
    raise ValueError(f"缺少必需的环境变量: {missing}")
```

#### 配置合并

```python
# 合并多个配置源
default_config = {'host': 'localhost', 'port': 8000, 'debug': False}
user_config = {'port': 9000, 'debug': True}
env_config = config.from_env_prefix('APP_')

final_config = config.merge_configs(default_config, user_config, env_config)
print(final_config)  # {'host': 'localhost', 'port': 9000, 'debug': True}
```

## 组合使用示例

### 完整的数据处理流水线

```python
from qka.utils.tools import cache, timeit, retry, FileHelper, FormatHelper

# 组合多个装饰器
@cache(ttl=3600)  # 缓存1小时
@timeit(detailed=True)  # 详细计时
@retry(max_attempts=3)  # 最多重试3次
def process_market_data(symbol, date):
    """处理市场数据的完整流水线"""
    
    # 下载数据
    raw_data = download_data(symbol, date)
    
    # 数据清洗
    cleaned_data = clean_data(raw_data)
    
    # 数据分析
    analysis_result = analyze_data(cleaned_data)
    
    # 保存结果
    helper = FileHelper()
    formatter = FormatHelper()
    
    output_file = f"analysis_{symbol}_{formatter.format_date(date)}.json"
    helper.safe_write(output_file, analysis_result)
    
    return analysis_result

# 使用
result = process_market_data('AAPL', '2024-01-15')
```

### 批量数据处理

```python
import concurrent.futures
from qka.utils.tools import timeit, cache

@cache(cache_type='redis')
def get_stock_data(symbol):
    return fetch_stock_data(symbol)

@timeit
def process_portfolio(symbols):
    """并行处理投资组合数据"""
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # 并行获取数据
        future_to_symbol = {
            executor.submit(get_stock_data, symbol): symbol 
            for symbol in symbols
        }
        
        results = {}
        for future in concurrent.futures.as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                data = future.result()
                results[symbol] = data
            except Exception as exc:
                print(f'{symbol} 处理失败: {exc}')
    
    return results

# 处理大型投资组合
portfolio = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA'] * 20
results = process_portfolio(portfolio)
```

## 最佳实践

1. **缓存策略**
   - 选择合适的缓存类型和TTL
   - 注意缓存一致性问题
   - 监控缓存命中率

2. **性能监控**
   - 对关键函数使用计时装饰器
   - 设置合理的性能阈值
   - 定期分析性能数据

3. **错误处理**
   - 合理设置重试策略
   - 记录重试和失败信息
   - 区分可重试和不可重试的错误

4. **文件操作**
   - 使用原子操作确保数据一致性
   - 定期备份重要文件
   - 监控磁盘空间使用
