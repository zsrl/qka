"""
QKA数据模块基础功能

包含数据源管理、配置、工厂函数等核心功能
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import List, Dict
from qka.utils.logger import logger

# ============================================================================
# 1. 全局配置
# ============================================================================

# 全局默认数据源配置
_DEFAULT_DATA_SOURCE = 'akshare'

def set_source(source: str) -> None:
    """
    设置全局默认数据源
    
    Args:
        source: 数据源类型 ('qmt', 'akshare')
    
    Examples:
        import qka
        
        # 设置默认使用QMT数据源
        qka.set_source('qmt')
        
        # 之后创建数据对象就不需要指定source了
        data_obj = qka.data(stocks=['000001.SZ', '600000.SH'])
    """
    global _DEFAULT_DATA_SOURCE
    
    if source.lower() not in DATA_SOURCE_MAPPING:
        available_sources = ', '.join(DATA_SOURCE_MAPPING.keys())
        raise ValueError(f"不支持的数据源类型: {source}，支持的数据源: {available_sources}")
    
    _DEFAULT_DATA_SOURCE = source.lower()
    logger.info(f"已设置默认数据源为: {source}")

def get_source() -> str:
    """
    获取当前默认数据源
    
    Returns:
        当前默认数据源名称
    """
    return _DEFAULT_DATA_SOURCE

# ============================================================================
# 2. 数据源注册机制
# ============================================================================

# 数据源映射字典（稍后会被初始化）
DATA_SOURCE_MAPPING = {}

def get_available_sources():
    """获取所有可用的数据源名称"""
    return list(DATA_SOURCE_MAPPING.keys())

def register_data_source(name: str, data_source_class):
    """
    注册新的数据源
    
    Args:
        name: 数据源名称
        data_source_class: 数据源类（必须继承DataSource）
    
    Examples:
        # 注册新的数据源
        register_data_source('tushare', TushareData)
    """
    if not issubclass(data_source_class, DataSource):
        raise TypeError(f"数据源类 {data_source_class} 必须继承 DataSource")
    
    DATA_SOURCE_MAPPING[name.lower()] = data_source_class
    logger.info(f"已注册数据源: {name}")

# ============================================================================
# 3. 基础抽象类
# ============================================================================

class DataSource(ABC):
    """数据源基类"""
    
    def __init__(self, stocks: List[str] = None, sector: str = None):
        self.stocks = stocks or []
        self.sector = sector
        
    @abstractmethod
    def get_historical_data(self, period: str = '1d', start_time: str = '', end_time: str = '') -> Dict[str, pd.DataFrame]:
        """获取历史数据"""
        pass
        
    @abstractmethod
    def subscribe_realtime(self, callback):
        """订阅实时数据"""
        pass
    
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

# ============================================================================
# 4. 统一数据接口
# ============================================================================

class Data:
    """统一数据接口"""
    
    def __init__(self, source: str = 'akshare', stocks: List[str] = None, sector: str = None):
        """
        初始化数据对象
        
        Args:
            source: 数据源类型 ('qmt', 'akshare')
            stocks: 股票代码列表
            sector: 板块名称
        """
        self.source_type = source
        
        if source.lower() not in DATA_SOURCE_MAPPING:
            available_sources = ', '.join(DATA_SOURCE_MAPPING.keys())
            raise ValueError(f"不支持的数据源类型: {source}，支持的数据源: {available_sources}")
        
        # 动态创建数据源实例
        data_source_class = DATA_SOURCE_MAPPING[source.lower()]
        self.data_source = data_source_class(stocks, sector)
    
    def get(self, period: str = '1d', start_time: str = '', end_time: str = '') -> Dict[str, pd.DataFrame]:
        """获取历史数据"""
        return self.data_source.get_historical_data(period, start_time, end_time)
    
    def subscribe(self, callback):
        """订阅实时数据"""
        return self.data_source.subscribe_realtime(callback)
    
    @property
    def stocks(self) -> List[str]:
        """获取股票列表"""
        return self.data_source.stocks

# ============================================================================
# 5. 工厂函数
# ============================================================================

def data(stocks=None, sector=None, source=None):
    """
    创建数据对象的工厂函数
    
    Args:
        stocks: 股票代码列表
        sector: 板块名称
        source: 数据源类型 ('qmt', 'akshare')，可选参数，如果不指定则使用全局默认数据源
    
    Returns:
        Data对象
        
    Examples:
        import qka
        
        # 设置默认数据源
        qka.set_source('qmt')
        
        # 使用默认数据源创建数据对象
        data_obj = qka.data(stocks=['000001.SZ', '600000.SH'])
        
        # 临时指定其他数据源
        data_ak = qka.data(stocks=['000001', '600000'], source='akshare')
        
        # 获取板块数据
        data_sector = qka.data(sector='沪深A股')
        
        # 获取历史数据
        hist_data = data_obj.get('1d', '2024-01-01', '2024-12-31')
    """
    # 如果没有指定source，使用全局默认数据源
    if source is None:
        source = _DEFAULT_DATA_SOURCE
    
    return Data(source, stocks, sector)

# ============================================================================
# 6. 初始化数据源映射
# ============================================================================

def _initialize_data_sources():
    """初始化内置数据源"""
    try:
        from .qmt import QMTData
        register_data_source('qmt', QMTData)
    except ImportError:
        pass  # QMT可能未安装
    
    try:
        from .akshare import AkshareData
        register_data_source('akshare', AkshareData)
    except ImportError:
        pass  # Akshare可能未安装

# 自动初始化内置数据源
_initialize_data_sources()
