"""
QKA Core 模块
包含核心功能：数据处理、回测引擎、配置管理、事件系统等
"""

from .data import data
from .backtest import backtest, Strategy
from .config import config, load_config
from .events import EventType, event_engine, emit_event, start_event_engine, stop_event_engine
from .plot import plot

__all__ = [
    'data', 'backtest', 'Strategy',
    'config', 'load_config',
    'EventType', 'event_engine', 'emit_event', 'start_event_engine', 'stop_event_engine',
    'plot'
]
