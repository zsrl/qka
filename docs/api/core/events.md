# Events API 参考

::: qka.core.events
    options:
      show_root_heading: true
      show_source: true
      heading_level: 2
      members_order: source
      show_signature_annotations: true
      separate_signature: true

## 事件系统使用指南

### 基本概念

事件系统采用发布-订阅模式，支持：
- 事件发布和订阅
- 异步事件处理
- 事件过滤和转换
- 事件统计和监控

### 基本用法

```python
from qka.core.events import EventBus, Event

# 创建事件总线
bus = EventBus()

# 定义事件处理器
def handle_order(event):
    print(f"处理订单事件: {event}")

# 订阅事件
bus.subscribe('order_created', handle_order)

# 发布事件
event = Event('order_created', {'symbol': 'AAPL', 'quantity': 100})
bus.publish(event)
```

### 预定义事件类型

#### MarketDataEvent - 市场数据事件

```python
from qka.core.events import MarketDataEvent

# 创建市场数据事件
event = MarketDataEvent(
    symbol='AAPL',
    timestamp=datetime.now(),
    data={
        'open': 150.0,
        'high': 152.0,
        'low': 149.0,
        'close': 151.0,
        'volume': 1000000
    }
)

# 订阅市场数据事件
@bus.subscribe('market_data')
def handle_market_data(event):
    symbol = event.symbol
    price = event.data['close']
    print(f"{symbol}: ${price}")
```

#### OrderEvent - 订单事件

```python
from qka.core.events import OrderEvent

# 创建订单事件
order_event = OrderEvent(
    order_id='ORD_001',
    symbol='AAPL',
    side='buy',
    quantity=100,
    price=150.0,
    order_type='limit',
    status='pending'
)

# 订阅订单事件
@bus.subscribe('order')
def handle_order(event):
    print(f"订单 {event.order_id}: {event.status}")
```

#### TradeEvent - 交易事件

```python
from qka.core.events import TradeEvent

# 创建交易事件
trade_event = TradeEvent(
    trade_id='TRD_001',
    order_id='ORD_001',
    symbol='AAPL',
    side='buy',
    quantity=100,
    price=150.5,
    commission=0.15,
    timestamp=datetime.now()
)

# 订阅交易事件
@bus.subscribe('trade')
def handle_trade(event):
    print(f"交易完成: {event.symbol} {event.side} {event.quantity}@{event.price}")
```

### 高级功能

#### 异步事件处理

```python
import asyncio
from qka.core.events import EventBus

# 创建支持异步的事件总线
bus = EventBus(async_mode=True)

# 异步事件处理器
async def async_handler(event):
    await asyncio.sleep(1)  # 模拟异步操作
    print(f"异步处理事件: {event}")

# 订阅异步处理器
bus.subscribe('async_event', async_handler)

# 发布事件（异步处理）
await bus.publish_async(Event('async_event', {'data': 'test'}))
```

#### 事件过滤

```python
# 带条件的事件订阅
def price_filter(event):
    return event.data.get('price', 0) > 100

bus.subscribe('market_data', handle_expensive_stocks, filter_func=price_filter)

# 仅处理价格大于100的股票数据
event = MarketDataEvent('AAPL', data={'price': 150})
bus.publish(event)  # 会被处理

event = MarketDataEvent('PENNY', data={'price': 5})
bus.publish(event)  # 不会被处理
```

#### 事件转换

```python
# 事件转换器
def price_transformer(event):
    # 将价格转换为人民币
    if 'price' in event.data:
        event.data['price_cny'] = event.data['price'] * 7.0
    return event

bus.subscribe('market_data', handle_cny_price, transformer=price_transformer)
```

#### 批量事件处理

```python
# 批量事件处理器
@bus.subscribe_batch('market_data', batch_size=10, timeout=5)
def handle_batch(events):
    prices = [e.data['price'] for e in events]
    avg_price = sum(prices) / len(prices)
    print(f"批量处理 {len(events)} 条数据，平均价格: {avg_price}")

# 发布多个事件
for i in range(20):
    event = MarketDataEvent(f'STOCK_{i}', data={'price': 100 + i})
    bus.publish(event)
```

### 事件统计和监控

```python
# 获取事件统计
stats = bus.get_statistics()
print(f"总事件数: {stats['total_events']}")
print(f"订阅者数: {stats['total_subscribers']}")
print(f"事件类型分布: {stats['event_types']}")

# 监控事件处理性能
@bus.subscribe('performance_monitor')
def monitor_handler(event):
    processing_time = event.processing_time
    if processing_time > 1.0:  # 超过1秒
        print(f"事件处理较慢: {processing_time:.2f}s")
```

### 错误处理

```python
# 错误处理器
def error_handler(event, exception):
    print(f"事件处理失败: {event}, 错误: {exception}")
    # 记录错误日志或发送告警

bus.set_error_handler(error_handler)

# 带重试的事件处理
@bus.subscribe('critical_event', retry_count=3, retry_delay=1)
def critical_handler(event):
    if random.random() < 0.5:
        raise Exception("模拟处理失败")
    print(f"关键事件处理成功: {event}")
```

### 事件持久化

```python
# 启用事件持久化
bus.enable_persistence('events.db')

# 重放历史事件
bus.replay_events(
    event_type='market_data',
    start_time=datetime(2024, 1, 1),
    end_time=datetime(2024, 1, 31)
)
```

## 最佳实践

1. **事件设计**
   - 事件名称要清晰、一致
   - 事件数据结构要稳定
   - 避免事件过于频繁

2. **性能优化**
   - 异步处理耗时操作
   - 合理使用批量处理
   - 监控事件处理性能

3. **错误处理**
   - 处理器要有错误处理逻辑
   - 关键事件要有重试机制
   - 记录事件处理日志

4. **测试**
   - 模拟事件进行单元测试
   - 测试异常情况处理
   - 性能测试和压力测试
