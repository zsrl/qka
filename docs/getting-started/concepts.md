# 基础概念

了解 QKA 的核心概念和架构设计，帮助你更好地使用这个量化交易框架。

## 核心架构

QKA 采用模块化设计，主要包含以下几个核心模块：

```
qka/
├── core/           # 核心功能模块
│   ├── data.py     # 数据管理
│   ├── backtest.py # 回测引擎
│   ├── strategy.py # 策略基类
│   └── broker.py   # 虚拟经纪商
├── brokers/        # 交易接口
│   ├── client.py   # 交易客户端
│   ├── server.py   # 交易服务器
│   └── trade.py    # 交易执行
├── mcp/           # MCP 协议支持
│   ├── api.py     # MCP API
│   └── server.py  # MCP 服务器
└── utils/         # 工具模块
    ├── logger.py  # 日志系统
    └── util.py    # 通用工具
```

## 数据流

QKA 的数据处理流程如下：

1. **数据获取**: 通过 `qka.Data` 类从数据源获取股票数据
2. **策略处理**: 在 `on_bar` 方法中处理每个时间点的数据
3. **交易执行**: 通过 `broker` 执行买卖操作
4. **状态记录**: 自动记录资金、持仓和交易历史
5. **结果分析**: 通过回测结果进行策略评估

## 核心概念详解

### 1. 数据维度

QKA 的数据模型基于四个维度：

- **标的维度**: 股票代码列表，如 `['000001.SZ', '600000.SH']`
- **周期维度**: 数据频率，如 `'1d'`（日线）、`'1m'`（分钟线）
- **因子维度**: 技术指标和特征，如移动平均、RSI 等
- **数据源维度**: 数据来源，如 `'akshare'`、`'qmt'`

### 2. 策略开发

所有策略都必须继承 `qka.Strategy` 基类：

```python
class MyStrategy(qka.Strategy):
    def __init__(self):
        super().__init__()
        # 初始化策略参数
        
    def on_bar(self, date, get):
        """
        date: 当前时间戳
        get: 获取因子数据的函数，格式为 get(factor_name) -> pd.Series
        """
        # 策略逻辑
        pass
```

### 3. 回测引擎

回测引擎负责：

- 按时间顺序遍历数据
- 在每个时间点调用策略的 `on_bar` 方法
- 记录交易状态和资金变化
- 提供可视化分析

### 4. 经纪商接口

`qka.Broker` 类提供虚拟交易功能：

- 资金管理
- 持仓跟踪
- 交易执行
- 交易记录

## 关键特性

### 并发数据下载

QKA 使用多线程并发下载数据，显著提高数据获取效率：

```python
data = qka.Data(
    symbols=['000001.SZ', '600000.SH', ...],  # 多只股票
    pool_size=10  # 并发线程数
)
```

### 数据缓存

自动缓存下载的数据到本地，避免重复下载：

```python
# 数据会自动缓存到 datadir/ 目录
# 下次使用时直接从缓存读取
```

### 统一数据格式

无论数据来源如何，都统一为标准的 DataFrame 格式：

```python
# 列名格式: {symbol}_{column}
# 例如: 000001.SZ_close, 600000.SH_volume
```

## 设计原则

### 1. 简洁性

提供简单直观的 API，降低量化交易的学习门槛：

```python
# 三行代码完成基本回测
data = qka.Data(symbols=['000001.SZ'])
strategy = MyStrategy()
backtest = qka.Backtest(data, strategy)
backtest.run()
```

### 2. 扩展性

模块化设计，易于扩展新功能：

- 可以轻松添加新的数据源
- 支持自定义因子计算
- 可以扩展新的交易接口

### 3. 实用性

专注于 A 股市场的实际需求：

- 支持 A 股特有的交易规则
- 集成常用的 A 股数据源
- 提供实盘交易接口

## 使用模式

### 回测模式

用于策略开发和验证：

```python
# 1. 准备数据
data = qka.Data(symbols=stock_list)

# 2. 开发策略
class MyStrategy(qka.Strategy):
    def on_bar(self, date, get):
        # 策略逻辑
        pass

# 3. 运行回测
backtest = qka.Backtest(data, MyStrategy())
backtest.run()

# 4. 分析结果
backtest.plot()
```

### 实盘模式

用于实盘交易：

```python
# 1. 启动交易服务器
from qka.brokers.server import QMTServer
server = QMTServer(account_id, qmt_path)
server.start()

# 2. 使用交易客户端
from qka.brokers.client import QMTClient
client = QMTClient(token=token)
client.api("order_stock", ...)
```

## 最佳实践

1. **数据预处理**: 在策略开发前确保数据质量
2. **参数优化**: 使用网格搜索等方法优化策略参数
3. **风险控制**: 在策略中加入止损和仓位控制
4. **回测验证**: 使用不同时间段的数据验证策略稳定性
5. **实盘测试**: 从小资金开始实盘测试

## 下一步

- 查看 [用户指南](../user-guide/data.md) 学习详细功能用法
- 参考 [API 文档](../api/core/data.md) 了解完整接口说明
- 学习 [示例教程](../examples/basic/first-strategy.md) 获取实用代码示例