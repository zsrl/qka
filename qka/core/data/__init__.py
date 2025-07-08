"""
QKA数据模块

提供统一的数据源接口，支持多种数据源：
- QMT: 专业量化交易数据源
- Akshare: 开源金融数据接口

使用方式：
    import qka
    
    # 设置默认数据源
    qka.set_source('qmt')
    
    # 创建数据对象
    data_obj = qka.Data(
        time_range=('2023-01-01', '2023-12-31'),
        symbols=['000001.SZ', '600000.SH'],
        period='1d',
        factors=['open', 'high', 'low', 'close', 'volume']
    )
    
    # 获取历史数据
    hist_data = data_obj.get('1d', '2024-01-01', '2024-12-31')
"""

# 从base模块导入所有公共接口
from .base import (
    set_source, 
    get_source, 
    Data,
    register_data_source,
    get_available_sources
)

# 公开的API - 这些是qka包级别要暴露的
__all__ = [
    'set_source', 
    'get_source', 
    'Data',
    'register_data_source',
    'get_available_sources'
]
