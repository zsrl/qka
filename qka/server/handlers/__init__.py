"""
消息处理器模块
包含所有ZeroMQ消息类型的处理器
"""

from .code_executor_handler import execute_python_handler
from .class_inspector_handler import inspect_classes_handler

# 消息类型到处理器的映射
MESSAGE_HANDLERS = {
    "execute_python": execute_python_handler,
    "inspect_classes": inspect_classes_handler
}

# 导出所有处理器和映射
__all__ = [
    'execute_python_handler',
    'inspect_classes_handler',
    'MESSAGE_HANDLERS'
]