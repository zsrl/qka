# 示例和教程

QKA量化回测系统的实用示例和完整教程。

## 快速入门示例

### [基础示例](basic/index.md)
- [第一个策略](basic/first-strategy.md) - 创建你的第一个交易策略
- [数据获取](basic/data-fetching.md) - 学习如何获取和处理市场数据
- [简单回测](basic/simple-backtest.md) - 运行基本的策略回测

### [进阶示例](advanced/index.md)
- [事件驱动策略](advanced/event-driven.md) - 使用事件系统的高级策略
- [多资产策略](advanced/multi-asset.md) - 跨资产类别的投资策略
- [风险管理](advanced/risk-management.md) - 集成风险控制的策略

### [完整案例](complete/index.md)
- [动量策略](complete/momentum-strategy.md) - 完整的动量交易策略
- [均值回归策略](complete/mean-reversion.md) - 均值回归策略实现
- [配对交易](complete/pairs-trading.md) - 统计套利策略

## 实际应用

### [实盘交易](live-trading/index.md)
- [环境配置](live-trading/setup.md) - 实盘交易环境搭建
- [风险控制](live-trading/risk-control.md) - 实盘风险管理
- [监控告警](live-trading/monitoring.md) - 交易监控和告警

### [性能优化](optimization/index.md)
- [策略优化](optimization/strategy-optimization.md) - 策略参数优化
- [性能调优](optimization/performance-tuning.md) - 系统性能优化
- [并行计算](optimization/parallel-computing.md) - 使用并行计算加速回测

### [集成案例](integration/index.md)
- [数据源集成](integration/data-sources.md) - 集成多种数据源
- [交易接口](integration/broker-apis.md) - 连接不同的交易平台
- [外部工具](integration/external-tools.md) - 与其他工具的集成

## 代码片段

### 常用模式

```python
# 策略模板
from qka.core import Strategy, EventBus
from qka.utils import Logger

class MyStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.logger = Logger()
        
    def on_market_data(self, event):
        # 处理市场数据
        pass
        
    def on_signal(self, signal):
        # 处理交易信号
        pass
```

### 工具使用

```python
# 配置管理
from qka.core import Config

config = Config()
config.load_from_file('config.yaml')

# 日志记录
from qka.utils import Logger

logger = Logger()
logger.info("策略启动")

# 缓存装饰器
from qka.utils.tools import cache

@cache(ttl=300)
def expensive_calculation():
    return result
```

## 学习路径

### 初学者路径
1. [安装和配置](../getting-started/installation.md)
2. [基础概念](../getting-started/concepts.md)
3. [第一个策略](../getting-started/first-strategy.md)
4. [基础示例](basic/index.md)

### 进阶路径
1. [进阶示例](advanced/index.md)
2. [系统架构](../user-guide/architecture.md)
3. [性能优化](optimization/index.md)
4. [完整案例](complete/index.md)

### 专家路径
1. [源码分析](../development/source-analysis.md)
2. [扩展开发](../development/extensions.md)
3. [集成案例](integration/index.md)
4. [贡献指南](../development/contributing.md)

## 常见问题

### 策略开发
- **Q: 如何处理数据缺失？**
  A: 使用数据验证和填充机制，参考[数据处理示例](basic/data-processing.md)

- **Q: 如何优化策略性能？**
  A: 查看[性能优化指南](optimization/performance-tuning.md)

### 回测分析
- **Q: 如何设置回测参数？**
  A: 参考[回测配置示例](basic/backtest-config.md)

- **Q: 如何分析回测结果？**
  A: 查看[结果分析教程](basic/result-analysis.md)

### 实盘交易
- **Q: 如何配置交易接口？**
  A: 参考[交易接口配置](live-trading/broker-setup.md)

- **Q: 如何监控策略运行？**
  A: 查看[监控配置指南](live-trading/monitoring.md)

## 贡献示例

我们欢迎社区贡献更多示例：

1. Fork 项目仓库
2. 在 `examples/` 目录下添加示例
3. 在 `docs/examples/` 下添加对应文档
4. 提交 Pull Request

### 示例规范
- 代码要有详细注释
- 包含完整的运行说明
- 提供示例数据
- 说明预期结果

更多信息请查看[贡献指南](../development/contributing.md)。
