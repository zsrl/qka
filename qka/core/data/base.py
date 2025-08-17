"""
QKA数据模块基础功能

包含数据基类和统一数据接口
"""

import pandas as pd
from typing import List, Dict, Tuple, Optional
from abc import ABC, abstractmethod
from qka.utils.logger import logger
from qka.core.data.download import Downloader

class Data(ABC):
    """数据基类，所有数据源都继承此类"""
    
    def __init__(
        self, 
        symbols: Optional[List[str]] = None,
        period: str = '1d',
        adjust: str = 'qfq',
        factors: Optional[List[str]] = None,
        source: str = 'akshare',
        pool_size: int = 4
    ):
        """
        初始化数据对象
        
        Args:
            symbols: [维度1] 标的，如 ['000001.SZ', '600000.SH']
            period: [维度2] 周期，如 '1m', '5m', '1d' 等
            factors: [维度4] 因子，如 ['open', 'high', 'low', 'close', 'volume']
            source: [维度5] 数据来源 ('qmt', 'akshare')
            cache: 是否启用缓存
            pool_size: 并发池大小
        """
        self.symbols = symbols or []
        self.period = period
        self.adjust = adjust
        self.factors = factors or ['open', 'high', 'low', 'close', 'volume']
        self.source_type = self.__class__.__name__.replace('Data','').lower()
        self.source = source
        self.pool_size = pool_size

    def get(self) -> Dict[str, pd.DataFrame]:
        """获取历史数据"""
        d = Downloader(source=self.source)
        return d.download(symbols=self.symbols, period=self.period, adjust=self.adjust)
