# 第一个策略

本教程将指导您创建和运行您的第一个量化交易策略。

## 策略概述

我们将创建一个简单的均线策略：
- 当短期均线上穿长期均线时买入（金叉）
- 当短期均线下穿长期均线时卖出（死叉）

## 创建策略文件

创建一个新文件 `my_first_strategy.py`：

```python
"""
我的第一个量化策略
简单的双均线策略
"""

import qka
from qka.core.backtest import Strategy
from qka.core.data import get_stock_data


class MovingAverageStrategy(Strategy):
    """双均线策略"""
    
    def __init__(self, short_window=20, long_window=50):
        super().__init__()
        self.short_window = short_window
        self.long_window = long_window
        self.name = f"双均线策略({short_window}/{long_window})"
        
        # 存储均线数据
        self.short_ma = {}
        self.long_ma = {}
        self.last_signal = {}
    
    def on_init(self):
        """策略初始化"""
        self.log("策略初始化开始")
        
        # 订阅股票数据
        self.subscribe('000001.SZ')  # 平安银行
        
        self.log("策略初始化完成")
    
    def calculate_moving_average(self, prices, window):
        """计算移动平均线"""
        if len(prices) < window:
            return None
        return sum(prices[-window:]) / window
    
    def on_data(self, data):
        """处理数据更新"""
        for symbol in data.index:
            # 获取历史价格
            prices = self.get_price_history(symbol, self.long_window + 10)
            
            if len(prices) < self.long_window:
                continue
            
            # 计算短期和长期均线
            short_ma = self.calculate_moving_average(prices, self.short_window)
            long_ma = self.calculate_moving_average(prices, self.long_window)
            
            if short_ma is None or long_ma is None:
                continue
            
            # 获取之前的均线值
            prev_short = self.short_ma.get(symbol, 0)
            prev_long = self.long_ma.get(symbol, 0)
            
            # 当前持仓
            position = self.get_position(symbol)
            current_price = data.loc[symbol, 'close']
            
            # 交易信号判断
            if short_ma > long_ma and prev_short <= prev_long:
                # 金叉 - 买入信号
                if not position:
                    volume = self.calculate_position_size(symbol, current_price)
                    if volume > 0:
                        self.buy(symbol, volume)
                        self.log(f"{symbol} 金叉买入，价格: {current_price:.2f}, 数量: {volume}")
                        self.last_signal[symbol] = 'BUY'
            
            elif short_ma < long_ma and prev_short >= prev_long:
                # 死叉 - 卖出信号
                if position and position.volume > 0:
                    self.sell(symbol, position.volume)
                    self.log(f"{symbol} 死叉卖出，价格: {current_price:.2f}, 数量: {position.volume}")
                    self.last_signal[symbol] = 'SELL'
            
            # 保存当前均线值
            self.short_ma[symbol] = short_ma
            self.long_ma[symbol] = long_ma
    
    def calculate_position_size(self, symbol, price):
        """计算买入数量"""
        # 使用可用资金的10%买入
        available_cash = self.get_available_cash()
        target_value = available_cash * 0.1
        volume = int(target_value / price / 100) * 100  # 整手买入
        return volume
    
    def on_order(self, order):
        """订单状态变化回调"""
        self.log(f"订单更新: {order.symbol} {order.side} {order.volume}股 @ {order.price:.2f} - {order.status}")
    
    def on_trade(self, trade):
        """成交回调"""
        self.log(f"成交确认: {trade.symbol} {trade.side} {trade.volume}股 @ {trade.price:.2f}")


if __name__ == "__main__":
    # 运行策略
    print("开始运行双均线策略...")
    
    # 1. 加载配置
    qka.config.backtest.initial_cash = 1000000  # 100万初始资金
    qka.config.backtest.commission_rate = 0.0003  # 万三手续费
    
    # 2. 创建回测引擎
    from qka.core.backtest import BacktestEngine
    
    engine = BacktestEngine(
        initial_cash=qka.config.backtest.initial_cash,
        start_date='2024-01-01',
        end_date='2024-06-30',
        commission_rate=qka.config.backtest.commission_rate
    )
    
    # 3. 获取数据
    print("正在获取数据...")
    data = get_stock_data('000001.SZ', start='2024-01-01', end='2024-06-30')
    engine.add_data(data)
    
    # 4. 创建并运行策略
    strategy = MovingAverageStrategy(short_window=20, long_window=50)
    
    print("开始回测...")
    result = engine.run(strategy)
    
    # 5. 显示结果
    print("\n" + "="*50)
    print("回测结果")
    print("="*50)
    print(f"策略名称: {strategy.name}")
    print(f"回测期间: 2024-01-01 至 2024-06-30")
    print(f"初始资金: ¥{qka.config.backtest.initial_cash:,.2f}")
    print(f"最终资金: ¥{result.final_value:,.2f}")
    print(f"总收益率: {result.total_return:.2%}")
    print(f"年化收益率: {result.annual_return:.2%}")
    print(f"最大回撤: {result.max_drawdown:.2%}")
    print(f"夏普比率: {result.sharpe_ratio:.2f}")
    print(f"交易次数: {result.trade_count}")
    print(f"胜率: {result.win_rate:.2%}")
    
    # 6. 绘制收益曲线（如果有matplotlib）
    try:
        from qka.core.plot import plot_returns
        plot_returns(result.returns, title="双均线策略收益曲线")
        print("\n收益曲线图已显示")
    except ImportError:
        print("\n提示: 安装 matplotlib 可以查看收益曲线图")
        print("命令: pip install matplotlib")
    
    print("\n策略运行完成！")
```

## 运行策略

### 命令行运行

```bash
# 确保已安装 QKA
pip install qka

# 运行策略
python my_first_strategy.py
```

### 预期输出

```
开始运行双均线策略...
正在获取数据...
开始回测...

==================================================
回测结果
==================================================
策略名称: 双均线策略(20/50)
回测期间: 2024-01-01 至 2024-06-30
初始资金: ¥1,000,000.00
最终资金: ¥1,050,000.00
总收益率: 5.00%
年化收益率: 10.25%
最大回撤: -3.20%
夏普比率: 1.15
交易次数: 8
胜率: 62.50%

收益曲线图已显示
策略运行完成！
```

## 理解代码

### 策略类结构

```python
class MovingAverageStrategy(Strategy):
    def __init__(self):
        # 初始化参数
        
    def on_init(self):
        # 策略启动时执行一次
        
    def on_data(self, data):
        # 每次数据更新时执行
        
    def on_order(self, order):
        # 订单状态变化时执行
        
    def on_trade(self, trade):
        # 成交时执行
```

### 关键方法说明

| 方法 | 作用 | 调用时机 |
|------|------|----------|
| `on_init()` | 策略初始化 | 策略开始时 |
| `on_data()` | 处理数据 | 每个交易日 |
| `buy()` | 买入股票 | 产生买入信号时 |
| `sell()` | 卖出股票 | 产生卖出信号时 |
| `get_position()` | 获取持仓 | 需要查询持仓时 |
| `log()` | 记录日志 | 任何时候 |

## 策略优化

### 参数调优

```python
# 测试不同参数组合
strategies = []
for short in [10, 15, 20]:
    for long in [30, 40, 50]:
        if short < long:
            strategy = MovingAverageStrategy(short, long)
            result = engine.run(strategy)
            strategies.append((short, long, result.sharpe_ratio))

# 找出最优参数
best_params = max(strategies, key=lambda x: x[2])
print(f"最优参数: 短线={best_params[0]}, 长线={best_params[1]}")
```

### 添加止损止盈

```python
def on_data(self, data):
    # ...原有逻辑...
    
    # 检查止损止盈
    for symbol in self.positions:
        position = self.get_position(symbol)
        if position and position.volume > 0:
            current_price = data.loc[symbol, 'close']
            cost_price = position.avg_price
            
            # 计算收益率
            return_rate = (current_price - cost_price) / cost_price
            
            # 止损（-5%）
            if return_rate <= -0.05:
                self.sell(symbol, position.volume)
                self.log(f"{symbol} 触发止损")
            
            # 止盈（+10%）
            elif return_rate >= 0.10:
                self.sell(symbol, position.volume)
                self.log(f"{symbol} 触发止盈")
```

## 下一步

现在您已经创建了第一个策略，可以：

1. **学习更多策略**：查看 [示例教程](../examples/simple-strategy.md)
2. **优化策略**：了解 [参数优化](../user-guide/backtest.md#参数优化)
3. **风险管理**：学习 [风险控制](../examples/risk-management.md)
4. **实盘交易**：准备 [实盘部署](../user-guide/trading.md)

## 常见问题

### Q: 如何添加更多股票？

```python
def on_init(self):
    # 添加多只股票
    stocks = ['000001.SZ', '000002.SZ', '600000.SH']
    for stock in stocks:
        self.subscribe(stock)
```

### Q: 如何修改买入金额？

```python
def calculate_position_size(self, symbol, price):
    # 固定金额买入（比如每次10000元）
    target_value = 10000
    volume = int(target_value / price / 100) * 100
    return volume
```

### Q: 如何保存回测结果？

```python
# 保存结果到文件
import json
results = {
    'total_return': result.total_return,
    'sharpe_ratio': result.sharpe_ratio,
    'max_drawdown': result.max_drawdown
}

with open('backtest_results.json', 'w') as f:
    json.dump(results, f, indent=2)
```

恭喜！您已经创建并运行了第一个量化交易策略。
