"""
数据源映射配置

这个文件定义了所有可用的数据源及其对应的类。
当添加新的数据源时，只需要：
1. 创建新的数据源文件（继承DataSource）
2. 在这里添加映射关系
"""

from .qmt import QMTData
from .akshare import AkshareData

# 数据源映射字典
DATA_SOURCE_MAPPING = {
    'qmt': QMTData,
    'akshare': AkshareData,
}

def get_available_sources():
    """获取所有可用的数据源名称"""
    return list(DATA_SOURCE_MAPPING.keys())

def register_data_source(name: str, data_source_class):
    """
    注册新的数据源
    
    Args:
        name: 数据源名称
        data_source_class: 数据源类（必须继承DataSource）
    """
    from .base import DataSource
    
    if not issubclass(data_source_class, DataSource):
        raise TypeError(f"数据源类 {data_source_class} 必须继承 DataSource")
    
    DATA_SOURCE_MAPPING[name.lower()] = data_source_class
    print(f"已注册数据源: {name}")

# 导出
__all__ = ['DATA_SOURCE_MAPPING', 'get_available_sources', 'register_data_source']
