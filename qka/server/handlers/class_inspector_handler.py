"""
类检查器消息处理器
处理inspect_classes类型的消息
"""

import inspect
import yaml
import qka
import logging

logger = logging.getLogger(__name__)

def inspect_qka_classes() -> str:
    """
    提取qka模块中的所有类及其方法信息
    
    Returns:
        YAML格式的类信息字符串
    """
    result = {}
    
    # 遍历模块中的所有类
    for name, cls in inspect.getmembers(qka, inspect.isclass):
        # 过滤掉异常类（如PackageNotFoundError）
        if name.endswith('Error'):
            continue
            
        class_info = {
            "name": name,
            "doc": inspect.getdoc(cls) or "",
            "methods": {}
        }
        
        # 遍历类中的所有方法，过滤掉以单个下划线开头的内部方法
        for m_name, m in inspect.getmembers(cls, inspect.isfunction):
            # 保留__init__等特殊方法，过滤掉以单个下划线开头的内部方法
            if not m_name.startswith('_') or m_name.startswith('__'):
                method_info = {
                    "doc": inspect.getdoc(m) or "",
                    "args": str(inspect.signature(m))
                }
                class_info["methods"][m_name] = method_info
        
        result[name] = class_info
    
    # 返回YAML格式的字符串
    return yaml.dump(result, allow_unicode=True, default_flow_style=False)

def inspect_classes_handler(data: dict) -> dict:
    """检查类信息的处理器"""
    logger.info("收到检查类信息请求")
    
    try:
        result = inspect_qka_classes()
        
        return {
            "type": "inspect_result",
            "success": True,
            "classes_info": result
        }
        
    except Exception as e:
        logger.error(f"检查类信息时发生错误: {e}")
        return {
            "type": "inspect_result",
            "success": False,
            "error": str(e)
        }