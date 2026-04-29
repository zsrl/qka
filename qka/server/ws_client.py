"""
简单的WebSocket客户端
连接地址：ws://www.quantai.chat/ws?clientId=test-client-123
支持执行Python代码并返回结果
"""

import asyncio
import json
import logging
import threading
import time
from typing import Optional, Callable

import websockets
from qka.server.handlers.code_executor_handler import execute_python_handler

logger = logging.getLogger(__name__)

# URL = "wss://quantai.chat/ws?clientId=test-client-123"
URL = "ws://localhost:3000/ws?clientId=test-client-123"

class WebSocketClient:
    """简单的WebSocket客户端"""
    
    def __init__(self, uri: str = URL):
        """
        初始化WebSocket客户端
        
        Args:
            uri: WebSocket服务器地址
        """
        self.uri = uri
        self.websocket = None
        self.running = False
        self.client_thread = None
        self.message_handler: Optional[Callable] = None
        self.loop = None
    
    def set_message_handler(self, handler: Callable):
        """
        设置消息处理器
        
        Args:
            handler: 处理函数，接收消息字符串参数
        """
        self.message_handler = handler
    
    async def _connect(self):
        """连接WebSocket服务器"""
        try:
            self.websocket = await websockets.connect(self.uri)
            logger.info(f"已连接到 {self.uri}")
            return True
        except Exception as e:
            logger.error(f"连接失败: {e}")
            return False
    
    async def _receive_messages(self):
        """接收消息循环"""
        if not self.websocket:
            return
        
        try:
            async for message in self.websocket:
                if self.message_handler:
                    try:
                        self.message_handler(message)
                    except Exception as e:
                        logger.error(f"处理消息时出错: {e}")
                else:
                    # 默认处理：打印消息
                    logger.info(f"收到消息: {message}")
        except websockets.exceptions.ConnectionClosed:
            logger.info("连接已关闭")
        except Exception as e:
            logger.error(f"接收消息时出错: {e}")
    
    async def _client_loop(self):
        """客户端主循环"""
        if not await self._connect():
            return
        
        # 启动消息接收任务
        receive_task = asyncio.create_task(self._receive_messages())
        
        try:
            # 保持连接
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            receive_task.cancel()
            if self.websocket:
                await self.websocket.close()
    
    def _run_client(self):
        """在新的事件循环中运行客户端"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._client_loop())
    
    def start(self):
        """启动客户端"""
        if self.running:
            logger.warning("客户端已经在运行")
            return
        
        self.running = True
        self.client_thread = threading.Thread(target=self._run_client, daemon=True)
        self.client_thread.start()
        
        # 等待连接建立
        time.sleep(1)
        logger.info("WebSocket客户端启动成功")
    
    def stop(self):
        """停止客户端"""
        if not self.running:
            return
        
        self.running = False
        logger.info("正在停止WebSocket客户端...")
        
        if self.client_thread and self.client_thread.is_alive():
            self.client_thread.join(timeout=5.0)
        
        logger.info("WebSocket客户端已停止")
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        # 简单检查：websocket存在且running为True
        return self.websocket is not None and self.running
    
    async def send_message_async(self, message: str):
        """
        异步发送消息
        
        Args:
            message: 消息内容
            
        Returns:
            bool: 发送是否成功
        """
        if not self.is_connected() or not self.websocket:
            logger.warning("未连接，无法发送消息")
            return False
        
        try:
            await self.websocket.send(message)
            return True
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False
    
    def send_message(self, message: str) -> bool:
        """
        同步发送消息
        
        Args:
            message: 消息内容
            
        Returns:
            bool: 发送是否成功
        """
        if not self.loop or not self.loop.is_running():
            logger.error("事件循环未运行")
            return False
        
        try:
            asyncio.run_coroutine_threadsafe(
                self.send_message_async(message),
                self.loop
            )
            return True
        except Exception as e:
            logger.error(f"同步发送消息失败: {e}")
            return False
    
    def send_json(self, data: dict) -> bool:
        """
        发送JSON消息
        
        Args:
            data: 字典数据
            
        Returns:
            bool: 发送是否成功
        """
        try:
            message = json.dumps(data, ensure_ascii=False)
            return self.send_message(message)
        except Exception as e:
            logger.error(f"JSON编码失败: {e}")
            return False


def main():
    """命令行入口点：启动WebSocket客户端"""
    import argparse
    
    parser = argparse.ArgumentParser(description="启动WebSocket客户端")
    # parser.add_argument("--uri", default="wss://quantai.chat/ws?clientId=test-client-123",
    #                    help="WebSocket服务器地址 (默认: wss://quantai.chat/ws?clientId=test-client-123)")
    parser.add_argument("--verbose", action="store_true", help="显示详细日志")
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 创建客户端
    client = WebSocketClient()
    
    def handle_message(message: str):
        """处理收到的WebSocket消息"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "execute_code":
                # 处理代码执行请求
                request_id = data.get("requestId")
                code = data.get("code", "")
                
                logger.info(f"收到代码执行请求，requestId: {request_id}, 代码长度: {len(code)}")
                
                # 使用handlers中的代码执行器
                handler_data = {"code": code}
                result = execute_python_handler(handler_data)
                
                # 构建响应消息，直接返回execute_python_handler的结果
                response = {
                    "type": "code_execution_result",
                    "requestId": request_id,
                    "timestamp": int(time.time() * 1000),
                    **result  # 直接将执行结果的所有字段都包含进来
                }
                
                # 发送响应
                client.send_json(response)
                logger.info(f"已发送代码执行结果，requestId: {request_id}")
                
            else:
                # 其他类型的消息，打印日志
                logger.info(f"收到消息类型: {message_type}, 数据: {data}")
                
        except json.JSONDecodeError:
            logger.warning(f"收到非JSON消息: {message}")
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
    
    client.set_message_handler(handle_message)
    
    print("客户端已启动，等待代码执行请求...")
    print("按 Ctrl+C 停止客户端")
    
    # 启动客户端
    client.start()
    
    try:
        # 保持运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止客户端...")
    finally:
        client.stop()
        print("客户端已停止")


if __name__ == "__main__":
    main()