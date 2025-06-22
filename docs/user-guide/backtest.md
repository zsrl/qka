# 回测分析

QKA 提供了简洁易用的回测功能，帮助您快速验证交易策略的有效性。

## 快速开始

### 三步完成回测

QKA 回测非常简单，只需三步：

```python
import qka

# 第1步：获取数据
data_obj = qka.data(stocks=['000001', '000002'])  # 默认使用akshare数据源

# 第2步：定义策略
class SimpleStrategy(qka.Strategy):
    def on_bar(self, data, broker, current_date):
        for symbol, df in data.items():
            if len(df) >= 20:
                price = df['close'].iloc[-1]
                ma20 = df['close'].rolling(20).mean().iloc[-1]
                
                if price > ma20:  # 突破均线买入
                    broker.buy(symbol, 0.5, price)
                elif price < ma20:  # 跌破均线卖出
                    broker.sell(symbol, 1.0, price)

# 第3步：运行回测并查看结果
result = qka.backtest(data_obj, SimpleStrategy(), start_time='2023-01-01', end_time='2023-12-31')

print(f"总收益率: {result['total_return']:.2%}")
print(f"年化收益率: {result['annual_return']:.2%}")
print(f"夏普比率: {result['sharpe_ratio']:.2f}")
```

> **数据源说明**: 默认使用akshare数据源。如需使用其他数据源，可以调用 `set_source('qmt')` 或在 `data()` 函数中指定 `source` 参数。

## 策略开发

### 策略基类

所有策略都需要继承 `qka.Strategy` 基类：

```python
import qka

class MyStrategy(qka.Strategy):
    def on_bar(self, data, broker, current_date):
        """
        每个交易日调用的策略逻辑
        
        Args:
            data: 历史数据字典 {股票代码: DataFrame}
            broker: 交易接口
            current_date: 当前日期
        """
        # 在这里实现你的策略逻辑
        pass
    
    def on_start(self, broker):
        """回测开始时调用"""
        print(f"策略 {self.name} 开始运行")
    
    def on_end(self, broker):
        """回测结束时调用"""
        print(f"策略 {self.name} 运行结束")
```

### 策略示例

#### 移动平均策略

```python
class MovingAverageStrategy(qka.Strategy):
    def __init__(self, short_window=5, long_window=20):
        super().__init__()
        self.short_window = short_window
        self.long_window = long_window
    
    def on_bar(self, data, broker, current_date):
        for symbol, df in data.items():
            if len(df) < self.long_window:
                continue
                
            # 计算短期和长期移动平均
            short_ma = df['close'].rolling(self.short_window).mean().iloc[-1]
            long_ma = df['close'].rolling(self.long_window).mean().iloc[-1]
            current_price = df['close'].iloc[-1]
            
            # 金叉买入，死叉卖出
            if short_ma > long_ma and broker.get_position(symbol) == 0:
                broker.buy(symbol, 0.3, current_price)  # 用30%资金买入
            elif short_ma < long_ma and broker.get_position(symbol) > 0:
                broker.sell(symbol, 1.0, current_price)  # 全部卖出
```

#### 布林带策略

```python
class BollingerBandStrategy(qka.Strategy):
    def __init__(self, window=20, num_std=2):
        super().__init__()
        self.window = window
        self.num_std = num_std
    
    def on_bar(self, data, broker, current_date):
        for symbol, df in data.items():
            if len(df) < self.window:
                continue
                
            # 计算布林带
            close_prices = df['close']
            rolling_mean = close_prices.rolling(self.window).mean().iloc[-1]
            rolling_std = close_prices.rolling(self.window).std().iloc[-1]
            
            upper_band = rolling_mean + (rolling_std * self.num_std)
            lower_band = rolling_mean - (rolling_std * self.num_std)
            current_price = close_prices.iloc[-1]
            
            # 价格突破下轨买入，突破上轨卖出
            if current_price < lower_band and broker.get_position(symbol) == 0:
                broker.buy(symbol, 0.4, current_price)
            elif current_price > upper_band and broker.get_position(symbol) > 0:
                broker.sell(symbol, 1.0, current_price)
```

## 交易接口

### Broker 类

`Broker` 类提供了所有交易相关的功能：

```python
# 获取当前持仓
position = broker.get_position('000001')  # 返回持仓股数

# 获取可用现金
cash = broker.get_cash()

# 获取所有持仓
positions = broker.get_positions()  # 返回 {股票代码: 持仓数量}

# 计算总资产
prices = {'000001': 10.5, '000002': 8.3}
total_value = broker.get_total_value(prices)
```

### 买入操作

```python
# 按比例买入（推荐）
broker.buy('000001', 0.3, price)  # 用30%的资金买入

# 按股数买入
broker.buy('000001', 1000, price)  # 买入1000股（自动调整为整手）

# 买入条件检查
if broker.get_cash() > 10000:  # 现金充足
    if broker.get_position('000001') == 0:  # 没有持仓
        broker.buy('000001', 0.2, current_price)
```

### 卖出操作

```python
# 按比例卖出
broker.sell('000001', 0.5, price)  # 卖出50%的持仓
broker.sell('000001', 1.0, price)  # 全部卖出

# 按股数卖出
broker.sell('000001', 500, price)  # 卖出500股

# 卖出条件检查
if broker.get_position('000001') > 0:  # 有持仓
    broker.sell('000001', 1.0, current_price)  # 全部卖出
```

## 回测配置

### 基本配置

```python
import qka

# 自定义 Broker 配置
custom_broker = qka.Broker(
    initial_cash=500000,     # 初始资金50万
    commission_rate=0.0003   # 手续费率0.03%
)

# 使用自定义配置运行回测
result = qka.backtest(
    data=data_obj,
    strategy=MyStrategy(),
    broker=custom_broker,
    start_time='2023-01-01',
    end_time='2023-12-31'
)
```

### 数据获取

```python
import qka

# 使用默认数据源（akshare）
data_obj = qka.data(stocks=['000001'])

# 多只股票
data_obj = qka.data(stocks=['000001', '000002', '600000'])

# 设置全局数据源
qka.set_source('qmt')
data_obj = qka.data(stocks=['000001.SZ', '600000.SH'])  # QMT格式股票代码

# 临时指定数据源
data_obj = qka.data(stocks=['000001'], source='akshare')
```

## 回测结果分析

### 基本指标

回测结果包含以下关键指标：

```python
# 基本收益指标
print(f"初始资金: {result['initial_capital']:,.0f}")
print(f"最终资产: {result['final_value']:,.0f}")
print(f"总收益率: {result['total_return']:.2%}")
print(f"年化收益率: {result['annual_return']:.2%}")

# 风险指标
print(f"收益波动率: {result['volatility']:.2%}")
print(f"夏普比率: {result['sharpe_ratio']:.2f}")
print(f"最大回撤: {result['max_drawdown']:.2%}")

# 交易指标
print(f"总交易次数: {result['total_trades']}")
print(f"总手续费: {result['total_commission']:,.2f}")
print(f"胜率: {result['win_rate']:.2%}")
print(f"交易天数: {result['trading_days']}")
```

### 详细数据

```python
# 每日净值数据
daily_values = result['daily_values']
for record in daily_values[:5]:  # 显示前5天
    print(f"日期: {record['date']}, 总资产: {record['total_value']:,.2f}")

# 交易记录
trades = result['trades']
for trade in trades[:5]:  # 显示前5笔交易
    print(f"{trade['date']}: {trade['action']} {trade['symbol']} "
          f"{trade['shares']}股 @{trade['price']}")

# 最终持仓
positions = result['positions']
print(f"最终持仓: {positions}")
```

## 结果可视化

```python
import qka

# 绘制回测结果图表
qka.plot(result)
```

## 策略开发技巧

### 数据处理

```python
def on_bar(self, data, broker, current_date):
    for symbol, df in data.items():
        # 检查数据长度
        if len(df) < 20:
            continue
            
        # 获取最新价格
        current_price = df['close'].iloc[-1]
        
        # 计算技术指标
        sma_20 = df['close'].rolling(20).mean().iloc[-1]
        rsi = self.calculate_rsi(df['close'], 14)
        
        # 处理缺失值
        if pd.isna(sma_20) or pd.isna(rsi):
            continue
            
        # 策略逻辑
        if rsi < 30 and current_price > sma_20:
            broker.buy(symbol, 0.2, current_price)
```

### 风险控制

```python
def on_bar(self, data, broker, current_date):
    for symbol, df in data.items():
        current_price = df['close'].iloc[-1]
        position = broker.get_position(symbol)
        
        # 止损逻辑
        if position > 0:
            avg_cost = broker.avg_costs.get(symbol, current_price)
            if current_price < avg_cost * 0.95:  # 5%止损
                broker.sell(symbol, 1.0, current_price)
                continue
        
        # 仓位控制
        total_value = broker.get_total_value({symbol: current_price})
        position_value = position * current_price
        position_ratio = position_value / total_value
        
        if position_ratio > 0.3:  # 单只股票最大30%仓位
            continue
            
        # 买入逻辑
        # ...
```

### 多股票策略

```python
class MultiStockStrategy(qka.Strategy):
    def on_bar(self, data, broker, current_date):
        # 收集所有股票的信号
        signals = {}
        for symbol, df in data.items():
            if len(df) >= 20:
                signal = self.calculate_signal(df)
                signals[symbol] = signal
        
        # 按信号强度排序
        sorted_signals = sorted(signals.items(), 
                              key=lambda x: x[1], reverse=True)
        
        # 只选择前3只股票
        selected_stocks = sorted_signals[:3]
        
        # 平均分配资金
        for symbol, signal in selected_stocks:
            if signal > 0.5 and broker.get_position(symbol) == 0:
                broker.buy(symbol, 0.3, data[symbol]['close'].iloc[-1])
```

## 最佳实践

### 1. 数据质量检查

```python
def on_bar(self, data, broker, current_date):
    for symbol, df in data.items():
        # 检查价格合理性
        current_price = df['close'].iloc[-1]
        if current_price <= 0 or pd.isna(current_price):
            continue
            
        # 检查成交量
        volume = df['volume'].iloc[-1]
        if volume <= 0:
            continue
            
        # 策略逻辑
        # ...
```

### 2. 参数化策略

```python
class ParameterizedStrategy(qka.Strategy):
    def __init__(self, ma_period=20, position_size=0.3, stop_loss=0.05):
        super().__init__()
        self.ma_period = ma_period
        self.position_size = position_size
        self.stop_loss = stop_loss
    
    def on_bar(self, data, broker, current_date):
        for symbol, df in data.items():
            if len(df) < self.ma_period:
                continue
                
            current_price = df['close'].iloc[-1]
            ma = df['close'].rolling(self.ma_period).mean().iloc[-1]
            
            # 使用参数化的逻辑
            if current_price > ma:
                broker.buy(symbol, self.position_size, current_price)
```

### 3. 策略状态管理

```python
class StatefulStrategy(qka.Strategy):
    def __init__(self):
        super().__init__()
        self.last_signal = {}
        self.entry_prices = {}
    
    def on_bar(self, data, broker, current_date):
        for symbol, df in data.items():
            # 保存策略状态
            current_signal = self.calculate_signal(df)
            last_signal = self.last_signal.get(symbol, 0)
            
            # 信号变化时才交易
            if current_signal != last_signal:
                if current_signal > 0:
                    price = df['close'].iloc[-1]
                    broker.buy(symbol, 0.3, price)
                    self.entry_prices[symbol] = price
                else:
                    broker.sell(symbol, 1.0, df['close'].iloc[-1])
                    self.entry_prices.pop(symbol, None)
            
            self.last_signal[symbol] = current_signal
```

## 常见问题

### Q: 如何处理停牌股票？

```python
def on_bar(self, data, broker, current_date):
    for symbol, df in data.items():
        # 检查是否停牌
        if current_date not in df.index:
            continue  # 跳过停牌股票
            
        current_price = df.loc[current_date, 'close']
        if current_price == 0:
            continue  # 价格为0可能是停牌
```

### Q: 如何避免未来函数？

```python
def on_bar(self, data, broker, current_date):
    for symbol, df in data.items():
        # 只使用当前日期之前的数据
        historical_data = df.loc[:current_date]
        
        # 计算指标时确保不使用未来数据
        sma = historical_data['close'].rolling(20).mean().iloc[-1]
```

### Q: 如何处理数据缺失？

```python
def on_bar(self, data, broker, current_date):
    for symbol, df in data.items():
        # 检查关键数据是否缺失
        if df[['open', 'high', 'low', 'close', 'volume']].iloc[-1].isna().any():
            continue
        
        # 使用前向填充处理缺失值
        df_filled = df.fillna(method='ffill')
```
