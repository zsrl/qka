"""
QKA回测引擎模块

提供基于时间序列的回测功能，支持多股票横截面数据处理
"""

import pandas as pd
import dask.dataframe as dd
from typing import Dict, List
from datetime import datetime
from qka.utils.logger import logger

class Backtest:
    """
    QKA回测引擎类
    
    提供基于时间序列的回测功能，支持多股票横截面数据处理
    """
    
    def __init__(self, data, strategy):
        """
        初始化回测引擎
        
        Args:
            data: Data类的实例，包含股票数据
            strategy: 策略对象，必须包含init和onbar方法
        """
        self.data = data
        self.strategy = strategy
    
    def run(self):
        """
        执行回测
        """
        # 获取所有股票数据（dask DataFrame）
        df = self.data.get()

        for date, row in df.iterrows():
            def get(factor):
                s = row[row.index.str.endswith(factor)]
                s.index = s.index.str.replace(f'_{factor}$', '', regex=True)
                return s
            
            # 先调用策略的on_bar（可能包含交易操作）
            self.strategy.on_bar(date, get)
            
            # 再调用broker的on_bar记录状态（包含交易后的状态）
            self.strategy.broker.on_bar(date, get)