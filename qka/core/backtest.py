
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
import warnings
warnings.filterwarnings('ignore')

from qka.core.data.base import Data

class Strategy(ABC):
    """策略基类"""
    
    def __init__(self):
        self.name = self.__class__.__name__
    
    @abstractmethod
    def on_bar(self, data: Dict[str, pd.DataFrame], broker, current_date: datetime):
        """
        每个交易日调用的策略逻辑
        
        Args:
            data: 历史数据 {股票代码: DataFrame}
            broker: 交易接口
            current_date: 当前日期
        """
        pass
    
    def on_start(self, broker):
        """回测开始时调用"""
        pass
    
    def on_end(self, broker):
        """回测结束时调用"""
        pass

class Broker:
    """简化的交易接口"""
    
    def __init__(self, initial_cash: float = 1000000, commission_rate: float = 0.0003):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.commission_rate = commission_rate
        self.positions = {}  # {股票代码: 数量}
        self.avg_costs = {}  # {股票代码: 平均成本}
        self.trades = []     # 交易记录
        self.daily_values = []  # 每日净值
        
    def buy(self, symbol: str, amount: float, price: Optional[float] = None) -> bool:
        """
        买入股票
        
        Args:
            symbol: 股票代码
            amount: 金额或数量，如果 < 1 则视为金额比例，否则视为股数
            price: 价格，为None时使用当前价格
        """
        if amount <= 0:
            return False
            
        if amount < 1:  # 按比例买入
            buy_amount = self.cash * amount
            shares = int(buy_amount / price / 100) * 100  # 按手买入
        else:  # 按股数买入
            shares = int(amount / 100) * 100  # 按手买入
            buy_amount = shares * price
            
        commission = buy_amount * self.commission_rate
        total_cost = buy_amount + commission
        
        if self.cash >= total_cost and shares >= 100:
            # 更新持仓
            old_shares = self.positions.get(symbol, 0)
            old_cost = self.avg_costs.get(symbol, 0.0)
            
            new_shares = old_shares + shares
            new_avg_cost = ((old_shares * old_cost) + buy_amount) / new_shares
            
            self.positions[symbol] = new_shares
            self.avg_costs[symbol] = new_avg_cost
            self.cash -= total_cost
              # 记录交易
            self.trades.append({
                'date': getattr(self, 'current_date', datetime.now()),
                'symbol': symbol,
                'action': 'buy',
                'shares': shares,
                'price': price,
                'amount': buy_amount,
                'commission': commission
            })
            
            return True
        return False
    
    def sell(self, symbol: str, amount: float = 1.0, price: Optional[float] = None) -> bool:
        """
        卖出股票
        
        Args:
            symbol: 股票代码  
            amount: 比例或数量，如果 <= 1 则视为比例，否则视为股数
            price: 价格，为None时使用当前价格
        """
        current_shares = self.positions.get(symbol, 0)
        if current_shares == 0:
            return False
            
        if amount <= 1:  # 按比例卖出
            sell_shares = int(current_shares * amount)
        else:  # 按股数卖出
            sell_shares = min(int(amount / 100) * 100, current_shares)
            
        if sell_shares <= 0:
            return False
            
        sell_amount = sell_shares * price
        commission = sell_amount * self.commission_rate
        net_proceeds = sell_amount - commission
        
        # 更新持仓
        self.positions[symbol] = current_shares - sell_shares
        if self.positions[symbol] == 0:
            del self.positions[symbol]
            if symbol in self.avg_costs:
                del self.avg_costs[symbol]
                
        self.cash += net_proceeds
          # 记录交易
        self.trades.append({
            'date': getattr(self, 'current_date', datetime.now()),
            'symbol': symbol,
            'action': 'sell',
            'shares': sell_shares,
            'price': price,
            'amount': sell_amount,
            'commission': commission
        })
        
        return True
    
    def get_position(self, symbol: str) -> int:
        """获取持仓数量"""
        return self.positions.get(symbol, 0)
    
    def get_cash(self) -> float:
        """获取可用现金"""
        return self.cash
    
    def get_total_value(self, prices: Dict[str, float]) -> float:
        """计算总资产"""
        stock_value = sum(shares * prices.get(symbol, 0) 
                         for symbol, shares in self.positions.items())
        return self.cash + stock_value
    
    def get_positions(self) -> Dict[str, int]:
        """获取所有持仓"""
        return self.positions.copy()

def backtest(data: Data, strategy: Strategy, broker: Optional[Broker] = None, 
             start_time: str = '', end_time: str = '') -> Dict[str, Any]:
    """
    简化的回测函数
    
    Args:
        data: 数据对象
        strategy: 策略对象
        broker: 交易接口，为None时使用默认设置
        start_time: 开始时间 'YYYY-MM-DD'
        end_time: 结束时间 'YYYY-MM-DD'
    
    Returns:
        回测结果字典
    """
    # 获取历史数据
    historical_data = data.get(period='1d', start_time=start_time, end_time=end_time)
    
    if not historical_data:
        raise ValueError("未获取到有效数据")
    
    # 初始化broker
    if broker is None:
        broker = Broker()
    
    # 获取所有交易日期
    all_dates = set()
    for symbol, df in historical_data.items():
        if isinstance(df, pd.DataFrame) and not df.empty:
            dates = df.index
            if start_time:
                start_dt = pd.to_datetime(start_time)
                dates = dates[dates >= start_dt]
            if end_time:
                end_dt = pd.to_datetime(end_time)
                dates = dates[dates <= end_dt]
            all_dates.update(dates)
    
    trading_days = sorted(list(all_dates))
    
    if not trading_days:
        raise ValueError("没有找到有效的交易日期")
    
    # 策略初始化
    strategy.on_start(broker)
    
    # 逐日回测
    for current_date in trading_days:
        broker.current_date = current_date
        
        # 准备当日数据（截止到当前日期的历史数据）
        current_data = {}
        current_prices = {}
        
        for symbol, df in historical_data.items():
            if current_date in df.index:
                # 获取截止到当前日期的所有历史数据
                historical_slice = df.loc[:current_date].copy()
                current_data[symbol] = historical_slice
                current_prices[symbol] = df.loc[current_date, 'close']
        
        # 执行策略
        if current_data:
            try:
                strategy.on_bar(current_data, broker, current_date)
            except Exception as e:
                print(f"策略执行错误 {current_date}: {e}")
                continue
        
        # 记录当日资产状况
        total_value = broker.get_total_value(current_prices)
        broker.daily_values.append({
            'date': current_date,
            'cash': broker.cash,
            'total_value': total_value,
            'positions': broker.get_positions().copy(),
            'prices': current_prices.copy()
        })
    
    # 策略结束
    strategy.on_end(broker)
    
    # 计算回测结果
    return _calculate_performance(broker)

def _calculate_performance(broker: Broker) -> Dict[str, Any]:
    """计算回测绩效指标"""
    
    if not broker.daily_values:
        return {
            'error': '没有有效的回测数据'
        }
    
    # 提取数据
    dates = [record['date'] for record in broker.daily_values]
    values = [record['total_value'] for record in broker.daily_values]
    
    # 基本统计
    initial_value = broker.initial_cash
    final_value = values[-1] if values else initial_value
    total_return = (final_value - initial_value) / initial_value
    
    # 计算年化收益率
    days = len(values)
    if days > 0:
        annual_return = (final_value / initial_value) ** (252 / days) - 1
    else:
        annual_return = 0
    
    # 计算波动率和夏普比率
    returns = pd.Series(values).pct_change().dropna()
    if len(returns) > 1:
        volatility = returns.std() * np.sqrt(252)
        sharpe_ratio = annual_return / volatility if volatility > 0 else 0
    else:
        volatility = 0
        sharpe_ratio = 0
    
    # 计算最大回撤
    peak = pd.Series(values).expanding().max()
    drawdown = (pd.Series(values) - peak) / peak
    max_drawdown = drawdown.min()
      # 交易统计
    trades = broker.trades
    total_trades = len(trades)
    total_commission = sum(trade['commission'] for trade in trades)
    
    # 简化的胜率计算
    profitable_trades = 0
    buy_trades = [t for t in trades if t['action'] == 'buy']
    sell_trades = [t for t in trades if t['action'] == 'sell']
    
    if total_trades > 0 and sell_trades:
        for sell_trade in sell_trades:
            symbol = sell_trade['symbol']
            sell_date = sell_trade['date']
            
            # 查找最近的买入记录
            recent_buy = None
            for buy_trade in reversed(buy_trades):
                if (buy_trade['symbol'] == symbol and 
                    buy_trade['date'] <= sell_date):
                    recent_buy = buy_trade
                    break
            
            if recent_buy:
                profit = (sell_trade['price'] - recent_buy['price']) * sell_trade['shares']
                profit -= (sell_trade['commission'] + recent_buy['commission'])
                if profit > 0:
                    profitable_trades += 1
    
    win_rate = profitable_trades / len(sell_trades) if sell_trades else 0
    
    return {
        'initial_capital': initial_value,
        'final_value': final_value,
        'total_return': total_return,
        'annual_return': annual_return,
        'volatility': volatility,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'total_trades': total_trades,
        'total_commission': total_commission,
        'win_rate': win_rate,
        'trading_days': days,
        'daily_values': broker.daily_values,
        'trades': trades,
        'positions': broker.get_positions()
    }