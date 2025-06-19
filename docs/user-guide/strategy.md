# 策略开发

QKA 提供了灵活的策略开发框架，支持多种交易策略模式。

## 策略基类

所有策略都需要继承 `Strategy` 基类：

```python
from qka.core.backtest import Strategy

class MyStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.name = "我的策略"
        self.description = "策略描述"
    
    def on_init(self):
        """策略初始化"""
        self.log("策略初始化完成")
    
    def on_data(self, data):
        """数据更新时调用"""
        # 策略逻辑
        pass
    
    def on_order(self, order):
        """订单状态变化时调用"""
        self.log(f"订单状态: {order.status}")
    
    def on_trade(self, trade):
        """成交时调用"""
        self.log(f"成交: {trade.symbol} {trade.volume}股")
```

## 简单策略示例

### 均线策略

```python
import pandas as pd
from qka.core.backtest import Strategy

class MovingAverageStrategy(Strategy):
    def __init__(self, short_window=20, long_window=50):
        super().__init__()
        self.short_window = short_window
        self.long_window = long_window
        self.name = f"MA策略({short_window}/{long_window})"
    
    def on_init(self):
        # 订阅数据
        self.subscribe('000001.SZ')
        
        # 初始化指标
        self.short_ma = {}
        self.long_ma = {}
    
    def on_data(self, data):
        for symbol in data.index:
            # 计算移动平均线
            prices = self.get_price_history(symbol, self.long_window)
            if len(prices) < self.long_window:
                continue
            
            short_ma = prices[-self.short_window:].mean()
            long_ma = prices.mean()
            
            prev_short = self.short_ma.get(symbol, 0)
            prev_long = self.long_ma.get(symbol, 0)
            
            # 金叉买入
            if short_ma > long_ma and prev_short <= prev_long:
                if not self.get_position(symbol):
                    self.buy(symbol, 100)
                    self.log(f"{symbol} 金叉买入")
            
            # 死叉卖出
            elif short_ma < long_ma and prev_short >= prev_long:
                if self.get_position(symbol):
                    self.sell(symbol, self.get_position(symbol).volume)
                    self.log(f"{symbol} 死叉卖出")
            
            self.short_ma[symbol] = short_ma
            self.long_ma[symbol] = long_ma
```

### 布林带策略

```python
class BollingerBandStrategy(Strategy):
    def __init__(self, window=20, num_std=2):
        super().__init__()
        self.window = window
        self.num_std = num_std
        self.name = f"布林带策略({window}, {num_std})"
    
    def calculate_bollinger_bands(self, prices):
        """计算布林带"""
        rolling_mean = prices.rolling(window=self.window).mean()
        rolling_std = prices.rolling(window=self.window).std()
        
        upper_band = rolling_mean + (rolling_std * self.num_std)
        lower_band = rolling_mean - (rolling_std * self.num_std)
        
        return upper_band, rolling_mean, lower_band
    
    def on_data(self, data):
        for symbol in data.index:
            prices = self.get_price_history(symbol, self.window + 10)
            if len(prices) < self.window:
                continue
            
            upper, middle, lower = self.calculate_bollinger_bands(prices)
            current_price = data.loc[symbol, 'close']
            
            position = self.get_position(symbol)
            
            # 价格触及下轨买入
            if current_price <= lower.iloc[-1] and not position:
                self.buy(symbol, 100)
                self.log(f"{symbol} 触及下轨买入")
            
            # 价格触及上轨卖出
            elif current_price >= upper.iloc[-1] and position:
                self.sell(symbol, position.volume)
                self.log(f"{symbol} 触及上轨卖出")
```

## 高级策略特性

### 多股票策略

```python
class MultiStockStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.stock_pool = ['000001.SZ', '000002.SZ', '600000.SH']
        self.max_positions = 3
    
    def on_init(self):
        # 订阅股票池
        for symbol in self.stock_pool:
            self.subscribe(symbol)
    
    def select_stocks(self, data):
        """股票选择逻辑"""
        scores = {}
        for symbol in self.stock_pool:
            # 计算股票评分
            score = self.calculate_score(symbol, data)
            scores[symbol] = score
        
        # 返回评分最高的股票
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:self.max_positions]
    
    def calculate_score(self, symbol, data):
        """计算股票评分"""
        # 实现评分逻辑
        return 0.5
```

### 动态调仓策略

```python
class RebalanceStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.rebalance_frequency = 'monthly'  # 调仓频率
        self.target_weights = {
            '000001.SZ': 0.4,
            '000002.SZ': 0.3,
            '600000.SH': 0.3
        }
    
    def should_rebalance(self):
        """判断是否需要调仓"""
        # 实现调仓条件判断
        return True
    
    def rebalance(self):
        """执行调仓"""
        total_value = self.get_total_value()
        
        for symbol, target_weight in self.target_weights.items():
            target_value = total_value * target_weight
            current_value = self.get_position_value(symbol)
            
            if abs(target_value - current_value) > 1000:  # 阈值
                if target_value > current_value:
                    # 买入
                    amount = target_value - current_value
                    self.buy_value(symbol, amount)
                else:
                    # 卖出
                    amount = current_value - target_value
                    self.sell_value(symbol, amount)
```

## 策略参数优化

### 参数扫描

```python
from qka.core.backtest import ParameterOptimizer

# 定义参数范围
param_ranges = {
    'short_window': range(5, 21, 5),
    'long_window': range(20, 61, 10)
}

# 创建优化器
optimizer = ParameterOptimizer(MovingAverageStrategy, param_ranges)

# 执行优化
best_params = optimizer.optimize(
    objective='sharpe_ratio',  # 优化目标
    data_range=('2023-01-01', '2023-12-31')
)

print(f"最优参数: {best_params}")
```

### 遗传算法优化

```python
from qka.core.backtest import GeneticOptimizer

optimizer = GeneticOptimizer(
    strategy_class=MovingAverageStrategy,
    param_ranges=param_ranges,
    population_size=50,
    generations=100
)

best_params = optimizer.evolve()
```

## 风险管理

### 止损止盈

```python
class RiskManagedStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.stop_loss_ratio = 0.05  # 5% 止损
        self.take_profit_ratio = 0.10  # 10% 止盈
    
    def check_risk_management(self, symbol):
        """检查风险管理条件"""
        position = self.get_position(symbol)
        if not position:
            return
        
        current_price = self.get_current_price(symbol)
        cost_price = position.avg_price
        
        # 计算收益率
        return_rate = (current_price - cost_price) / cost_price
        
        # 止损
        if return_rate <= -self.stop_loss_ratio:
            self.sell(symbol, position.volume)
            self.log(f"{symbol} 触发止损")
        
        # 止盈
        elif return_rate >= self.take_profit_ratio:
            self.sell(symbol, position.volume)
            self.log(f"{symbol} 触发止盈")
```

### 仓位管理

```python
def calculate_position_size(self, symbol, signal_strength):
    """计算仓位大小"""
    available_cash = self.get_available_cash()
    risk_per_trade = available_cash * 0.02  # 每次交易风险2%
    
    stop_loss_distance = self.calculate_stop_loss_distance(symbol)
    position_size = risk_per_trade / stop_loss_distance
    
    # 调整仓位大小基于信号强度
    position_size *= signal_strength
    
    return min(position_size, available_cash * 0.1)  # 最大10%仓位
```

## 策略评估

### 性能指标

```python
# 在策略中记录关键指标
def on_trade(self, trade):
    super().on_trade(trade)
    
    # 记录自定义指标
    self.record('trade_count', self.get_trade_count())
    self.record('win_rate', self.calculate_win_rate())
    self.record('max_drawdown', self.calculate_max_drawdown())
```

### 策略诊断

```python
from qka.core.backtest import StrategyAnalyzer

analyzer = StrategyAnalyzer()

# 分析策略表现
analysis = analyzer.analyze_strategy(strategy_result)

print(f"年化收益率: {analysis.annual_return:.2%}")
print(f"夏普比率: {analysis.sharpe_ratio:.2f}")
print(f"最大回撤: {analysis.max_drawdown:.2%}")
```

## 最佳实践

1. **清晰的逻辑结构**：将策略逻辑分解为独立的方法
2. **参数化设计**：将关键参数设为可配置
3. **充分的日志记录**：记录关键决策点和执行过程
4. **风险控制**：始终包含风险管理逻辑
5. **性能监控**：定期评估策略表现
6. **版本控制**：保存策略的不同版本

## API 参考

策略开发的详细API参考请查看 [Strategy API文档](../api/core/backtest.md)。

### 主要类和接口

- **Strategy** - 策略基类
- **BacktestEngine** - 回测引擎
- **Portfolio** - 投资组合管理

更多详细信息和示例请参考API文档页面。
