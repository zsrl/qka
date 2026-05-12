<!-- AUTO: API 签名 -->

### Broker

### `Broker(**initial_cash** = 100000.0, **commission_rate** = DEFAULT_COMMISSION_RATE, **stamp_duty_rate** = DEFAULT_STAMP_DUTY_RATE, **slippage** = DEFAULT_SLIPPAGE)`

    初始化Broker

### `Broker.on_bar(**date**, **get**)`

    Bar结束时记录当前状态。

### `Broker.buy(**symbol** `str`, **price** `float`, **size** `int`) → `bool``

    买入操作 考虑滑点（买入价上移）和佣金（最低 5 元）。

### `Broker.sell(**symbol** `str`, **price** `float`, **size** `int`) → `bool``

    卖出操作 考虑滑点（卖出价下移）、佣金（最低 5 元）和印花税。

### `Broker.get(**factor** `str`, **timestamp** = None) → `Any``

    从trades DataFrame中获取数据

<!-- /AUTO -->

# Broker 模块

虚拟交易经纪商，管理资金、持仓和费用。

## 初始化

Broker 由 Strategy 自动创建，用户在策略中通过 `self.broker` 访问。

```python
# Strategy 内部自动创建
strategy = MyStrategy(cash=100000)  # 初始资金 10 万
```

## 交易接口

```python
# 买入
self.broker.buy(symbol, price, size)
# symbol: 股票代码，如 '000001.SZ'
# price: 成交价（float）
# size: 股数（int，必须 100 的倍数）

# 卖出
self.broker.sell(symbol, price, size)
```

## 状态属性

```python
self.broker.cash          # 可用资金（float）
self.broker.positions     # 持仓 dict

# 持仓格式：
# {symbol: {'size': int, 'avg_price': float, 'cost': float}}

symbol in self.broker.positions  # 判断是否持仓
```

## 费用设置

```python
from qka import Broker

broker = Broker(
    initial_cash=100000,
    commission_rate=0.00025,   # 万2.5 佣金（默认）
    stamp_duty_rate=0.0005,    # 万5 印花税，仅卖出（默认）
    slippage=0.001,            # 0.1% 滑点（默认）
)
```

- 最低佣金 5 元
- 印花税仅卖出时收取

## 正确/错误用法

```python
# ✅ 正确
if '000001.SZ' in self.broker.positions:
    size = self.broker.positions['000001.SZ']['size']
    self.broker.sell('000001.SZ', price, size)

# ❌ 错误：直接修改内部状态
self.broker.cash -= 1000
self.broker.positions['000001.SZ'] = {'size': 100, ...}
```
