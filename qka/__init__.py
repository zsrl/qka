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
from qka.core.data import Data
from qka.core.accessor import DataAccessor
from qka.core.backtest import Backtest
from qka.core.strategy import Strategy
from qka.core.broker import Broker
from qka.core.sizing import SizingAccessor

# 子模块导入
from qka import core, utils

__all__ = [
    # 核心功能
    'Data', 'Backtest', 'Strategy', 'Broker', 'DataAccessor', 'SizingAccessor',
    # 子模块
    'core', 'utils'
]