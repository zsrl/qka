# 核心模块 API 参考

QKA 的核心功能模块，包含数据管理、回测引擎、策略基类和虚拟经纪商。

## qka.Data

数据管理类，负责股票数据的获取、缓存和管理。

::: qka.core.data.Data
    options:
      show_root_heading: false
      show_source: true
      members_order: source
      heading_level: 3

### 使用示例

```python
import qka

# 创建数据对象
data = qka.Data(
    symbols=['000001.SZ', '600000.SH'],
    period='1d',
    adjust='qfq'
)

# 获取数据
df = data.get()
print(df.head())
```

## qka.Backtest

回测引擎类，提供基于时间序列的回测功能。

::: qka.core.backtest.Backtest
    options:
      show_root_heading: false
      show_source: true
      members_order: source
      heading_level: 3

### 使用示例

```python
# 运行回测
strategy = MyStrategy()
backtest = qka.Backtest(data, strategy)
backtest.run()

# 可视化结果
backtest.plot("我的策略回测结果")
```

## qka.Strategy

策略抽象基类，所有自定义策略都应该继承此类。

::: qka.core.strategy.Strategy
    options:
      show_root_heading: false
      show_source: true
      members_order: source
      heading_level: 3

### 使用示例

```python
class MyStrategy(qka.Strategy):
    def __init__(self):
        super().__init__()
        self.ma_short = 5
        self.ma_long = 20
    
    def on_bar(self, date, get):
        close_prices = get('close')
        # 策略逻辑...
```

## qka.Broker

虚拟交易经纪商类，管理资金、持仓和交易记录。

::: qka.core.broker.Broker
    options:
      show_root_heading: false
      show_source: true
      members_order: source
      heading_level: 3

### 使用示例

```python
# 在策略中使用
class MyStrategy(qka.Strategy):
    def on_bar(self, date, get):
        close_prices = get('close')
        for symbol in close_prices.index:
            if self.should_buy(symbol, close_prices[symbol]):
                self.broker.buy(symbol, close_prices[symbol], 100)
```

## 模块导入方式

根据 [`qka/__init__.py`](../../qka/__init__.py) 的配置，所有核心模块都可以直接从 `qka` 包导入：

```python
import qka

# 直接使用
data = qka.Data(...)
backtest = qka.Backtest(...)
strategy = qka.Strategy(...)  # 作为基类
broker = qka.Broker(...)
```

## 相关链接

- [用户指南 - 数据获取](../../user-guide/data.md)
- [用户指南 - 回测分析](../../user-guide/backtest.md)
- [快速开始 - 第一个策略](../../getting-started/first-strategy.md)
- [交易模块 API](../brokers.md)
- [工具模块 API](../utils.md)