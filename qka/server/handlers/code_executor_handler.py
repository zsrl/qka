"""
代码执行器消息处理器
处理execute_python类型的消息
"""

import traceback
import logging
from io import StringIO
import sys
from typing import Dict, Any

logger = logging.getLogger(__name__)

class CodeExecutor:
    """Python代码执行器类"""
    
    def __init__(self):
        """初始化代码执行器"""
        pass
    
    def execute_code(self, code: str) -> Dict[str, Any]:
        """
        执行Python代码并返回结果
        
        Args:
            code: 要执行的Python代码字符串
            
        Returns:
            包含执行结果的字典
        """
        # 重定向标准输出
        old_stdout = sys.stdout
        redirected_output = StringIO()
        sys.stdout = redirected_output
        
        try:
            # 执行代码
            exec(code)
            
            # 获取输出
            output = redirected_output.getvalue()
            
            return {
                "success": True,
                "output": output,
                "error": None,
                "traceback": None
            }
            
        except Exception as e:
            # 获取详细的错误信息
            error_traceback = traceback.format_exc()
            return {
                "success": False,
                "output": redirected_output.getvalue(),
                "error": str(e),
                "traceback": error_traceback
            }
        finally:
            # 恢复标准输出
            sys.stdout = old_stdout

# 创建全局执行器实例
_executor = CodeExecutor()

def execute_python_code(code: str) -> Dict[str, Any]:
    """
    执行Python代码的便捷函数
    
    Args:
        code: 要执行的Python代码字符串
        
    Returns:
        包含执行结果的字典
    """
    return _executor.execute_code(code)

def execute_python_handler(data: dict) -> dict:
    """执行Python代码的处理器"""
    code = data.get("code", "")
    logger.info(f"收到执行Python代码请求，代码长度: {len(code)}")
    
    result = execute_python_code(code)
    
    return {
        "type": "execute_result",
        "success": result["success"],
        "output": result["output"],
        "error": result.get("error"),
        "traceback": result.get("traceback")
    }