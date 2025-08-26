class Broker:
    def __init__(self, initial_cash=100000.0):
        """
        初始化Broker类
        
        Args:
            initial_cash (float): 初始资金，默认10万元
        """
        self.cash = initial_cash  # 可用现金
        self.positions = {}       # 持仓记录，格式: {symbol: {'size': 数量, 'avg_price': 平均成本}}
        self.trade_history = []   # 交易历史记录
        
    def buy(self, symbol, price, size):
        """
        买入操作
        
        Args:
            symbol (str): 交易标的代码
            price (float): 买入价格
            size (int): 买入数量
            
        Returns:
            bool: 交易是否成功
        """
        # 计算买入所需金额
        required_cash = price * size
        
        # 检查资金是否足够
        if self.cash < required_cash:
            print(f"资金不足！需要 {required_cash:.2f}，当前可用 {self.cash:.2f}")
            return False
        
        # 执行买入操作
        self.cash -= required_cash
        
        # 更新持仓
        if symbol in self.positions:
            # 已有持仓，计算新的平均成本
            old_position = self.positions[symbol]
            old_size = old_position['size']
            old_avg_price = old_position['avg_price']
            old_total_value = old_size * old_avg_price
            new_total_value = old_total_value + required_cash
            new_size = old_size + size
            new_avg_price = new_total_value / new_size
            
            self.positions[symbol] = {
                'size': new_size,
                'avg_price': new_avg_price
            }
        else:
            # 新建持仓
            self.positions[symbol] = {
                'size': size,
                'avg_price': price
            }
        
        # 记录交易历史
        self.trade_history.append({
            'action': 'buy',
            'symbol': symbol,
            'price': price,
            'size': size,
            'timestamp': self._get_current_time()
        })
        
        print(f"买入成功: {symbol} {size}股 @ {price:.2f}，花费 {required_cash:.2f}")
        return True
    
    def sell(self, symbol, price, size):
        """
        卖出操作
        
        Args:
            symbol (str): 交易标的代码
            price (float): 卖出价格
            size (int): 卖出数量
            
        Returns:
            bool: 交易是否成功
        """
        # 检查是否有足够的持仓
        if symbol not in self.positions:
            print(f"没有 {symbol} 的持仓！")
            return False
        
        position = self.positions[symbol]
        if position['size'] < size:
            print(f"持仓不足！当前持有 {position['size']}，尝试卖出 {size}")
            return False
        
        # 计算卖出所得金额
        sale_proceeds = price * size
        
        # 执行卖出操作
        self.cash += sale_proceeds
        
        # 更新持仓
        if position['size'] == size:
            # 全部卖出，删除持仓记录
            del self.positions[symbol]
        else:
            # 部分卖出，更新持仓数量
            self.positions[symbol]['size'] -= size
        
        # 记录交易历史
        self.trade_history.append({
            'action': 'sell',
            'symbol': symbol,
            'price': price,
            'size': size,
            'timestamp': self._get_current_time()
        })
        
        print(f"卖出成功: {symbol} {size}股 @ {price:.2f}，获得 {sale_proceeds:.2f}")
        return True
    
    def get_position(self, symbol):
        """
        获取指定标的的持仓信息
        
        Args:
            symbol (str): 标的代码
            
        Returns:
            dict or None: 持仓信息，如果没有持仓则返回None
        """
        return self.positions.get(symbol)
    
    def get_total_assets(self):
        """
        获取总资产（现金 + 持仓市值）
        
        Returns:
            float: 总资产价值
        """
        total_value = self.cash
        for symbol, position in self.positions.items():
            # 这里需要市场价格来计算持仓市值
            # 暂时使用平均成本作为市值估算
            total_value += position['size'] * position['avg_price']
        return total_value
    
    def _get_current_time(self):
        """
        获取当前时间（用于交易记录）
        
        Returns:
            str: 当前时间字符串
        """
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def __str__(self):
        """
        返回Broker状态的字符串表示
        """
        output = f"现金: {self.cash:.2f}\n"
        output += f"总资产: {self.get_total_assets():.2f}\n"
        output += "持仓:\n"
        for symbol, position in self.positions.items():
            output += f"  {symbol}: {position['size']}股 @ {position['avg_price']:.2f}\n"
        return output
