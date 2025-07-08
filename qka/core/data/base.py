"""
QKA数据模块基础功能

包含数据基类和统一数据接口
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import List, Dict, Tuple, Optional
from qka.utils.logger import logger

# ============================================================================
# 1. 数据基类
# ============================================================================

class DataBase(ABC):
    """数据基类，所有数据源都继承此类"""
    
    def __init__(
        self, 
        time_range: Tuple[str, str] = None,
        symbols: List[str] = None,
        period: str = '1d',
        factors: List[str] = None
    ):
        """
        初始化数据对象
        
        Args:
            time_range: 时间范围，格式为 ('开始时间', '结束时间')
            symbols: 股票代码列表
            period: 数据周期，如 '1m', '5m', '1d' 等
            factors: 数据因子列表，如 ['open', 'high', 'low', 'close', 'volume']
        """
        self.time_range = time_range
        self.symbols = symbols or []
        self.period = period
        self.factors = factors or ['open', 'high', 'low', 'close', 'volume']
        
    @abstractmethod
    def get(self, period: str = None, start_time: str = '', end_time: str = '') -> Dict[str, pd.DataFrame]:
        """获取历史数据"""
        pass
        
    def subscribe(self, callback):
        """订阅实时数据，默认不实现"""
        logger.warning(f"{self.__class__.__name__} 暂不支持实时数据订阅")
        raise NotImplementedError(f"{self.__class__.__name__} 暂不支持实时数据订阅")
    
    def normalize_data(self, data: Dict) -> Dict[str, pd.DataFrame]:
        """标准化数据格式为统一的DataFrame格式"""
        normalized = {}
        for symbol, df in data.items():
            if isinstance(df, pd.DataFrame):
                # 确保包含必要的列
                required_cols = ['open', 'high', 'low', 'close', 'volume']
                if all(col in df.columns for col in required_cols):
                    # 确保索引是datetime类型
                    if not isinstance(df.index, pd.DatetimeIndex):
                        if 'time' in df.columns:
                            df = df.set_index('time')
                        df.index = pd.to_datetime(df.index)
                    normalized[symbol] = df
                else:
                    logger.warning(f"股票 {symbol} 缺少必要的数据列")
        return normalized
    
    @property
    def stocks(self) -> List[str]:
        """获取股票列表"""
        return self.symbols

# ============================================================================
# 2. 统一数据接口
# ============================================================================

class Data(DataBase):
    """统一数据接口，通过source参数动态选择数据源"""
    
    def __init__(
        self, 
        time_range: Tuple[str, str] = None,
        symbols: List[str] = None,
        period: str = '1d',
        factors: List[str] = None,
        source: str = None
    ):
        """
        初始化数据对象
        
        Args:
            time_range: 时间范围，格式为 ('开始时间', '结束时间')
            symbols: 股票代码列表
            period: 数据周期，如 '1m', '5m', '1d' 等
            factors: 数据因子列表，如 ['open', 'high', 'low', 'close', 'volume']
            source: 数据源类型 ('qmt', 'akshare')，可选参数，如果不指定则使用全局默认数据源
        """
        super().__init__(time_range, symbols, period, factors)
        
        # 导入配置管理模块
        from .config import config
        
        # 如果没有指定source，使用全局默认数据源
        if source is None:
            source = config._source
            
        self.source_type = source
        
        # 动态创建数据源实例
        if source.lower() == 'akshare':
            try:
                from .akshare import AkshareData
                data_source_class = AkshareData
            except ImportError:
                raise ImportError("AkshareData 不可用，请检查 akshare 是否已安装")
        elif source.lower() == 'qmt':
            try:
                from .qmt import QMTData
                data_source_class = QMTData
            except ImportError:
                raise ImportError("QMTData 不可用，请检查 QMT 是否已安装")
        else:
            raise ValueError(f"不支持的数据源类型: {source}，支持的数据源: akshare, qmt")
        
        self.data_source = data_source_class(time_range, symbols, period, factors)
    
    def get(self, period: str = None, start_time: str = '', end_time: str = '') -> Dict[str, pd.DataFrame]:
        """获取历史数据"""
        # 如果没有指定period，使用初始化时的period
        if period is None:
            period = self.period
        
        # 如果没有指定时间范围，使用初始化时的time_range
        if not start_time and not end_time and self.time_range:
            start_time, end_time = self.time_range
            
        return self.data_source.get(period, start_time, end_time)
    
    def subscribe(self, callback):
        """订阅实时数据"""
        return self.data_source.subscribe(callback)
