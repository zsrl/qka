"""
QKA Core 模块
包含核心功能：数据处理、回测引擎、数据访问器、经纪商、仓位管理等
"""

# 数据与核心功能导入
try:
    from .simulate import Simulate
    from .data import Data
    from .accessor import DataAccessor
    from .backtest import Backtest
    from .strategy import Strategy
    from .broker import Broker
    from .sizing import SizingAccessor
except ImportError:
    pass

__all__ = [
    # 数据相关
    'Data', 'Simulate', 'DataAccessor',
    # 回测相关
    'Backtest', 'Strategy', 'Broker',
    # 仓位管理
    'SizingAccessor',
]
