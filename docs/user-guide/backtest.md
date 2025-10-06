# 回测分析

QKA 提供完整的回测功能，支持策略验证、性能分析和结果可视化。

## 基本用法

### 创建回测

```python
import qka

# 1. 准备数据
data = qka.Data(symbols=['000001.SZ', '600000.SH'])

# 2. 创建策略
class MyStrategy(qka.Strategy):
    def on_bar(self, date, get):
        close_prices = get('close')
        # 策略逻辑...

# 3. 运行回测
strategy = MyStrategy()
backtest = qka.Backtest(data, strategy)
backtest.run()
```

### 查看回测结果

```python
# 查看最终状态
print(f"最终资金: {strategy.broker.cash:.2f}")
print(f"持仓情况: {strategy.broker.positions}")

# 查看交易记录
trades_df = strategy.broker.trades
print("交易记录:")
print(trades_df.tail())
```

## 可视化分析

### 收益曲线

```python
# 绘制收益曲线
fig = backtest.plot("我的策略回测结果")

# 自定义图表标题
fig = backtest.plot("自定义标题")
```

### 详细分析

```python
# 计算关键指标
trades_df = strategy.broker.trades

# 总收益率
initial_cash = 100000
final_total = trades_df['total'].iloc[-1]
total_return = (final_total - initial_cash) / initial_cash * 100

# 最大回撤
peak = trades_df['total'].expanding().max()
drawdown = (trades_df['total'] - peak) / peak * 100
max_drawdown = drawdown.min()

print(f"总收益率: {total_return:.2f}%")
print(f"最大回撤: {max_drawdown:.2f}%")
print(f"夏普比率: {calculate_sharpe(trades_df):.2f}")
```

## 策略开发指南

### 策略结构

所有策略必须继承 `qka.Strategy` 并实现 `on_bar` 方法：

```python
class MyStrategy(qka.Strategy):
    def __init__(self):
        super().__init__()
        # 初始化策略参数
        self.param1 = value1
        self.param2 = value2
    
    def on_bar(self, date, get):
        """
        date: 当前时间戳
        get: 获取因子数据的函数
        """
        # 获取数据
        close_prices = get('close')
        volumes = get('volume')
        
        # 策略逻辑
        for symbol in close_prices.index:
            current_price = close_prices[symbol]
            current_volume = volumes[symbol]
            
            # 交易决策
            if self.should_buy(symbol, current_price, current_volume):
                self.buy(symbol, current_price)
            elif self.should_sell(symbol, current_price, current_volume):
                self.sell(symbol, current_price)
    
    def should_buy(self, symbol, price, volume):
        # 买入条件
        return True  # 替换为实际条件
    
    def should_sell(self, symbol, price, volume):
        # 卖出条件
        return True  # 替换为实际条件
    
    def buy(self, symbol, price):
        # 买入逻辑
        size = self.calculate_position_size(price)
        self.broker.buy(symbol, price, size)
    
    def sell(self, symbol, price):
        # 卖出逻辑
        position = self.broker.positions.get(symbol)
        if position:
            self.broker.sell(symbol, price, position['size'])
```

### 数据访问

在 `on_bar` 方法中，使用 `get` 函数访问数据：

```python
def on_bar(self, date, get):
    # 获取收盘价（所有股票）
    close_prices = get('close')
    
    # 获取成交量
    volumes = get('volume')
    
    # 获取开盘价
    open_prices = get('open')
    
    # 获取自定义因子（如果定义了）
    ma5_values = get('ma5')  # 假设在数据中定义了ma5因子
```

## 风险控制

### 仓位管理

```python
class RiskManagedStrategy(qka.Strategy):
    def __init__(self):
        super().__init__()
        self.max_position_ratio = 0.1  # 单只股票最大仓位比例
        self.max_total_position = 0.8  # 总仓位上限
    
    def calculate_position_size(self, symbol, price):
        # 计算合理的买入数量
        available_cash = self.broker.cash
        total_assets = self.broker.get('total')
        
        # 单只股票仓位限制
        max_position_value = total_assets * self.max_position_ratio
        max_shares = int(max_position_value / price)
        
        # 总仓位限制
        current_position_value = sum(
            pos['size'] * pos['avg_price'] 
            for pos in self.broker.positions.values()
        )
        available_for_new = total_assets * self.max_total_position - current_position_value
        max_shares_by_total = int(available_for_new / price)
        
        return min(max_shares, max_shares_by_total, int(available_cash / price))
```

### 止损策略

```python
class StopLossStrategy(qka.Strategy):
    def __init__(self):
        super().__init__()
        self.stop_loss_rate = 0.05  # 5%止损
        self.entry_prices = {}      # 记录买入价格
    
    def on_bar(self, date, get):
        close_prices = get('close')
        
        # 检查止损
        for symbol, position in self.broker.positions.items():
            if symbol in self.entry_prices:
                entry_price = self.entry_prices[symbol]
                current_price = close_prices[symbol]
                loss_rate = (current_price - entry_price) / entry_price
                
                if loss_rate <= -self.stop_loss_rate:
                    # 触发止损
                    self.broker.sell(symbol, current_price, position['size'])
                    del self.entry_prices[symbol]
        
        # 正常的买入逻辑
        for symbol in close_prices.index:
            if self.should_buy(symbol, close_prices[symbol]):
                size = self.calculate_position_size(symbol, close_prices[symbol])
                if self.broker.buy(symbol, close_prices[symbol], size):
                    self.entry_prices[symbol] = close_prices[symbol]
```

## 性能优化

### 避免重复计算

```python
class OptimizedStrategy(qka.Strategy):
    def __init__(self):
        super().__init__()
        self.cache = {}  # 缓存计算结果
    
    def on_bar(self, date, get):
        # 缓存数据访问
        close_prices = get('close')
        
        for symbol in close_prices.index:
            # 避免重复获取相同数据
            if symbol not in self.cache:
                self.cache[symbol] = self.calculate_indicators(symbol, get)
            
            indicators = self.cache[symbol]
            
            # 使用缓存的数据进行决策
            if self.should_trade(symbol, indicators):
                # 交易逻辑...
                pass
```

### 批量处理

```python
class BatchStrategy(qka.Strategy):
    def on_bar(self, date, get):
        # 一次性获取所有需要的数据
        close_prices = get('close')
        volumes = get('volume')
        ma5_values = get('ma5')
        ma20_values = get('ma20')
        
        # 批量计算交易信号
        buy_signals = self.calculate_buy_signals(close_prices, volumes, ma5_values, ma20_values)
        sell_signals = self.calculate_sell_signals(close_prices, volumes, ma5_values, ma20_values)
        
        # 批量执行交易
        for symbol, should_buy in buy_signals.items():
            if should_buy:
                self.buy(symbol, close_prices[symbol])
        
        for symbol, should_sell in sell_signals.items():
            if should_sell:
                self.sell(symbol, close_prices[symbol])
```

## 高级功能

### 多时间框架

```python
class MultiTimeframeStrategy(qka.Strategy):
    def __init__(self):
        super().__init__()
        # 加载不同时间框架的数据
        self.daily_data = qka.Data(symbols=['000001.SZ'], period='1d')
        self.hourly_data = qka.Data(symbols=['000001.SZ'], period='1h')
    
    def on_bar(self, date, get):
        # 日线级别判断趋势
        daily_trend = self.analyze_daily_trend()
        
        # 小时线级别寻找入场点
        if daily_trend == 'up':
            hourly_signal = self.analyze_hourly_signal()
            if hourly_signal == 'buy':
                # 执行买入
                pass
```

### 参数优化

```python
# 简单的参数网格搜索
def optimize_strategy():
    best_params = None
    best_return = -float('inf')
    
    for ma_short in [5, 10, 20]:
        for ma_long in [20, 30, 50]:
            # 使用不同参数运行回测
            data = qka.Data(symbols=['000001.SZ'])
            strategy = MovingAverageStrategy(ma_short, ma_long)
            backtest = qka.Backtest(data, strategy)
            backtest.run()
            
            # 计算收益率
            final_total = strategy.broker.get('total')
            total_return = (final_total - 100000) / 100000
            
            if total_return > best_return:
                best_return = total_return
                best_params = (ma_short, ma_long)
    
    return best_params, best_return
```

## 常见问题

### Q: 回测速度很慢怎么办？

A: 可以尝试：
- 减少股票数量
- 使用更短的时间段
- 优化策略代码，避免重复计算
- 使用更简单的因子

### Q: 如何验证策略的稳定性？

A: 建议：
- 使用不同时间段的数据进行回测
- 进行参数敏感性分析
- 使用交叉验证
- 考虑交易成本和滑点

### Q: 回测结果和实盘差异很大？

A: 可能原因：
- 未来函数（使用了未来数据）
- 未考虑交易成本和滑点
- 数据质量问题
- 市场环境变化

## 下一步

- 学习 [实盘交易](trading.md) 了解如何将策略用于实盘
- 查看 [API 文档](../api/core/backtest.md) 了解完整的回测接口
- 参考 [示例教程](../examples/basic/simple-backtest.md) 获取更多代码示例