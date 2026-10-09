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
from qka.core.simulate import Simulate
from qka.core.data import Data
from qka.core.accessor import DataAccessor
from qka.core.backtest import Backtest
from qka.core.strategy import Strategy
from qka.core.broker import Broker
from qka.core.sizing import SizingAccessor
from qka.core.analysis import Analysis, Segment, AlphaBeta
# 通达信数据源：安装目录的设置与查询（source='tdx' 时使用）
from qka.core.tdx import set_tdx_root, get_tdx_root_info

# 子模块导入
from qka import core, utils

__all__ = [
    # 核心功能
    'Data', 'Simulate', 'Backtest', 'Strategy', 'Broker', 'DataAccessor', 'SizingAccessor',
    # 分析
    'Analysis', 'Segment', 'AlphaBeta',
    # 通达信数据源
    'set_tdx_root', 'get_tdx_root_info',
    # 子模块
    'core', 'utils'
]