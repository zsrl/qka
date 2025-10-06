# 第一个策略

本指南将带你创建第一个简单的量化策略，包括数据获取、策略开发和回测分析。

## 策略目标

创建一个简单的移动平均策略：
- 当短期均线上穿长期均线时买入
- 当短期均线下穿长期均线时卖出

## 步骤1：数据获取

首先，我们需要获取股票数据：

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
print(f"数据形状: {df.shape}")
print(df.head())
```

## 步骤2：创建策略

继承 `qka.Strategy` 类并实现 `on_bar` 方法：

```python
class MovingAverageStrategy(qka.Strategy):
    def __init__(self):
        super().__init__()
        self.ma_short = 5    # 短期均线周期
        self.ma_long = 20    # 长期均线周期
        self.positions = {}  # 持仓记录
    
    def on_bar(self, date, get):
        """
        每个bar的处理逻辑
        
        Args:
            date: 当前时间戳
            get: 获取因子数据的函数
        """
        # 获取当前价格数据
        close_prices = get('close')
        
        # 遍历所有股票
        for symbol in close_prices.index:
            # 获取该股票的历史数据
            symbol_close = get('close')[symbol]
            
            # 计算移动平均
            if len(symbol_close) >= self.ma_long:
                ma_short = symbol_close[-self.ma_short:].mean()
                ma_long = symbol_close[-self.ma_long:].mean()
                
                current_price = symbol_close.iloc[-1]
                
                # 交易逻辑
                if ma_short > ma_long and symbol not in self.positions:
                    # 短期均线上穿长期均线，买入
                    size = int(self.broker.cash * 0.1 / current_price)  # 使用10%资金
                    if size > 0:
                        self.broker.buy(symbol, current_price, size)
                        self.positions[symbol] = True
                        
                elif ma_short < ma_long and symbol in self.positions:
                    # 短期均线下穿长期均线，卖出
                    position = self.broker.positions.get(symbol)
                    if position:
                        self.broker.sell(symbol, current_price, position['size'])
                        del self.positions[symbol]
```

## 步骤3：运行回测

创建策略实例并运行回测：

```python
# 创建策略实例
strategy = MovingAverageStrategy()

# 创建回测引擎
backtest = qka.Backtest(data, strategy)

# 运行回测
print("开始回测...")
backtest.run()
print("回测完成！")

# 查看回测结果
print(f"最终资金: {strategy.broker.cash:.2f}")
print(f"持仓情况: {strategy.broker.positions}")
```

## 步骤4：可视化结果

使用内置的可视化功能查看回测结果：

```python
# 绘制收益曲线
fig = backtest.plot("移动平均策略回测结果")

# 查看详细交易记录
trades_df = strategy.broker.trades
print("交易记录:")
print(trades_df.tail())

# 计算收益率
initial_cash = 100000
final_total = trades_df['total'].iloc[-1]
total_return = (final_total - initial_cash) / initial_cash * 100
print(f"总收益率: {total_return:.2f}%")
```

## 完整代码示例

```python
import qka

class MovingAverageStrategy(qka.Strategy):
    def __init__(self):
        super().__init__()
        self.ma_short = 5
        self.ma_long = 20
        self.positions = {}
    
    def on_bar(self, date, get):
        close_prices = get('close')
        
        for symbol in close_prices.index:
            symbol_close = get('close')[symbol]
            
            if len(symbol_close) >= self.ma_long:
                ma_short = symbol_close[-self.ma_short:].mean()
                ma_long = symbol_close[-self.ma_long:].mean()
                current_price = symbol_close.iloc[-1]
                
                if ma_short > ma_long and symbol not in self.positions:
                    size = int(self.broker.cash * 0.1 / current_price)
                    if size > 0:
                        self.broker.buy(symbol, current_price, size)
                        self.positions[symbol] = True
                elif ma_short < ma_long and symbol in self.positions:
                    position = self.broker.positions.get(symbol)
                    if position:
                        self.broker.sell(symbol, current_price, position['size'])
                        del self.positions[symbol]

# 执行策略
data = qka.Data(symbols=['000001.SZ', '600000.SH'], period='1d')
strategy = MovingAverageStrategy()
backtest = qka.Backtest(data, strategy)
backtest.run()
backtest.plot()
```

## 策略优化建议

1. **参数调优**: 尝试不同的均线周期组合
2. **风险控制**: 添加止损和仓位控制
3. **多因子**: 结合其他技术指标
4. **数据验证**: 使用更长时间段的数据进行验证

## 下一步

- 学习 [基础概念](concepts.md) 深入了解 QKA 架构
- 查看 [用户指南](../user-guide/data.md) 学习更多高级功能
- 参考 [API 文档](../api/core/data.md) 了解完整接口说明