"""
QKA回测引擎模块

提供基于时间序列的回测功能，支持多股票横截面数据处理
"""

import pandas as pd
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
        # 获取所有股票数据
        all_data = self.data.get()
        
        if not all_data:
            logger.error("没有获取到任何数据")
            return
        
        # 获取所有时间戳（基准时间序列）
        benchmark_timestamps = self._get_benchmark_timestamps(all_data)
        
        if not benchmark_timestamps:
            logger.error("无法获取基准时间戳")
            return
        
        # 初始化策略
        if hasattr(self.strategy, 'init'):
            self.strategy.init()
        
        # 按时间顺序迭代
        for timestamp in sorted(benchmark_timestamps):
            # 生成当前时间戳的横截面数据
            cross_section_data = self._create_cross_section_data(all_data, timestamp)
            
            if cross_section_data.empty:
                continue
                
            # 调用策略的onbar方法
            if hasattr(self.strategy, 'on_bar'):
                self.strategy.on_bar(timestamp, cross_section_data)

    def _get_benchmark_timestamps(self, all_data: Dict[str, pd.DataFrame]) -> List[datetime]:
        """
        获取基准时间戳序列
        
        使用所有股票数据的时间戳并集作为基准
        """
        all_timestamps = set()
        
        for symbol, df in all_data.items():
            if not df.empty:
                all_timestamps.update(df.index)
        
        return sorted(all_timestamps)

    def _create_cross_section_data(self, all_data: Dict[str, pd.DataFrame], timestamp: datetime) -> pd.DataFrame:
        """
        创建横截面数据
        
        Args:
            all_data: 所有股票数据
            timestamp: 当前时间戳
        
        Returns:
            pd.DataFrame: 横截面数据，行是股票，列是指标
        """
        cross_section = []
        
        for symbol, df in all_data.items():
            if timestamp in df.index:
                # 获取当前时间戳的数据
                row_data = df.loc[timestamp].copy()
                row_data['symbol'] = symbol
                cross_section.append(row_data)
        
        if cross_section:
            # 创建DataFrame，设置symbol为索引
            cross_section_df = pd.DataFrame(cross_section)
            cross_section_df.set_index('symbol', inplace=True)
            return cross_section_df
        else:
            return pd.DataFrame()