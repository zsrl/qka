# 工具模块 API 参考

QKA 的工具模块，提供日志系统、颜色输出和各种实用工具函数。

## qka.utils.logger

日志系统模块，提供结构化的日志记录功能。

::: qka.utils.logger
    options:
      show_root_heading: false
      show_source: true
      members_order: source
      heading_level: 3

### 主要功能

#### create_logger 函数
创建增强的日志记录器，支持控制台和文件输出。

#### StructuredLogger 类
结构化日志记录器，支持附加额外字段。

#### WeChatHandler 类
微信消息处理器，支持通过企业微信机器人发送日志。

### 使用示例

```python
from qka.utils.logger import create_logger

# 创建日志记录器
logger = create_logger(
    name='my_strategy',
    level='DEBUG',
    console_output=True,
    file_output=True,
    log_dir='my_logs'
)

# 记录日志
logger.info("策略开始运行")
logger.error("交易失败", symbol='000001.SZ', price=10.5)
```

## qka.utils.util

通用工具函数模块。

::: qka.utils.util
    options:
      show_root_heading: false
      show_source: true
      members_order: source
      heading_level: 3

## qka.utils.anis

ANSI 颜色代码工具，提供带颜色的控制台输出。

::: qka.utils.anis
    options:
      show_root_heading: false
      show_source: true
      members_order: source
      heading_level: 3

### 使用示例

```python
from qka.utils.anis import RED, GREEN, BLUE, RESET

print(f"{RED}错误信息{RESET}")
print(f"{GREEN}成功信息{RESET}")
print(f"{BLUE}提示信息{RESET}")
```

## 模块导入方式

工具模块需要从子模块导入：

```python
# 日志系统
from qka.utils.logger import create_logger, StructuredLogger

# 工具函数
from qka.utils.util import timestamp_to_datetime_string

# 颜色输出
from qka.utils.anis import RED, GREEN, BLUE, RESET
```

## 相关链接

- [核心模块 API](core.md)
- [交易模块 API](brokers.md)
- [用户指南 - 日志系统](../../user-guide/logging.md)