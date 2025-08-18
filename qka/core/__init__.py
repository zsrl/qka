"""
QKA Core 模块
包含核心功能：数据处理、回测引擎、配置管理、事件系统等
"""


# 数据相关
from .data import Data
# 回测相关
from .backtest import backtest, Strategy, Broker
# 配置相关
from .config import config, load_config
# 事件系统
from .events import EventType, event_engine, emit_event, start_event_engine, stop_event_engine
# 绘图
from .plot import plot

__all__ = [
    # 数据相关
    'Data',
    # 回测相关
    'backtest', 'Strategy', 'Broker',
    # 配置
    'config', 'load_config',
    # 事件系统
    'EventType', 'event_engine', 'emit_event', 'start_event_engine', 'stop_event_engine',
    # 绘图
    'plot'
]
