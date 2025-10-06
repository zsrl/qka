# QKA - 快量化

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/qka)](https://pypi.org/project/qka/)

**快捷量化助手（Quick Quantitative Assistant）** 是一个简洁易用、功能完整的A股量化交易框架，支持数据获取、策略回测、实盘交易等全流程量化交易功能。

## 特性

- 🚀 **简洁易用**: 统一的API设计，降低量化交易门槛
- 📊 **数据丰富**: 支持Akshare数据源，提供多周期、多因子数据
- 🔄 **高效回测**: 基于时间序列的回测引擎，支持多股票横截面处理
- 💰 **实盘交易**: 集成QMT交易接口，支持实盘交易
- 📈 **可视化**: 内置Plotly图表，提供交互式回测结果展示
- 🔧 **模块化**: 高度模块化设计，易于扩展和维护
- 📝 **文档完整**: 提供详细的API文档和使用示例

## 安装

### 从PyPI安装

```bash
pip install qka
```

### 从源码安装

```bash
git clone https://github.com/zsrl/qka.git
cd qka
pip install -e .
```

## 快速开始

### 1. 数据获取

```python
import qka

# 创建数据对象
data = qka.Data(
    symbols=['000001.SZ', '600000.SH'],  # 股票代码列表
    period='1d',                         # 日线数据
    adjust='qfq'                         # 前复权
)

# 获取数据
df = data.get()
print(df.head())
```

### 2. 策略开发

```python
import qka

class MyStrategy(qka.Strategy):
    def __init__(self):
        super().__init__()
        self.cash = 100000  # 初始资金
    
    def on_bar(self, date, get):
        """每个bar的处理逻辑"""
        # 获取当前价格数据
        close_prices = get('close')
        
        # 示例策略：当000001.SZ价格低于10元时买入
        if '000001.SZ' in close_prices and close_prices['000001.SZ'] < 10:
            # 买入1000股
            self.broker.buy('000001.SZ', close_prices['000001.SZ'], 1000)
```

### 3. 回测分析

```python
import qka

# 创建策略实例
strategy = MyStrategy()

# 创建回测引擎
backtest = qka.Backtest(data, strategy)

# 运行回测
backtest.run()

# 绘制收益曲线
backtest.plot("我的策略回测结果")
```

### 4. QMT实盘交易

#### 启动交易服务器

```python
from qka.brokers.server import QMTServer

# 创建交易服务器
server = QMTServer(
    account_id="YOUR_ACCOUNT_ID",      # 你的账户ID
    mini_qmt_path="YOUR_QMT_PATH"      # QMT安装路径
)

# 启动服务器（会打印token供客户端使用）
server.start()
```

#### 使用交易客户端

```python
from qka.brokers.client import QMTClient

# 创建交易客户端
client = QMTClient(
    base_url="http://localhost:8000",  # 服务器地址
    token="服务器打印的token"           # 访问令牌
)

# 查询账户资产
assets = client.api("query_stock_asset")
print(assets)

# 下单交易
from xtquant import xtconstant
result = client.api(
    "order_stock",
    stock_code='600000.SH',
    order_type=xtconstant.STOCK_BUY,
    order_volume=1000,
    price_type=xtconstant.FIX_PRICE,
    price=10.5
)
```

## 核心模块

### 数据模块 (qka.Data)

- **多数据源**: 支持Akshare、QMT等数据源
- **缓存机制**: 自动缓存数据，提高访问效率
- **并发下载**: 多线程并发下载，提升数据获取速度
- **数据标准化**: 统一数据格式，便于策略开发

### 回测模块 (qka.Backtest)

- **时间序列**: 基于时间序列的回测引擎
- **多资产支持**: 支持多股票横截面数据处理
- **交易记录**: 完整的交易记录和持仓跟踪
- **可视化**: 交互式回测结果图表

### 策略模块 (qka.Strategy)

- **抽象基类**: 提供策略开发的标准接口
- **事件驱动**: 基于bar的事件处理机制
- **交易接口**: 内置买入卖出操作接口
- **状态管理**: 自动管理资金和持仓状态

### 经纪商模块 (qka.brokers)

- **QMT集成**: 完整的QMT交易接口封装
- **客户端/服务器**: 支持远程交易服务
- **订单管理**: 完整的订单生命周期管理
- **错误处理**: 完善的错误处理和日志记录

### MCP模块 (qka.mcp)

- **模型服务**: 提供模型上下文协议支持
- **数据查询**: 支持Akshare数据查询工具
- **异步处理**: 基于异步IO的高性能处理

### 工具模块 (qka.utils)

- **日志系统**: 结构化日志记录，支持文件和控制台输出
- **颜色输出**: 带颜色的控制台输出
- **工具函数**: 各种实用工具函数

## 高级用法

### 自定义因子计算

```python
import pandas as pd

def calculate_ma_factor(df):
    """计算移动平均因子"""
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    return df

data = qka.Data(
    symbols=['000001.SZ'],
    factor=calculate_ma_factor  # 应用自定义因子
)
```

### 批量数据处理

```python
# 批量处理多只股票
symbols = ['000001.SZ', '600000.SH', '000002.SZ', '600036.SH']
data = qka.Data(
    symbols=symbols,
    pool_size=20  # 增加并发数提高下载速度
)
```

### 事件驱动策略

```python
class EventDrivenStrategy(qka.Strategy):
    def on_bar(self, date, get):
        close_prices = get('close')
        volumes = get('volume')
        
        # 基于成交量的事件
        for symbol in close_prices.index:
            if volumes[symbol] > volumes.mean() * 2:  # 成交量放大
                self.broker.buy(symbol, close_prices[symbol], 100)
```

## 配置说明

### 数据缓存配置

```python
from pathlib import Path

data = qka.Data(
    symbols=['000001.SZ'],
    datadir=Path("/path/to/cache")  # 自定义缓存目录
)
```

## 常见问题

### Q: 如何获取股票代码？
A: 可以使用Akshare获取股票列表：
```python
import akshare as ak
stock_list = ak.stock_info_a_code_name()
```

### Q: 回测时如何设置手续费？
A: 目前版本默认无手续费，可以在策略中手动计算或扩展Broker类。

### Q: 支持哪些数据周期？
A: 目前主要支持日线数据，可根据需要扩展分钟线、周线等。

### Q: 如何添加新的数据源？
A: 继承Data类并实现相应的数据获取方法。

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 联系方式

- 项目主页: [https://github.com/zsrl/qka](https://github.com/zsrl/qka)
- 问题反馈: [GitHub Issues](https://github.com/zsrl/qka/issues)

## 致谢

感谢以下开源项目的支持：

- [Akshare](https://github.com/akfamily/akshare) - 丰富的数据源
- [Plotly](https://plotly.com/python/) - 交互式图表
- [FastAPI](https://fastapi.tiangolo.com/) - 高性能API框架
- [xtquant](https://github.com/ShiMiaoYS/xtquant) - QMT Python接口

---

**注意**: 量化交易存在风险，请在充分了解风险的情况下使用本框架。作者不对使用本框架产生的任何投资损失负责。
