"""
QKA数据模块
"""

# 从base模块导入核心类
from .base import Data

# 从config模块导入配置对象
from .config import config

# 公开的API - 这些是qka包级别要暴露的
__all__ = [
    'Data',
    'config'
]