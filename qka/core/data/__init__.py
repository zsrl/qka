"""qka 数据模块（2026-11-13 按职责拆分，对外接口保持不变）。

原来是一个 2702 行的 data.py，取数 / 缓存 / 因子 / 三个数据源 / 模拟数据
全混在一个类里。现在按职责分到 base + cache + factors + sources/*，
`from qka.core.data import Data` 这类 import 一行都不用改。

注意：data.py 文件已删除，本包取代它 —— Python 的 import 路径完全一致。
"""
from ._common import (get_tickflow_api_key, set_tickflow_api_key)
from .base import Data

__all__ = ['Data', 'set_tickflow_api_key', 'get_tickflow_api_key']
