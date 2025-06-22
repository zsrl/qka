"""
QKA 简化回测API演示 - 极简版本
只需3步：获取数据 -> 定义策略 -> 运行回测
"""

import qka

# 第1步：定义策略
class SimpleStrategy(qka.Strategy):
    def on_bar(self, data, broker, current_date):
        for symbol, df in data.items():
            if len(df) < 20:  # 需要足够的历史数据
                continue
                
            current_price = df['close'].iloc[-1]
            ma20 = df['close'].rolling(20).mean().iloc[-1]
            
            # 简单策略：价格突破20日均线买入，跌破卖出
            if current_price > ma20 and broker.get_position(symbol) == 0:
                broker.buy(symbol, 0.5, current_price)  # 用50%资金买入
                
            elif current_price < ma20 and broker.get_position(symbol) > 0:
                broker.sell(symbol, 1.0, current_price)  # 全部卖出

# 第2步：获取数据并运行回测
if __name__ == "__main__":
    # 获取数据
    data_obj = qka.data(stocks=['000001', '000002'])  # 使用默认数据源
    
    # 运行回测
    result = qka.backtest(
        data=data_obj,
        strategy=SimpleStrategy(),
        start_time='2023-01-01',
        end_time='2023-12-31'
    )

    qka.plot(result)
    
    # 第3步：查看结果
    print(f"总收益率: {result['total_return']:.2%}")
    print(f"年化收益率: {result['annual_return']:.2%}")
    print(f"最大回撤: {result['max_drawdown']:.2%}")
    print(f"夏普比率: {result['sharpe_ratio']:.2f}")
