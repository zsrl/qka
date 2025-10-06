# 交易模块 API 参考

QKA 的交易接口模块，提供 QMT 交易服务器的客户端和服务器端实现。

## qka.brokers.QMTClient

QMT 交易客户端类，提供与 QMT 交易服务器的通信接口。

::: qka.brokers.client.QMTClient
    options:
      show_root_heading: false
      show_source: true
      members_order: source
      heading_level: 3

### 使用示例

```python
from qka.brokers.client import QMTClient

# 创建交易客户端
client = QMTClient(
    base_url="http://localhost:8000",
    token="服务器打印的token"
)

# 调用交易接口
assets = client.api("query_stock_asset")
print(assets)
```

## qka.brokers.QMTServer

QMT 交易服务器类，将 QMT 交易接口封装为 RESTful API。

::: qka.brokers.server.QMTServer
    options:
      show_root_heading: false
      show_source: true
      members_order: source
      heading_level: 3

### 使用示例

```python
from qka.brokers.server import QMTServer

# 创建交易服务器
server = QMTServer(
    account_id="YOUR_ACCOUNT_ID",
    mini_qmt_path="YOUR_QMT_PATH"
)

# 启动服务器
server.start()
```

## qka.brokers.trade

交易执行相关类和函数，包含订单、交易和持仓管理。

::: qka.brokers.trade
    options:
      show_root_heading: false
      show_source: true
      members_order: source
      heading_level: 3

### 主要组件

#### Order 类
订单对象，表示一个交易订单。

#### Trade 类  
交易记录，表示一个已成交的交易。

#### Position 类
持仓信息，表示一个持仓头寸。

#### create_trader 函数
创建 QMT 交易对象的便捷函数。

### 使用示例

```python
from qka.brokers.trade import create_trader, Order

# 创建交易对象
trader, account = create_trader(account_id, mini_qmt_path)

# 创建订单
order = Order(
    symbol='000001.SZ',
    side='buy',
    quantity=1000,
    order_type='market'
)
```

## 模块导入方式

交易模块需要从子模块导入：

```python
# 客户端
from qka.brokers.client import QMTClient

# 服务器
from qka.brokers.server import QMTServer

# 交易执行
from qka.brokers.trade import create_trader, Order, Trade, Position
```

## 工作流程

### 1. 启动交易服务器

```python
from qka.brokers.server import QMTServer

server = QMTServer(
    account_id="123456789",
    mini_qmt_path="D:/qmt"
)
server.start()  # 会打印token供客户端使用
```

### 2. 使用交易客户端

```python
from qka.brokers.client import QMTClient

client = QMTClient(
    base_url="http://localhost:8000",
    token="服务器打印的token"
)

# 查询账户信息
assets = client.api("query_stock_asset")

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

## 注意事项

1. **QMT 依赖**: 需要安装 QMT 并正确配置环境
2. **网络连接**: 确保服务器和客户端网络连通
3. **权限验证**: 使用 token 进行身份验证
4. **错误处理**: 妥善处理网络错误和交易失败

## 相关链接

- [用户指南 - 实盘交易](../../user-guide/trading.md)
- [核心模块 API](core.md)
- [工具模块 API](utils.md)
- [xtquant 文档](https://github.com/ShiMiaoYS/xtquant)