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
        df, timestamps = self.data.get()

        for timestamp in timestamps:
            data = df[timestamp:timestamp].compute()

            self.strategy.on_bar(timestamp, data)