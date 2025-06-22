"""
QKA - 量化交易框架

统一的访问接口，支持 qka.xxx 的访问模式
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("qka")
except PackageNotFoundError:
    __version__ = "0.1.0"  # fallback version

# 核心功能直接导入
from qka.core.data import data, set_source, get_source, register_data_source, get_available_sources
from qka.core.backtest import backtest, Strategy, Broker
from qka.core.config import config, load_config
from qka.core.events import event_engine, emit_event
from qka.core.plot import plot

# 子模块导入
from qka import core, utils, mcp

# 交易相关（有依赖的模块暂时不导入，避免导入错误）
# from qka.brokers.trade import create_trader
# from qka.brokers.client import QMTClient
# from qka.brokers.server import QMTServer

__all__ = [
    # 核心功能
    'data', 'backtest', 'Strategy', 'Broker', 'plot',
    # 配置
    'config', 'load_config',
    # 数据源管理
    'set_source', 'get_source', 'register_data_source', 'get_available_sources',
    # 事件系统
    'event_engine', 'emit_event',
    # 子模块
    'core', 'utils', 'mcp'
]