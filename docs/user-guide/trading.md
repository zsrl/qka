# 实盘交易

QKA 提供了完整的实盘交易解决方案，支持多种券商接口和交易模式。

## 交易环境配置

### 券商配置

在配置文件中设置券商信息：

```json
{
  "trading": {
    "broker": "华泰证券",
    "account": "your_account",
    "server_host": "localhost",
    "server_port": 8888,
    "timeout": 30,
    "auto_login": true,
    "credentials": {
      "username": "your_username",
      "password": "your_password",
      "communication_password": "your_comm_password"
    }
  }
}
```

### 安全设置

```python
import os
from qka.core.config import config

# 使用环境变量存储敏感信息
os.environ['QKA_BROKER_USERNAME'] = 'your_username'
os.environ['QKA_BROKER_PASSWORD'] = 'your_password'

# 配置会自动读取环境变量
config.trading.credentials.username = os.getenv('QKA_BROKER_USERNAME')
```

## 交易客户端

### 创建交易客户端

```python
from qka.brokers import QMTClient
from qka.brokers.trade import Order, Trade, Position

# 创建交易客户端
client = QMTClient(base_url="http://localhost:8000", token="your_token")

# 连接到券商
try:
    client.connect()
    print("连接成功")
except Exception as e:
    print(f"连接失败: {e}")
```

### 账户信息查询

```python
# 查询账户资金
account_info = client.get_account_info()
print(f"总资产: {account_info.total_value:,.2f}")
print(f"可用资金: {account_info.available_cash:,.2f}")
print(f"市值: {account_info.market_value:,.2f}")

# 查询持仓
positions = client.get_positions()
for position in positions:
    print(f"{position.symbol}: {position.volume}股, 成本: {position.cost:.2f}")

# 查询委托
orders = client.get_orders()
for order in orders:
    print(f"{order.symbol}: {order.status} {order.volume}股 @ {order.price:.2f}")
```

## 下单交易

### 基本下单

```python
from qka.brokers.trade import OrderType, OrderSide

# 市价买入
buy_order = client.place_order(
    symbol='000001.SZ',
    side=OrderSide.BUY,
    order_type=OrderType.MARKET,
    volume=100
)

print(f"买单ID: {buy_order.order_id}")

# 限价卖出
sell_order = client.place_order(
    symbol='000001.SZ',
    side=OrderSide.SELL,
    order_type=OrderType.LIMIT,
    volume=100,
    price=15.50
)

print(f"卖单ID: {sell_order.order_id}")
```

### 高级订单类型

```python
# 止损单
stop_loss_order = client.place_order(
    symbol='000001.SZ',
    side=OrderSide.SELL,
    order_type=OrderType.STOP_LOSS,
    volume=100,
    stop_price=14.50
)

# 止盈单
take_profit_order = client.place_order(
    symbol='000001.SZ',
    side=OrderSide.SELL,
    order_type=OrderType.TAKE_PROFIT,
    volume=100,
    stop_price=16.50
)

# 条件单
conditional_order = client.place_conditional_order(
    symbol='000001.SZ',
    condition='price >= 16.0',
    action='buy',
    volume=200
)
```

### 批量下单

```python
# 批量下单
orders = [
    {
        'symbol': '000001.SZ',
        'side': OrderSide.BUY,
        'volume': 100,
        'price': 15.00
    },
    {
        'symbol': '000002.SZ',
        'side': OrderSide.BUY,
        'volume': 200,
        'price': 12.50
    }
]

batch_results = client.place_batch_orders(orders)
for result in batch_results:
    if result.success:
        print(f"订单 {result.order_id} 提交成功")
    else:
        print(f"订单提交失败: {result.error}")
```

## 实盘策略运行

### 策略实盘化

```python
from qka.core.backtest import Strategy
from qka.brokers.live import LiveEngine

class LiveTradingStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.name = "实盘交易策略"
        self.client = TradingClient()
    
    def on_init(self):
        """策略初始化"""
        # 连接交易客户端
        self.client.connect()
        
        # 订阅实时数据
        self.subscribe_realtime('000001.SZ')
        
        # 初始化风险控制
        self.setup_risk_management()
    
    def on_data(self, data):
        """实时数据处理"""
        for symbol in data.index:
            # 获取当前持仓
            position = self.client.get_position(symbol)
            current_price = data.loc[symbol, 'last_price']
            
            # 策略逻辑
            signal = self.generate_signal(symbol, data)
            
            if signal == 'BUY' and not position:
                self.execute_buy(symbol, current_price)
            elif signal == 'SELL' and position:
                self.execute_sell(symbol, position.volume, current_price)
    
    def execute_buy(self, symbol, price):
        """执行买入"""
        # 计算仓位大小
        volume = self.calculate_position_size(symbol, price)
        
        # 风险检查
        if self.check_risk_limits(symbol, volume, price):
            order = self.client.place_order(
                symbol=symbol,
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                volume=volume,
                price=price * 1.001  # 稍微高于市价确保成交
            )
            self.log(f"买入订单已提交: {order.order_id}")
        else:
            self.log(f"风险控制: 跳过买入 {symbol}")
    
    def execute_sell(self, symbol, volume, price):
        """执行卖出"""
        order = self.client.place_order(
            symbol=symbol,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            volume=volume,
            price=price * 0.999  # 稍微低于市价确保成交
        )
        self.log(f"卖出订单已提交: {order.order_id}")
```

### 启动实盘引擎

```python
# 创建实盘引擎
live_engine = LiveEngine()

# 配置实盘引擎
live_engine.configure(
    strategy=LiveTradingStrategy(),
    data_frequency='1min',  # 分钟级数据
    order_timeout=30,       # 订单超时时间
    max_retry=3            # 最大重试次数
)

# 启动实盘交易
live_engine.start()

# 策略将在后台运行，处理实时数据和交易
```

## 风险管理

### 实盘风险控制

```python
class RiskManager:
    def __init__(self, client):
        self.client = client
        self.max_position_ratio = 0.1  # 单股最大仓位10%
        self.max_daily_loss = 0.05     # 日最大亏损5%
        self.max_drawdown = 0.15       # 最大回撤15%
    
    def check_position_limit(self, symbol, volume, price):
        """检查仓位限制"""
        account_info = self.client.get_account_info()
        position_value = volume * price
        position_ratio = position_value / account_info.total_value
        
        return position_ratio <= self.max_position_ratio
    
    def check_daily_loss_limit(self):
        """检查日损失限制"""
        today_pnl = self.client.get_today_pnl()
        account_info = self.client.get_account_info()
        loss_ratio = abs(today_pnl) / account_info.total_value
        
        return loss_ratio <= self.max_daily_loss
    
    def emergency_stop(self):
        """紧急止损"""
        # 撤销所有未成交订单
        pending_orders = self.client.get_pending_orders()
        for order in pending_orders:
            self.client.cancel_order(order.order_id)
        
        # 平仓所有持仓
        positions = self.client.get_positions()
        for position in positions:
            self.client.place_order(
                symbol=position.symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                volume=position.volume
            )
        
        self.log("执行紧急止损")
```

### 实时监控

```python
from qka.brokers.monitor import TradingMonitor

monitor = TradingMonitor(client)

# 设置监控规则
monitor.add_rule(
    name='日亏损监控',
    condition=lambda: monitor.get_daily_pnl_ratio() < -0.05,
    action=monitor.send_alert
)

monitor.add_rule(
    name='仓位监控',
    condition=lambda: monitor.get_max_position_ratio() > 0.15,
    action=monitor.reduce_positions
)

# 启动监控
monitor.start()
```

## 数据同步

### 实时行情订阅

```python
from qka.brokers.data import RealtimeDataFeed

# 创建实时数据源
data_feed = RealtimeDataFeed()

# 订阅股票行情
symbols = ['000001.SZ', '000002.SZ', '600000.SH']
data_feed.subscribe(symbols)

# 设置数据回调
def on_tick_data(tick):
    print(f"{tick.symbol}: {tick.last_price} ({tick.timestamp})")

data_feed.set_tick_callback(on_tick_data)

# 启动数据接收
data_feed.start()
```

### 数据存储

```python
from qka.core.data import DataStorage

storage = DataStorage()

# 存储实时数据
def save_tick_data(tick):
    storage.save_tick(
        symbol=tick.symbol,
        timestamp=tick.timestamp,
        price=tick.last_price,
        volume=tick.volume,
        bid=tick.bid,
        ask=tick.ask
    )

data_feed.set_tick_callback(save_tick_data)
```

## 交易记录与分析

### 交易日志

```python
from qka.utils.logger import get_structured_logger

trade_logger = get_structured_logger('trading')

def log_trade(order):
    trade_logger.info('trade_executed', {
        'order_id': order.order_id,
        'symbol': order.symbol,
        'side': order.side,
        'volume': order.volume,
        'price': order.executed_price,
        'timestamp': order.executed_time,
        'commission': order.commission
    })
```

### 实盘表现分析

```python
from qka.core.backtest import LivePerformanceAnalyzer

analyzer = LivePerformanceAnalyzer(client)

# 生成日报
daily_report = analyzer.generate_daily_report()
print(f"今日收益: {daily_report.daily_return:.2%}")
print(f"今日交易次数: {daily_report.trade_count}")

# 生成周报
weekly_report = analyzer.generate_weekly_report()
print(f"本周收益: {weekly_report.weekly_return:.2%}")
print(f"本周胜率: {weekly_report.win_rate:.2%}")
```

## 模拟交易

### 模拟环境

```python
from qka.brokers.simulator import SimulatorClient

# 创建模拟交易客户端
sim_client = SimulatorClient(
    initial_cash=1000000,
    commission_rate=0.0003
)

# 使用模拟客户端进行测试
strategy = LiveTradingStrategy()
strategy.client = sim_client

# 在模拟环境中运行策略
sim_engine = LiveEngine()
sim_engine.configure(
    strategy=strategy,
    client=sim_client,
    mode='simulation'
)

sim_engine.start()
```

## 异常处理

### 连接异常

```python
def handle_connection_error():
    """处理连接异常"""
    max_retry = 3
    retry_count = 0
    
    while retry_count < max_retry:
        try:
            client.reconnect()
            print("重连成功")
            break
        except Exception as e:
            retry_count += 1
            print(f"重连失败 ({retry_count}/{max_retry}): {e}")
            time.sleep(5)
    
    if retry_count >= max_retry:
        print("连接失败，停止交易")
        live_engine.stop()
```

### 订单异常

```python
def handle_order_error(order, error):
    """处理订单异常"""
    if '资金不足' in str(error):
        print("资金不足，调整仓位大小")
        # 重新计算仓位
    elif '涨跌停' in str(error):
        print("股票涨跌停，取消订单")
        # 取消相关订单
    else:
        print(f"订单异常: {error}")
        # 记录错误日志
```

## 最佳实践

1. **充分测试**：在模拟环境中充分测试策略
2. **风险控制**：设置多层风险控制机制
3. **实时监控**：建立完善的监控和告警系统
4. **异常处理**：考虑各种异常情况的处理
5. **数据备份**：定期备份交易数据和日志
6. **版本控制**：对策略代码进行版本管理
7. **渐进上线**：从小资金开始，逐步增加投入

## 注意事项

- **合规要求**：确保符合监管要求
- **系统稳定性**：确保网络和系统稳定
- **数据延迟**：考虑数据传输延迟的影响
- **交易时间**：注意交易时间段的限制
- **资金安全**：妥善保管账户信息

## API 参考

交易模块的详细API参考请查看 [API文档](../api/brokers/index.md)。

### 主要类和函数

- **QMTClient** - 交易客户端接口
- **Order** - 订单对象
- **Trade** - 交易记录  
- **Position** - 持仓信息

更多详细信息请参考对应的API文档页面。
