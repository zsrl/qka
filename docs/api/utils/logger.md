# Logger API 参考

::: qka.utils.logger
    options:
      show_root_heading: true
      show_source: true
      heading_level: 2
      members_order: source
      show_signature_annotations: true
      separate_signature: true

## 日志系统使用指南

### 基本用法

```python
from qka.utils.logger import Logger

# 创建日志实例
logger = Logger(name='my_app')

# 基本日志记录
logger.debug("调试信息")
logger.info("普通信息")
logger.warning("警告信息")
logger.error("错误信息")
logger.critical("严重错误")
```

### 彩色日志输出

```python
from qka.utils.logger import Logger, ColorFormatter

# 启用彩色输出
logger = Logger(name='colorful_app', enable_color=True)

# 日志会以不同颜色显示
logger.info("这是蓝色的信息日志")
logger.warning("这是黄色的警告日志")
logger.error("这是红色的错误日志")
```

### 结构化日志

```python
from qka.utils.logger import StructuredLogger

# 创建结构化日志记录器
logger = StructuredLogger(name='structured_app')

# 记录结构化日志
logger.info("用户登录", extra={
    'user_id': 12345,
    'username': 'john_doe',
    'ip_address': '192.168.1.100',
    'user_agent': 'Mozilla/5.0...'
})

logger.error("数据库连接失败", extra={
    'database': 'mysql',
    'host': 'localhost',
    'port': 3306,
    'error_code': 2003
})
```

### 文件日志配置

```python
# 配置文件日志
logger = Logger(
    name='file_app',
    log_file='logs/app.log',
    max_size='10MB',
    backup_count=5,
    compression=True
)

# 日志会自动轮转和压缩
for i in range(10000):
    logger.info(f"日志消息 {i}")
```

### 微信通知集成

```python
# 配置微信通知
logger = Logger(
    name='notify_app',
    wechat_webhook='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY'
)

# 发送重要通知到微信
logger.critical("系统出现严重错误", notify_wechat=True)
logger.error("数据库连接失败", notify_wechat=True)
```

### 性能监控日志

```python
import time
from qka.utils.logger import Logger

logger = Logger(name='perf_app')

# 记录函数执行时间
@logger.log_performance
def slow_function():
    time.sleep(2)
    return "完成"

# 记录代码块执行时间
with logger.timer("数据处理"):
    # 数据处理代码
    process_data()
```

### 日志过滤和格式化

```python
import logging
from qka.utils.logger import Logger

# 自定义日志过滤器
class SensitiveFilter(logging.Filter):
    def filter(self, record):
        # 过滤敏感信息
        if hasattr(record, 'msg'):
            record.msg = record.msg.replace('password=', 'password=***')
        return True

# 应用过滤器
logger = Logger(name='secure_app')
logger.logger.addFilter(SensitiveFilter())

# 自定义格式化器
formatter = logging.Formatter(
    '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger.set_formatter(formatter)
```

### 上下文日志

```python
from contextvars import ContextVar
from qka.utils.logger import Logger

# 定义上下文变量
request_id = ContextVar('request_id', default='unknown')

# 自定义格式化器
class ContextFormatter(logging.Formatter):
    def format(self, record):
        record.request_id = request_id.get()
        return super().format(record)

# 配置日志
logger = Logger(name='context_app')
formatter = ContextFormatter(
    '%(asctime)s [%(request_id)s] %(name)s - %(levelname)s - %(message)s'
)
logger.set_formatter(formatter)

# 使用上下文
request_id.set('req_123456')
logger.info("处理请求")  # 日志中会包含 request_id
```

### 异步日志

```python
import asyncio
from qka.utils.logger import Logger

# 异步日志处理
logger = Logger(name='async_app', async_mode=True)

async def async_operation():
    logger.info("开始异步操作")
    await asyncio.sleep(1)
    logger.info("异步操作完成")

# 运行异步代码
asyncio.run(async_operation())
```

### 日志分析和监控

```python
# 日志统计
stats = logger.get_statistics()
print(f"总日志条数: {stats['total_logs']}")
print(f"错误日志数: {stats['error_count']}")
print(f"警告日志数: {stats['warning_count']}")

# 设置日志阈值告警
logger.set_error_threshold(100)  # 错误数超过100时告警
logger.set_warning_threshold(500)  # 警告数超过500时告警

# 日志采样（高频日志场景）
logger.set_sampling_rate(0.1)  # 只记录10%的日志
```

### 多进程日志

```python
import multiprocessing
from qka.utils.logger import Logger

def worker_process(worker_id):
    # 每个进程创建独立的日志实例
    logger = Logger(
        name=f'worker_{worker_id}',
        log_file=f'logs/worker_{worker_id}.log'
    )
    
    for i in range(100):
        logger.info(f"工作进程 {worker_id} 处理任务 {i}")

# 启动多个工作进程
processes = []
for i in range(4):
    p = multiprocessing.Process(target=worker_process, args=(i,))
    processes.append(p)
    p.start()

for p in processes:
    p.join()
```

## 配置示例

### 日志配置文件

```yaml
# logging.yaml
version: 1
disable_existing_loggers: false

formatters:
  standard:
    format: '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    datefmt: '%Y-%m-%d %H:%M:%S'
  
  detailed:
    format: '%(asctime)s [%(levelname)s] %(name)s [%(filename)s:%(lineno)d] %(message)s'
    datefmt: '%Y-%m-%d %H:%M:%S'

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: standard
    stream: ext://sys.stdout
  
  file:
    class: logging.handlers.RotatingFileHandler
    level: DEBUG
    formatter: detailed
    filename: logs/app.log
    maxBytes: 10485760  # 10MB
    backupCount: 5
    encoding: utf8

loggers:
  qka:
    level: DEBUG
    handlers: [console, file]
    propagate: false

root:
  level: WARNING
  handlers: [console]
```

### 加载配置文件

```python
import logging.config
import yaml

# 加载日志配置
with open('logging.yaml', 'r') as f:
    config = yaml.safe_load(f.read())
    logging.config.dictConfig(config)

# 使用配置的日志器
logger = logging.getLogger('qka.strategy')
logger.info("策略启动")
```

## 最佳实践

1. **日志级别使用**
   - DEBUG: 详细的调试信息
   - INFO: 一般信息记录
   - WARNING: 警告但不影响运行
   - ERROR: 错误信息，影响功能
   - CRITICAL: 严重错误，可能导致程序终止

2. **结构化日志**
   - 使用统一的日志格式
   - 包含足够的上下文信息
   - 便于日志分析和查询

3. **性能考虑**
   - 避免在热点路径记录大量日志
   - 使用异步日志处理
   - 合理设置日志级别

4. **安全注意**
   - 不要记录敏感信息
   - 使用日志过滤器清理敏感数据
   - 控制日志文件访问权限
