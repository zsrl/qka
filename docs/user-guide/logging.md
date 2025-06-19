# 日志系统

QKA 提供了强大而灵活的日志系统，支持彩色输出、结构化日志、文件轮转和远程通知等功能。

## 为什么需要好的日志系统？

!!! tip "日志系统的重要性"
    - 🐛 **问题诊断** - 快速定位和解决问题
    - 📊 **性能监控** - 监控系统运行状态
    - 🔍 **行为追踪** - 记录用户操作和系统行为
    - 📈 **数据分析** - 提供业务分析数据
    - ⚠️ **告警通知** - 及时发现系统异常

## 快速开始

### 基础日志记录

```python
from qka.utils.logger import create_logger

# 创建日志记录器
logger = create_logger('my_app')

# 记录不同级别的日志
logger.debug("调试信息：变量值为 x=10")
logger.info("程序正常运行")
logger.warning("这是一个警告")
logger.error("发生错误")
logger.critical("严重错误，程序可能无法继续")
```

### 彩色日志输出

```python
# 启用彩色控制台输出
logger = create_logger('my_app', colored_console=True)

logger.debug("调试信息")    # 青色
logger.info("普通信息")     # 绿色
logger.warning("警告信息")  # 黄色
logger.error("错误信息")    # 红色
logger.critical("严重错误") # 紫色
```

## 日志配置

### 基本配置

```python
from qka.utils.logger import create_logger

logger = create_logger(
    name='my_app',                    # 日志记录器名称
    level='INFO',                     # 日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL
    console_output=True,              # 是否输出到控制台
    file_output=True,                 # 是否输出到文件
    log_dir='logs',                   # 日志文件目录
    max_file_size='10MB',             # 最大文件大小
    backup_count=10,                  # 备份文件数量
    json_format=False,                # 是否使用JSON格式
    colored_console=True              # 控制台是否使用颜色
)
```

### 使用配置文件

```python
import qka
from qka.utils.logger import setup_logging_from_config

# 使用全局配置
logger = create_logger(
    level=qka.config.log.level,
    log_dir=qka.config.log.log_dir,
    max_file_size=qka.config.log.max_file_size,
    backup_count=qka.config.log.backup_count
)
```

## 结构化日志

### 基础结构化日志

```python
from qka.utils.logger import get_structured_logger

# 创建结构化日志记录器
struct_logger = get_structured_logger('my_app')

# 记录带有额外字段的日志
struct_logger.info("用户登录", 
                  user_id=12345, 
                  ip="192.168.1.100", 
                  action="login",
                  success=True)

struct_logger.error("交易失败", 
                   symbol="000001.SZ", 
                   reason="余额不足", 
                   amount=10000,
                   user_id=12345)
```

### 交易日志示例

```python
# 记录订单信息
struct_logger.info("订单创建",
                  order_id="ORD001",
                  symbol="000001.SZ",
                  side="BUY",
                  quantity=1000,
                  price=10.50,
                  strategy="MA_CROSS")

# 记录成交信息
struct_logger.info("订单成交",
                  order_id="ORD001",
                  fill_price=10.48,
                  fill_quantity=1000,
                  commission=3.14,
                  timestamp="2023-12-01T10:30:00")

# 记录策略信号
struct_logger.info("信号生成",
                  strategy="MA_CROSS",
                  symbol="000001.SZ",
                  signal="BUY",
                  strength=0.85,
                  indicators={
                      "ma5": 10.45,
                      "ma20": 10.30,
                      "volume": 1500000
                  })
```

## 文件日志管理

### 自动文件轮转

QKA 支持自动文件轮转，防止日志文件过大：

```python
logger = create_logger(
    'my_app',
    max_file_size='50MB',    # 单个文件最大50MB
    backup_count=20          # 保留20个备份文件
)
```

文件结构示例：
```
logs/
├── 2023-12-01.log       # 当前日志文件
├── 2023-12-01.log.1     # 备份文件1
├── 2023-12-01.log.2     # 备份文件2
└── ...
```

### JSON格式日志

适合后续分析和处理：

```python
logger = create_logger('my_app', json_format=True)

logger.info("这将以JSON格式记录", extra_field="value")
```

JSON输出示例：
```json
{
  "timestamp": "2023-12-01T10:30:00.123456",
  "level": "INFO",
  "logger": "my_app",
  "message": "这将以JSON格式记录",
  "module": "main",
  "function": "main",
  "line": 15,
  "extra_field": "value"
}
```

## 远程通知

### 微信群通知

为重要错误添加微信群通知：

```python
from qka.utils.logger import add_wechat_handler

# 添加微信通知（只通知ERROR级别及以上）
webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
add_wechat_handler(logger, webhook_url, level='ERROR')

# 现在ERROR和CRITICAL级别的日志会发送到微信群
logger.error("这条错误信息会发送到微信群")
logger.critical("这条严重错误也会发送到微信群")
logger.warning("这条警告不会发送到微信群")
```

### 自定义通知处理器

```python
import requests
from qka.utils.logger import logger

class SlackHandler(logging.Handler):
    def __init__(self, webhook_url):
        super().__init__()
        self.webhook_url = webhook_url
    
    def emit(self, record):
        message = self.format(record)
        payload = {"text": message}
        try:
            requests.post(self.webhook_url, json=payload)
        except Exception as e:
            print(f"发送Slack消息失败: {e}")

# 添加Slack通知
slack_handler = SlackHandler("YOUR_SLACK_WEBHOOK_URL")
slack_handler.setLevel(logging.ERROR)
logger.addHandler(slack_handler)
```

## 在策略中使用日志

### 策略日志记录

```python
from qka.core.backtest import Strategy
from qka.utils.logger import create_logger

class LoggedStrategy(Strategy):
    def __init__(self):
        super().__init__()
        # 为策略创建专用日志记录器
        self.logger = create_logger(f'strategy_{self.name}', colored_console=True)
    
    def on_start(self, broker):
        self.logger.info(f"策略启动", 
                        strategy=self.name,
                        initial_cash=broker.initial_cash,
                        commission_rate=broker.commission_rate)
    
    def on_bar(self, data, broker, current_date):
        for symbol, df in data.items():
            if len(df) >= 20:
                current_price = df['close'].iloc[-1]
                ma20 = df['close'].rolling(20).mean().iloc[-1]
                
                if current_price > ma20 and broker.get_position(symbol) == 0:
                    self.logger.info(f"买入信号",
                                   symbol=symbol,
                                   price=current_price,
                                   ma20=ma20,
                                   signal_strength=(current_price - ma20) / ma20)
                    
                    if broker.buy(symbol, 0.3, current_price):
                        self.logger.info(f"买入成功",
                                       symbol=symbol,
                                       price=current_price,
                                       quantity=broker.get_position(symbol),
                                       cash_remaining=broker.get_cash())
                    else:
                        self.logger.warning(f"买入失败",
                                          symbol=symbol,
                                          price=current_price,
                                          reason="资金不足或其他原因")
                
                elif current_price < ma20 and broker.get_position(symbol) > 0:
                    self.logger.info(f"卖出信号",
                                   symbol=symbol,
                                   price=current_price,
                                   ma20=ma20,
                                   position=broker.get_position(symbol))
                    
                    if broker.sell(symbol, 1.0, current_price):
                        self.logger.info(f"卖出成功",
                                       symbol=symbol,
                                       price=current_price,
                                       cash_after=broker.get_cash())
    
    def on_end(self, broker):
        final_value = broker.get_total_value({})
        self.logger.info(f"策略结束",
                        strategy=self.name,
                        final_value=final_value,
                        return_rate=(final_value - broker.initial_cash) / broker.initial_cash,
                        total_trades=len(broker.trades))
```

### 交易日志分析

```python
import json
from datetime import datetime

def analyze_trading_logs(log_file):
    """分析交易日志文件"""
    trades = []
    
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            if '买入成功' in line or '卖出成功' in line:
                # 解析日志行（如果是JSON格式）
                try:
                    log_data = json.loads(line)
                    trades.append(log_data)
                except:
                    # 普通格式的解析
                    pass
    
    # 分析交易数据
    print(f"总交易次数: {len(trades)}")
    return trades

# 使用示例
trades = analyze_trading_logs('logs/strategy_MA_CROSS.log')
```

## 性能监控日志

### 函数执行时间记录

```python
from qka.utils.tools import timer
from qka.utils.logger import create_logger

logger = create_logger('performance')

@timer
def slow_function():
    """这个装饰器会自动记录执行时间"""
    import time
    time.sleep(1)
    return "完成"

# 手动记录性能
import time

def manual_timing_example():
    start_time = time.time()
    
    # 执行一些操作
    result = complex_calculation()
    
    end_time = time.time()
    logger.info("计算完成",
               function="complex_calculation",
               execution_time=end_time - start_time,
               result_size=len(result))
```

### 内存使用监控

```python
import psutil
import os

def log_memory_usage():
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    
    logger.info("内存使用情况",
               rss_mb=memory_info.rss / 1024 / 1024,  # 物理内存
               vms_mb=memory_info.vms / 1024 / 1024,  # 虚拟内存
               cpu_percent=process.cpu_percent())

# 定期记录内存使用
import threading
import time

def memory_monitor():
    while True:
        log_memory_usage()
        time.sleep(60)  # 每分钟记录一次

# 启动内存监控线程
monitor_thread = threading.Thread(target=memory_monitor, daemon=True)
monitor_thread.start()
```

## 日志最佳实践

### 1. 日志级别使用

```python
# DEBUG - 详细的诊断信息，仅在诊断问题时使用
logger.debug(f"计算中间结果: ma5={ma5}, ma20={ma20}")

# INFO - 一般信息，记录程序正常运行状态
logger.info("策略开始运行", strategy="MA_CROSS")

# WARNING - 警告信息，程序可以继续运行但需要注意
logger.warning("数据缺失", symbol="000001.SZ", missing_days=3)

# ERROR - 错误信息，功能无法正常执行但程序可以继续
logger.error("订单下单失败", symbol="000001.SZ", reason="余额不足")

# CRITICAL - 严重错误，程序可能无法继续运行
logger.critical("数据库连接失败", error="连接超时")
```

### 2. 敏感信息处理

```python
# ❌ 不要记录敏感信息
logger.info("用户登录", password="123456", api_key="secret_key")

# ✅ 正确的做法
logger.info("用户登录", 
           user_id="12345",
           ip="192.168.1.100",
           # 密码和API密钥不记录
           login_method="password")
```

### 3. 结构化信息

```python
# ❌ 字符串拼接，难以解析
logger.info(f"用户{user_id}在{timestamp}买入{symbol}数量{quantity}")

# ✅ 结构化记录，便于后续分析
logger.info("用户下单",
           user_id=user_id,
           timestamp=timestamp,
           action="BUY",
           symbol=symbol,
           quantity=quantity)
```

### 4. 异常记录

```python
try:
    result = risky_operation()
except Exception as e:
    # 记录完整的异常信息
    logger.error("操作失败",
                operation="risky_operation",
                error_type=type(e).__name__,
                error_message=str(e),
                exc_info=True)  # 包含完整的堆栈跟踪
```

## 日志分析工具

### 实时日志监控

```python
import subprocess
import re

def tail_logs(log_file, pattern=None):
    """实时监控日志文件"""
    process = subprocess.Popen(['tail', '-f', log_file], 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE,
                              universal_newlines=True)
    
    try:
        for line in iter(process.stdout.readline, ''):
            if pattern is None or re.search(pattern, line):
                print(line.strip())
    except KeyboardInterrupt:
        process.terminate()

# 使用示例
# tail_logs('logs/2023-12-01.log', 'ERROR')  # 只显示错误日志
```

### 日志统计

```python
import re
from collections import defaultdict

def analyze_log_file(log_file):
    """分析日志文件统计信息"""
    level_counts = defaultdict(int)
    error_types = defaultdict(int)
    
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            # 统计日志级别
            if match := re.search(r'\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\]', line):
                level_counts[match.group(1)] += 1
            
            # 统计错误类型
            if 'ERROR' in line and '失败' in line:
                if '下单失败' in line:
                    error_types['下单失败'] += 1
                elif '数据获取失败' in line:
                    error_types['数据获取失败'] += 1
    
    print("日志级别统计:")
    for level, count in level_counts.items():
        print(f"  {level}: {count}")
    
    print("\n错误类型统计:")
    for error_type, count in error_types.items():
        print(f"  {error_type}: {count}")

# 使用示例
analyze_log_file('logs/2023-12-01.log')
```

## API 参考

日志系统的详细API参考请查看 [Logger API文档](../api/utils/logger.md)。

### 主要类和函数

- **Logger** - 增强日志记录器
- **ColorFormatter** - 彩色日志格式化器
- **StructuredLogger** - 结构化日志记录器

更多详细信息和使用示例请参考API文档页面。
