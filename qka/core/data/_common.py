"""
QKA数据模块

提供统一的数据获取、缓存和管理功能，支持多数据源、多周期、多因子的数据获取。
"""

import contextlib
import hashlib
import inspect
import io
import json
import os
import textwrap
import threading
from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import baostock as bs
import dask.dataframe as dd
from typing import List, Optional, Callable, Union
from qka.utils.logger import logger
from qka.core import indicator
from qka.core.simulate import Simulate
from qka.core import tdx

# qka 内置指标裸名集合，用于 dispatch 识别（无需 qka. 前缀）
_QKA_BUILTIN_NAMES = frozenset({
    'alpha', 'beta', 'sharpe', 'max_drawdown',
    'information_ratio', 'rolling_zigzag',
})


def _is_qka_factor(ind_type):
    """判断指标类型是否为 qka 内置指标（支持 qka. 前缀或裸名）。"""
    return (isinstance(ind_type, str) and
            (ind_type.startswith('qka.') or ind_type in _QKA_BUILTIN_NAMES))


def _callable_source(fn):
    """取可调用对象的源码文本，用于算配方指纹；取不到返回 None（表示不缓存）。"""
    try:
        return textwrap.dedent(inspect.getsource(fn))
    except (OSError, TypeError):
        return None


_RF_SIG_CACHE = {}


def _accepts_rf(fn) -> bool:
    """该指标是否接受 `rf` 参数（α / 夏普接受，其余不接受）。

    签名解析只做一次并缓存 —— 否则每只票每个因子都要解析一遍，几千次纯浪费。
    """
    key = (getattr(fn, '__module__', ''), getattr(fn, '__name__', ''), id(fn))
    hit = _RF_SIG_CACHE.get(key)
    if hit is None:
        try:
            hit = 'rf' in inspect.signature(fn).parameters
        except (TypeError, ValueError):
            hit = False
        _RF_SIG_CACHE[key] = hit
    return hit


def _rf_given_positionally(fn, args) -> bool:
    """因子定义里是否已经按位置把 rf 填掉了，如 `('qka.alpha', 250, 0.02)`。

    这种写法要继续有效，并且**优先于** Data 的全局 risk_free ——
    否则两边一起给会报 `got multiple values for argument 'rf'`。
    """
    try:
        sig = inspect.signature(fn)
        # 前两个位置参数固定是 df / symbol
        bound = sig.bind_partial(object(), object(), *args)
    except (TypeError, ValueError):
        return False
    return 'rf' in bound.arguments


# ── TickFlow 凭据（进程级，设一次即可）──────────────────────────
# 放在模块级而不是 `Data` 参数里：「用哪个凭据」是部署级配置，不该每构造一次
# Data 就传一遍。优先级：set_tickflow_api_key() > 环境变量 > 免费档。
_TICKFLOW_API_KEY: Optional[str] = None


def set_tickflow_api_key(api_key: Optional[str]) -> None:
    """设置 TickFlow API key（进程级，设一次即可）。

    设了之后所有 `Data(source='tickflow')` 都走完整服务
    （https://api.tickflow.org）；不设则走免费档
    （https://free-api.tickflow.org），与既有行为完全一致。

    优先级：本函数设的值 > 环境变量 ``TICKFLOW_API_KEY`` > 免费档。

    Args:
        api_key: 密钥；传 None 或空串表示清除，回到免费档。

    Examples:
        >>> from qka import Data, set_tickflow_api_key
        >>> set_tickflow_api_key('tk_xxx')
        >>> Data(symbols=['600519.SH']).get()      # 已走完整服务
    """
    global _TICKFLOW_API_KEY
    _TICKFLOW_API_KEY = api_key or None
    # 已经建好的客户端按旧 key 建的，作废掉 —— 否则「先建了免费档客户端、
    # 后设 key」这条时间线会静默继续走免费档，既看不出来又难查。
    from .base import Data as _D
    _D._reset_tickflow_clients()


def get_tickflow_api_key() -> Optional[str]:
    """当前生效的 TickFlow key：函数设的优先，其次环境变量，都没有则 None。"""
    return _TICKFLOW_API_KEY or os.environ.get('TICKFLOW_API_KEY') or None


def _key_fingerprint(api_key: Optional[str]) -> str:
    """key 的短摘要，用作客户端缓存的键。

    不拿明文 key 当字典键 —— 免得它出现在内存转储或日志里。
    """
    if not api_key:
        return ''
    return hashlib.sha1(api_key.encode('utf-8')).hexdigest()[:12]


