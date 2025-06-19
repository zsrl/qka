# API 参考

QKA量化回测系统的完整API参考文档。

## 模块概览

### 核心模块

- [**Core**](core/index.md) - 核心功能模块
  - [配置管理](core/config.md) - 系统配置管理
  - [事件系统](core/events.md) - 事件驱动框架
  - [回测引擎](core/backtest.md) - 回测核心逻辑
  - [数据处理](core/data.md) - 数据获取和处理
  - [绘图工具](core/plot.md) - 结果可视化

### 工具模块

- [**Utils**](utils/index.md) - 工具类模块
  - [日志系统](utils/logger.md) - 增强日志功能
  - [通用工具](utils/tools.md) - 常用工具类
  - [动画工具](utils/anis.md) - 动画显示工具
  - [通用函数](utils/util.md) - 通用辅助函数

### 交易模块

- [**Brokers**](brokers/index.md) - 交易接口模块
  - [交易客户端](brokers/client.md) - 交易客户端接口
  - [交易服务器](brokers/server.md) - 交易服务器实现
  - [交易执行](brokers/trade.md) - 交易执行逻辑

### MCP模块

- [**MCP**](mcp/index.md) - Model Context Protocol模块
  - [API接口](mcp/api.md) - MCP API定义
  - [服务器实现](mcp/server.md) - MCP服务器

## 快速导航

- [配置系统 API](core/config.md) - 管理系统配置
- [事件系统 API](core/events.md) - 事件驱动编程
- [日志系统 API](utils/logger.md) - 结构化日志记录
- [工具类 API](utils/tools.md) - 通用工具函数

## 使用示例

```python
from qka.core import Config, EventBus
from qka.utils import Logger, cache, timeit

# 配置管理
config = Config()
config.load_from_file('config.yaml')

# 事件系统
bus = EventBus()
bus.subscribe('market_data', handler)

# 日志记录
logger = Logger()
logger.info("系统启动")

# 工具使用
@cache(ttl=300)
@timeit
def expensive_function():
    pass
```

## 版本信息

当前文档对应QKA系统版本：`1.0.0`

API文档会随代码更新自动同步，确保文档的准确性和时效性。
