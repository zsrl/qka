# QKA 增强功能文档 - 阶段1

## 概述

QKA 阶段1增强功能主要包括四个核心模块：
- 📋 **配置管理系统** - 统一的配置管理
- 📡 **事件驱动框架** - 发布-订阅模式的事件系统  
- 📝 **增强日志系统** - 结构化和彩色日志
- 🛠️ **基础工具类** - 通用工具函数和装饰器

---

## 📋 配置管理系统

### 快速开始

```python
import qka
from qka.core.config import load_config, create_sample_config

# 创建示例配置文件
create_sample_config('my_config.json')

# 加载配置
config = load_config('my_config.json')

# 使用配置
print(f"初始资金: {qka.config.backtest.initial_cash:,}")
print(f"数据源: {qka.config.data.default_source}")
```

### 配置结构

#### BacktestConfig - 回测配置
```python
config.backtest.initial_cash = 1_000_000     # 初始资金
config.backtest.commission_rate = 0.0003     # 手续费率
config.backtest.slippage = 0.001             # 滑点率
config.backtest.min_trade_amount = 100       # 最小交易股数
config.backtest.max_position_ratio = 0.3     # 单只股票最大仓位比例
config.backtest.benchmark = '000300.SH'      # 基准指数
```

#### DataConfig - 数据配置
```python
config.data.default_source = 'akshare'       # 默认数据源
config.data.cache_enabled = True             # 是否启用缓存
config.data.cache_dir = './data_cache'       # 缓存目录
config.data.cache_expire_days = 7            # 缓存过期天数
config.data.quality_check = True             # 是否进行数据质量检查
config.data.auto_download = True             # 是否自动下载缺失数据
```

#### TradingConfig - 交易配置
```python
config.trading.server_host = '0.0.0.0'       # 服务器地址
config.trading.server_port = 8000            # 服务器端口
config.trading.token_auto_generate = True    # 自动生成token
config.trading.order_timeout = 30            # 订单超时时间(秒)
config.trading.max_retry_times = 3           # 最大重试次数
config.trading.heartbeat_interval = 30       # 心跳间隔(秒)
```

### 环境变量支持

```bash
# 设置环境变量
export QKA_INITIAL_CASH=2000000
export QKA_DATA_SOURCE=qmt
export QKA_SERVER_PORT=9000
```

### 配置文件示例

```json
{
  "backtest": {
    "initial_cash": 1000000,
    "commission_rate": 0.0003,
    "slippage": 0.001
  },
  "data": {
    "default_source": "akshare",
    "cache_enabled": true,
    "cache_dir": "./data_cache"
  },
  "trading": {
    "server_host": "0.0.0.0",
    "server_port": 8000
  }
}
```

---

## 📡 事件驱动框架

### 快速开始

```python
from qka.core.events import EventType, event_handler, emit_event, start_event_engine

# 启动事件引擎
start_event_engine()

# 定义事件处理器
@event_handler(EventType.DATA_LOADED)
def on_data_loaded(event):
    print(f"数据加载完成: {event.data}")

# 发送事件
emit_event(EventType.DATA_LOADED, {"symbol": "000001.SZ", "count": 1000})
```

### 事件类型

#### 数据相关事件
- `DATA_LOADED` - 数据加载完成
- `DATA_ERROR` - 数据加载错误

#### 回测相关事件
- `BACKTEST_START` - 回测开始
- `BACKTEST_END` - 回测结束
- `BACKTEST_ERROR` - 回测错误

#### 交易相关事件
- `ORDER_CREATED` - 订单创建
- `ORDER_FILLED` - 订单成交
- `ORDER_CANCELLED` - 订单取消
- `ORDER_ERROR` - 订单错误

#### 策略相关事件
- `STRATEGY_START` - 策略开始
- `STRATEGY_END` - 策略结束
- `SIGNAL_GENERATED` - 信号生成

### 自定义事件处理器

```python
from qka.core.events import EventHandler, Event

class MyEventHandler(EventHandler):
    def handle(self, event: Event):
        if event.event_type == EventType.ORDER_FILLED:
            print(f"处理订单成交事件: {event.data}")
    
    def can_handle(self, event: Event) -> bool:
        return event.event_type == EventType.ORDER_FILLED

# 注册处理器
handler = MyEventHandler()
event_engine.subscribe(EventType.ORDER_FILLED, handler)
```

### 事件统计

```python
# 获取事件统计信息
stats = event_engine.get_statistics()
print(f"事件计数: {stats['event_count']}")
print(f"错误计数: {stats['error_count']}")
print(f"队列大小: {stats['queue_size']}")
```

---

## 📝 增强日志系统

### 快速开始

```python
from qka.utils.logger import create_logger, get_structured_logger

# 创建彩色日志记录器
logger = create_logger('my_app', colored_console=True)

logger.debug("这是调试信息")
logger.info("这是普通信息")
logger.warning("这是警告信息")
logger.error("这是错误信息")
```

### 结构化日志

```python
# 创建结构化日志记录器
struct_logger = get_structured_logger('my_app')

# 记录结构化日志
struct_logger.info("用户登录", 
                  user_id=12345, 
                  ip="192.168.1.100", 
                  action="login")

struct_logger.error("交易失败", 
                   symbol="000001.SZ", 
                   reason="余额不足", 
                   amount=10000)
```

### 日志配置选项

```python
logger = create_logger(
    name='my_app',                    # 日志记录器名称
    level='INFO',                     # 日志级别
    console_output=True,              # 是否输出到控制台
    file_output=True,                 # 是否输出到文件
    log_dir='logs',                   # 日志文件目录
    max_file_size='10MB',             # 最大文件大小
    backup_count=10,                  # 备份文件数量
    json_format=False,                # 是否使用JSON格式
    colored_console=True              # 控制台是否使用颜色
)
```

### 微信通知

```python
from qka.utils.logger import add_wechat_handler

# 添加微信通知处理器
webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
add_wechat_handler(logger, webhook_url, level='ERROR')

# 现在ERROR级别的日志会发送到微信
logger.error("这条错误信息会发送到微信群")
```

---

## 🛠️ 基础工具类

### 缓存工具

```python
from qka.utils.tools import Cache

# 创建缓存
cache = Cache(max_size=1000, ttl=3600)  # 最大1000条，1小时过期

# 使用缓存
cache.set('key1', 'value1')
value = cache.get('key1')
print(f"缓存大小: {cache.size()}")
```

### 计时器工具

```python
from qka.utils.tools import Timer, timer

# 使用上下文管理器
with Timer() as t:
    # 一些耗时操作
    time.sleep(1)
print(f"耗时: {t.elapsed():.3f}秒")

# 使用装饰器
@timer
def slow_function():
    time.sleep(1)
    return "完成"

result = slow_function()  # 自动打印执行时间
```

### 重试装饰器

```python
from qka.utils.tools import retry

@retry(max_attempts=3, delay=1.0, backoff=2.0)
def unreliable_function():
    # 可能失败的函数
    import random
    if random.random() < 0.7:
        raise Exception("随机失败")
    return "成功"

result = unreliable_function()  # 自动重试
```

### 记忆化装饰器

```python
from qka.utils.tools import memoize

@memoize(ttl=300)  # 缓存5分钟
def expensive_calculation(x, y):
    time.sleep(1)  # 模拟耗时计算
    return x * y

result1 = expensive_calculation(10, 20)  # 耗时1秒
result2 = expensive_calculation(10, 20)  # 从缓存返回，瞬间完成
```

### 文件工具

```python
from qka.utils.tools import FileUtils

# JSON文件操作
data = {"key": "value"}
FileUtils.save_json(data, "data.json")
loaded_data = FileUtils.load_json("data.json")

# Pickle文件操作
FileUtils.save_pickle(data, "data.pkl")
loaded_data = FileUtils.load_pickle("data.pkl")

# 文件信息
size = FileUtils.get_file_size("data.json")
mtime = FileUtils.get_file_mtime("data.json")
```

### 格式化工具

```python
from qka.utils.tools import format_number, format_percentage, format_currency

print(format_number(1234567.89))        # 1,234,567.89
print(format_percentage(0.1234))        # 12.34%
print(format_currency(123456.78))       # ¥123,456.78
```

### 验证工具

```python
from qka.utils.tools import ValidationUtils

# 验证股票代码
is_valid = ValidationUtils.is_valid_symbol("000001.SZ")  # True
is_valid = ValidationUtils.is_valid_symbol("AAPL")       # False

# 验证正数
is_positive = ValidationUtils.is_positive_number(100)    # True
is_positive = ValidationUtils.is_positive_number(-10)    # False

# 验证日期范围
is_valid_range = ValidationUtils.is_valid_date_range("2023-01-01", "2023-12-31")  # True
```

---

## 🚀 集成使用示例

### 增强的策略类

```python
from qka.core.backtest import Strategy
from qka.core.events import EventType, emit_event
from qka.utils.logger import create_logger
from qka.utils.tools import timer

class EnhancedStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.logger = create_logger('strategy')
    
    def on_start(self, broker):
        self.logger.info(f"策略启动: {self.name}")
        emit_event(EventType.STRATEGY_START, {"strategy": self.name})
    
    @timer
    def on_bar(self, data, broker, current_date):
        # 策略逻辑
        for symbol, df in data.items():
            if len(df) >= 20:
                current_price = df['close'].iloc[-1]
                ma20 = df['close'].rolling(20).mean().iloc[-1]
                
                if current_price > ma20:
                    emit_event(EventType.SIGNAL_GENERATED, {
                        "symbol": symbol,
                        "signal": "BUY",
                        "price": current_price
                    })
                    broker.buy(symbol, 0.3, current_price)
    
    def on_end(self, broker):
        self.logger.info(f"策略结束: {self.name}")
        emit_event(EventType.STRATEGY_END, {"strategy": self.name})
```

### 完整使用流程

```python
import qka
from qka.core.config import load_config
from qka.core.events import start_event_engine, stop_event_engine

# 1. 加载配置
config = load_config('my_config.json')

# 2. 启动事件系统
start_event_engine()

# 3. 获取数据
data_obj = qka.data(config.data.default_source, stocks=['000001', '000002'])

# 4. 运行回测
result = qka.backtest(
    data=data_obj,
    strategy=EnhancedStrategy(),
    start_time='2023-01-01',
    end_time='2023-12-31'
)

# 5. 查看结果
print(f"总收益率: {result['total_return']:.2%}")

# 6. 清理
stop_event_engine()
```

---

## 📚 API 参考

### 配置管理 API

| 函数/类 | 说明 |
|---------|------|
| `Config()` | 配置管理器类 |
| `load_config(file_path)` | 加载配置文件 |
| `create_sample_config(file_path)` | 创建示例配置 |
| `config.get(section, key, default)` | 获取配置值 |
| `config.set(section, key, value)` | 设置配置值 |

### 事件系统 API

| 函数/类 | 说明 |
|---------|------|
| `start_event_engine()` | 启动事件引擎 |
| `stop_event_engine()` | 停止事件引擎 |
| `emit_event(event_type, data)` | 发送事件 |
| `@event_handler(event_type)` | 事件处理器装饰器 |
| `event_engine.get_statistics()` | 获取事件统计 |

### 日志系统 API

| 函数/类 | 说明 |
|---------|------|
| `create_logger(name, **options)` | 创建日志记录器 |
| `get_structured_logger(name)` | 创建结构化日志记录器 |
| `add_wechat_handler(logger, webhook_url)` | 添加微信通知 |

### 工具类 API

| 函数/类 | 说明 |
|---------|------|
| `Cache(max_size, ttl)` | 内存缓存类 |
| `Timer()` | 计时器类 |
| `@timer` | 计时装饰器 |
| `@retry(max_attempts, delay)` | 重试装饰器 |
| `@memoize(ttl)` | 记忆化装饰器 |
| `FileUtils` | 文件操作工具类 |
| `ValidationUtils` | 验证工具类 |

---

## 🔄 下一阶段预告

**阶段2：数据层增强**
- 数据缓存机制
- 数据质量检查和清洗
- 增量数据更新
- 多频率数据支持
- 数据订阅管理器

敬请期待！ 🎉
