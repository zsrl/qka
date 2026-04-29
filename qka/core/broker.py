"""
QKA经纪商模块

提供虚拟交易经纪商功能，管理资金、持仓和交易记录，支持回测环境下的交易操作。
支持可配置的佣金、印花税和滑点模拟。
"""

import pandas as pd
from typing import Any
from qka.utils.logger import logger

# A 股默认费率
DEFAULT_COMMISSION_RATE = 0.00025   # 万2.5 佣金
DEFAULT_STAMP_DUTY_RATE = 0.0005    # 万5 印花税（仅卖出）
DEFAULT_SLIPPAGE = 0.001            # 0.1% 滑点
MIN_COMMISSION = 5.0                # 最低佣金 5 元


class Broker:
    """
    虚拟交易经纪商类

    管理资金、持仓和交易记录，提供买入卖出操作接口。
    支持佣金、印花税、滑点等真实交易成本模拟。

    Attributes:
        cash (float): 可用现金
        positions (Dict): 持仓记录
        trade_history (List): 交易历史记录
        commission_rate (float): 佣金费率
        stamp_duty_rate (float): 印花税费率（仅卖出）
        slippage (float): 滑点比率
        total_commission (float): 累计佣金
        total_stamp_duty (float): 累计印花税
        total_slippage_cost (float): 累计滑点成本
        trades (pd.DataFrame): 逐日状态记录
    """

    def __init__(self, initial_cash=100000.0,
                 commission_rate=DEFAULT_COMMISSION_RATE,
                 stamp_duty_rate=DEFAULT_STAMP_DUTY_RATE,
                 slippage=DEFAULT_SLIPPAGE):
        """
        初始化Broker

        Args:
            initial_cash (float): 初始资金，默认10万元
            commission_rate (float): 佣金费率，默认万2.5
            stamp_duty_rate (float): 印花税费率（仅卖出），默认万5
            slippage (float): 滑点比率，默认0.1%
        """
        self.cash = initial_cash
        self.positions = {}
        self.trade_history = []
        self.timestamp = None

        self.commission_rate = commission_rate
        self.stamp_duty_rate = stamp_duty_rate
        self.slippage = slippage

        self.total_commission = 0.0
        self.total_stamp_duty = 0.0
        self.total_slippage_cost = 0.0

        self.trades = pd.DataFrame(columns=[
            'cash', 'value', 'total', 'positions', 'trades'
        ])

    def on_bar(self, date, get):
        """
        Bar结束时记录当前状态。

        Args:
            date: 当前时间戳
            get: 获取因子数据的函数
        """
        self.timestamp = date
        total_value = self.cash
        position_summary = {}
        for symbol, pos in self.positions.items():
            price = get('close')
            if symbol in price.index:
                current_price = price[symbol]
                market_value = pos['size'] * current_price
                total_value += market_value
                position_summary[symbol] = {
                    'size': pos['size'],
                    'avg_price': pos['avg_price'],
                    'current_price': current_price,
                    'market_value': market_value,
                    'profit_pct': (current_price / pos['avg_price'] - 1) * 100 if pos['avg_price'] > 0 else 0,
                }

        self.trades.loc[self.timestamp] = {
            'cash': self.cash,
            'value': total_value - self.cash,
            'total': total_value,
            'positions': position_summary,
            'trades': list(self.trade_history),
        }

    def buy(self, symbol: str, price: float, size: int) -> bool:
        """
        买入操作

        考虑滑点（买入价上移）和佣金（最低 5 元）。

        Args:
            symbol (str): 交易标的代码
            price (float): 市价
            size (int): 买入数量

        Returns:
            bool: 交易是否成功
        """
        if size <= 0:
            logger.warning(f"买入数量必须大于 0！当前: {size}")
            return False

        if price <= 0:
            logger.warning(f"价格 {price:.2f} 不合法（前复权可能导致早期价格为负），跳过买入 {symbol}")
            return False

        exec_price = price * (1 + self.slippage)
        amount = exec_price * size
        if self.commission_rate > 0:
            commission = max(amount * self.commission_rate, MIN_COMMISSION)
        else:
            commission = 0.0
        total_cost = amount + commission

        if self.cash < total_cost:
            logger.debug(f"资金不足！需要 {total_cost:.2f}（佣金 {commission:.2f}），当前可用 {self.cash:.2f}")
            return False

        # 执行买入
        self.cash -= total_cost
        self.total_commission += commission
        self.total_slippage_cost += amount - price * size

        # 更新持仓（按实际成交价记录成本）
        if symbol in self.positions:
            old = self.positions[symbol]
            new_total = old['size'] * old['avg_price'] + amount
            new_size = old['size'] + size
            self.positions[symbol] = {'size': new_size, 'avg_price': new_total / new_size}
        else:
            self.positions[symbol] = {'size': size, 'avg_price': exec_price}

        self.trade_history.append({
            'action': 'buy', 'symbol': symbol,
            'price': price, 'exec_price': exec_price,
            'size': size, 'amount': amount,
            'commission': commission, 'total_cost': total_cost,
            'timestamp': self.timestamp,
        })

        logger.debug(f"买入成功: {symbol} {size}股 @ {exec_price:.2f}，花费 {total_cost:.2f}（佣金 {commission:.2f}）")
        return True

    def sell(self, symbol: str, price: float, size: int) -> bool:
        """
        卖出操作

        考虑滑点（卖出价下移）、佣金（最低 5 元）和印花税。

        Args:
            symbol (str): 交易标的代码
            price (float): 市价
            size (int): 卖出数量

        Returns:
            bool: 交易是否成功
        """
        if size <= 0:
            logger.warning(f"卖出数量必须大于 0！当前: {size}")
            return False

        if price <= 0:
            logger.warning(f"价格 {price:.2f} 不合法，跳过卖出 {symbol}")
            return False

        if symbol not in self.positions:
            logger.warning(f"没有 {symbol} 的持仓！")
            return False

        position = self.positions[symbol]
        if position['size'] < size:
            logger.warning(f"持仓不足！当前持有 {position['size']}，尝试卖出 {size}")
            return False

        exec_price = price * (1 - self.slippage)
        amount = exec_price * size
        if self.commission_rate > 0:
            commission = max(amount * self.commission_rate, MIN_COMMISSION)
        else:
            commission = 0.0
        stamp_duty = amount * self.stamp_duty_rate
        net_proceeds = amount - commission - stamp_duty

        # 执行卖出
        self.cash += net_proceeds
        self.total_commission += commission
        self.total_stamp_duty += stamp_duty
        self.total_slippage_cost += price * size - amount

        # 更新持仓
        if position['size'] == size:
            del self.positions[symbol]
        else:
            self.positions[symbol]['size'] -= size

        self.trade_history.append({
            'action': 'sell', 'symbol': symbol,
            'price': price, 'exec_price': exec_price,
            'size': size, 'amount': amount,
            'commission': commission, 'stamp_duty': stamp_duty,
            'net_proceeds': net_proceeds,
            'timestamp': self.timestamp,
        })

        logger.debug(f"卖出成功: {symbol} {size}股 @ {exec_price:.2f}，获得 {net_proceeds:.2f}（佣金 {commission:.2f} + 印花税 {stamp_duty:.2f}）")
        return True

    def get(self, factor: str, timestamp=None) -> Any:
        """
        从trades DataFrame中获取数据

        Args:
            factor (str): 列名，可选 'cash', 'value', 'total', 'positions', 'trades'
            timestamp: 时间戳，为None则使用当前时间戳

        Returns:
            Any: 对应列的数据，不存在则返回None
        """
        ts = timestamp if timestamp is not None else self.timestamp
        if ts is None or ts not in self.trades.index:
            return None
        if factor not in self.trades.columns:
            return None
        return self.trades.at[ts, factor]
