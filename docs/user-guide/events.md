# 事件系统

QKA 采用事件驱动架构，通过发布-订阅模式实现模块间的松耦合通信。事件系统让您可以监听和响应系统中发生的各种事件。

## 为什么使用事件系统？

!!! tip "事件系统的优势"
    - 🔗 **松耦合** - 模块间无需直接依赖
    - 📡 **实时响应** - 立即响应系统事件
    - 🔧 **易扩展** - 轻松添加新的事件处理逻辑
    - 📊 **可监控** - 完整的事件历史和统计

## 快速开始

### 启动事件系统

```python
from qka.core.events import start_event_engine, stop_event_engine

# 启动事件引擎
start_event_engine()

# 程序结束时停止
stop_event_engine()
```

### 监听事件

使用装饰器方式监听事件：

```python
from qka.core.events import EventType, event_handler

@event_handler(EventType.DATA_LOADED)
def on_data_loaded(event):
    print(f"数据加载完成: {event.data}")

@event_handler(EventType.ORDER_FILLED)
def on_order_filled(event):
    print(f"订单成交: {event.data}")
```

### 发送事件

```python
from qka.core.events import emit_event

# 发送数据加载事件
emit_event(EventType.DATA_LOADED, {
    "symbol": "000001.SZ",
    "rows": 1000,
    "timespan": "2023-01-01 to 2023-12-31"
})

# 发送订单成交事件
emit_event(EventType.ORDER_FILLED, {
    "order_id": "12345",
    "symbol": "000001.SZ",
    "price": 10.50,
    "quantity": 1000
})
```

## 事件类型详解

### 数据相关事件

#### DATA_LOADED - 数据加载完成
当数据成功加载时触发。

```python
@event_handler(EventType.DATA_LOADED)
def on_data_loaded(event):
    data = event.data
    print(f"加载了 {data['symbol']} 的 {data['rows']} 条数据")
```

**事件数据示例**:
```python
{
    "symbol": "000001.SZ",
    "rows": 1000,
    "timespan": "2023-01-01 to 2023-12-31",
    "source": "akshare"
}
```

#### DATA_ERROR - 数据加载错误
当数据加载失败时触发。

```python
@event_handler(EventType.DATA_ERROR)
def on_data_error(event):
    error = event.data
    print(f"数据加载失败: {error['message']}")
```

### 交易相关事件

#### ORDER_CREATED - 订单创建
当新订单被创建时触发。

```python
@event_handler(EventType.ORDER_CREATED)
def on_order_created(event):
    order = event.data
    print(f"创建订单: {order['action']} {order['symbol']} @ {order['price']}")
```

#### ORDER_FILLED - 订单成交
当订单成交时触发。

```python
@event_handler(EventType.ORDER_FILLED)
def on_order_filled(event):
    trade = event.data
    print(f"订单成交: {trade['symbol']} 成交价 {trade['price']}")
```

#### ORDER_CANCELLED - 订单取消
当订单被取消时触发。

```python
@event_handler(EventType.ORDER_CANCELLED)
def on_order_cancelled(event):
    order = event.data
    print(f"订单取消: {order['order_id']}")
```

### 策略相关事件

#### STRATEGY_START - 策略开始
当策略开始运行时触发。

```python
@event_handler(EventType.STRATEGY_START)
def on_strategy_start(event):
    strategy = event.data
    print(f"策略 {strategy['name']} 开始运行")
```

#### SIGNAL_GENERATED - 信号生成
当策略生成交易信号时触发。

```python
@event_handler(EventType.SIGNAL_GENERATED)
def on_signal_generated(event):
    signal = event.data
    print(f"信号: {signal['action']} {signal['symbol']}")
    
    # 可以在这里添加信号过滤、风险检查等逻辑
    if signal['strength'] > 0.8:
        print("强信号，建议关注！")
```

## 高级用法

### 自定义事件处理器

创建自定义的事件处理器类：

```python
from qka.core.events import EventHandler, Event

class TradingEventHandler(EventHandler):
    def __init__(self):
        self.order_count = 0
        self.total_volume = 0
    
    def handle(self, event: Event):
        if event.event_type == EventType.ORDER_FILLED:
            self.order_count += 1
            self.total_volume += event.data.get('quantity', 0)
            print(f"总订单数: {self.order_count}, 总成交量: {self.total_volume}")
    
    def can_handle(self, event: Event) -> bool:
        return event.event_type == EventType.ORDER_FILLED

# 注册处理器
from qka.core.events import event_engine

handler = TradingEventHandler()
event_engine.subscribe(EventType.ORDER_FILLED, handler)
```

### 事件过滤

只处理特定条件的事件：

```python
@event_handler(EventType.SIGNAL_GENERATED)
def handle_strong_signals(event):
    signal = event.data
    
    # 只处理强信号
    if signal.get('strength', 0) > 0.8:
        print(f"收到强信号: {signal}")
        # 执行相应操作
```

### 异步事件处理

```python
from qka.core.events import AsyncEventHandler
import asyncio

class AsyncOrderHandler(AsyncEventHandler):
    async def handle_async(self, event: Event):
        if event.event_type == EventType.ORDER_FILLED:
            # 异步处理订单
            await self.update_portfolio(event.data)
            await self.send_notification(event.data)
    
    async def update_portfolio(self, order_data):
        # 模拟异步数据库操作
        await asyncio.sleep(0.1)
        print(f"组合更新完成: {order_data}")
    
    async def send_notification(self, order_data):
        # 模拟异步通知发送
        await asyncio.sleep(0.1)
        print(f"通知已发送: {order_data}")
```

## 事件统计和监控

### 查看事件统计

```python
from qka.core.events import event_engine

# 获取统计信息
stats = event_engine.get_statistics()

print(f"事件计数: {stats['event_count']}")
print(f"错误计数: {stats['error_count']}")
print(f"队列大小: {stats['queue_size']}")
print(f"处理器数量: {stats['handler_count']}")
print(f"运行状态: {stats['is_running']}")
```

### 查看事件历史

```python
# 获取所有事件历史
all_events = event_engine.get_event_history(limit=100)

# 获取特定类型的事件历史
order_events = event_engine.get_event_history(
    event_type=EventType.ORDER_FILLED, 
    limit=50
)

for event in order_events:
    print(f"{event.timestamp}: {event.data}")
```

## 在策略中使用事件

### 事件驱动的策略

```python
from qka.core.backtest import Strategy
from qka.core.events import EventType, emit_event

class EventDrivenStrategy(Strategy):
    def on_start(self, broker):
        # 策略开始时发送事件
        emit_event(EventType.STRATEGY_START, {
            "strategy": self.name,
            "initial_cash": broker.initial_cash
        })
    
    def on_bar(self, data, broker, current_date):
        for symbol, df in data.items():
            if len(df) >= 20:
                current_price = df['close'].iloc[-1]
                ma20 = df['close'].rolling(20).mean().iloc[-1]
                
                # 生成信号事件
                if current_price > ma20:
                    emit_event(EventType.SIGNAL_GENERATED, {
                        "symbol": symbol,
                        "action": "BUY",
                        "price": current_price,
                        "strength": 0.8,
                        "reason": "价格突破20日均线"
                    })
                    
                    # 执行买入
                    if broker.buy(symbol, 0.3, current_price):
                        emit_event(EventType.ORDER_FILLED, {
                            "symbol": symbol,
                            "action": "BUY",
                            "price": current_price,
                            "quantity": broker.get_position(symbol)
                        })
```

### 事件监听器

```python
# 策略性能监控
@event_handler(EventType.ORDER_FILLED)
def monitor_strategy_performance(event):
    order = event.data
    
    # 记录交易日志
    with open('trades.log', 'a') as f:
        f.write(f"{event.timestamp}: {order}\n")
    
    # 计算收益
    if order['action'] == 'SELL':
        # 计算这笔交易的盈亏
        pass

# 风险监控
@event_handler(EventType.SIGNAL_GENERATED)
def risk_monitor(event):
    signal = event.data
    
    # 检查是否有过度交易
    if signal['strength'] < 0.5:
        print(f"⚠️ 弱信号警告: {signal}")
    
    # 检查仓位集中度
    # ...
```

## 最佳实践

### 1. 事件命名

为自定义事件使用清晰的命名：

```python
# 好的命名
EventType.PORTFOLIO_REBALANCED
EventType.RISK_LIMIT_EXCEEDED
EventType.MARKET_DATA_UPDATED

# 避免的命名
EventType.EVENT1
EventType.SOMETHING_HAPPENED
```

### 2. 事件数据结构

保持事件数据结构的一致性：

```python
# 推荐的事件数据结构
{
    "timestamp": "2023-12-01T10:30:00",
    "symbol": "000001.SZ",
    "action": "BUY",
    "price": 10.50,
    "quantity": 1000,
    "metadata": {
        "strategy": "MA_CROSS",
        "signal_strength": 0.85
    }
}
```

### 3. 错误处理

在事件处理器中添加适当的错误处理：

```python
@event_handler(EventType.ORDER_FILLED)
def safe_order_handler(event):
    try:
        # 处理订单逻辑
        process_order(event.data)
    except Exception as e:
        print(f"处理订单事件时出错: {e}")
        # 发送错误事件
        emit_event(EventType.ORDER_ERROR, {
            "original_event": event.to_dict(),
            "error": str(e)
        })
```

### 4. 性能考虑

避免在事件处理器中执行耗时操作：

```python
# ❌ 避免在事件处理器中执行耗时操作
@event_handler(EventType.DATA_LOADED)
def slow_handler(event):
    time.sleep(5)  # 这会阻塞事件队列
    
# ✅ 使用异步处理或后台任务
@event_handler(EventType.DATA_LOADED)
def fast_handler(event):
    # 快速处理或提交到后台队列
    background_queue.put(event.data)
```

## API 参考

事件系统的详细API参考请查看 [Events API文档](../api/core/events.md)。

### 主要类和函数

- **EventBus** - 事件总线
- **Event** - 基础事件类
- **MarketDataEvent** - 市场数据事件
- **OrderEvent** - 订单事件
- **TradeEvent** - 交易事件

更多详细信息和使用示例请参考API文档页面。
