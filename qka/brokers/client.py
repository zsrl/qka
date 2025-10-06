"""
QKA交易客户端模块

提供QMT交易服务器的客户端接口，支持远程调用交易功能。
"""

import requests
from typing import Any, Dict, Optional
from qka.utils.logger import logger

class QMTClient:
    """
    QMT交易客户端类
    
    提供与QMT交易服务器的通信接口，支持各种交易操作。
    
    Attributes:
        base_url (str): API服务器地址
        session (requests.Session): HTTP会话对象
        token (str): 访问令牌
        headers (Dict): HTTP请求头
    """
    
    def __init__(self, base_url: str = "http://localhost:8000", token: Optional[str] = None):
        """
        初始化交易客户端
        
        Args:
            base_url (str): API服务器地址，默认为本地8000端口
            token (str): 访问令牌，必须与服务器的token一致
            
        Raises:
            ValueError: 如果未提供token
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        if not token:
            raise ValueError("必须提供访问令牌(token)")
        self.token = token
        self.headers = {"X-Token": self.token}

    def api(self, method_name: str, **params) -> Any:
        """
        通用调用接口方法
        
        Args:
            method_name (str): 要调用的接口名称
            **params: 接口参数，作为关键字参数传入
            
        Returns:
            Any: 接口返回的数据
            
        Raises:
            Exception: API调用失败时抛出异常
        """
        try:
            response = self.session.post(
                f"{self.base_url}/api/{method_name}",
                json=params or {},
                headers=self.headers
            )
            response.raise_for_status()
            result = response.json()
            
            if not result.get('success'):
                raise Exception(f"API调用失败: {result.get('detail')}")
            
            return result.get('data')
        except Exception as e:
            logger.error(f"调用 {method_name} 失败: {str(e)}")
            raise

