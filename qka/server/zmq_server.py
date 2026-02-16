"""
ZeroMQ服务器模块
提供REQ-REP模式的ZeroMQ服务器，用于接收和回复消息
使用handler映射系统，支持动态扩展消息类型
"""

import zmq
import threading
import logging
import json
from qka.server.handlers import MESSAGE_HANDLERS

logger = logging.getLogger(__name__)


class ZeroMQServer:
    """ZeroMQ服务器类，实现REQ-REP模式的消息处理"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 5555):
        """
        初始化ZeroMQ服务器
        
        Args:
            host: 服务器绑定的主机地址
            port: 服务器绑定的端口号
        """
        self.host = host
        self.port = port
        self.context = None
        self.socket = None
        self.running = False
        self.server_thread = None
    
    
    def _process_message(self, message: str) -> str:
        """处理接收到的消息"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if not message_type:
                return json.dumps({"type": "error", "error": "消息类型缺失"}, ensure_ascii=False)
            
            handler = MESSAGE_HANDLERS.get(message_type)
            if not handler:
                return json.dumps({"type": "error", "error": f"未知的消息类型: {message_type}"}, ensure_ascii=False)
            
            # 调用处理器
            response = handler(data)
            return json.dumps(response, ensure_ascii=False)
            
        except json.JSONDecodeError:
            return json.dumps({"type": "error", "error": "消息格式错误"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"type": "error", "error": f"处理消息时发生错误: {str(e)}"}, ensure_ascii=False)
    
    def _server_loop(self):
        """服务器主循环"""
        try:
            # 创建ZeroMQ上下文和socket
            self.context = zmq.Context()
            self.socket = self.context.socket(zmq.REP)
            
            # 绑定到指定地址
            address = f"tcp://{self.host}:{self.port}"
            self.socket.bind(address)
            logger.info(f"ZeroMQ服务器启动在 {address}")
            
            # 主循环
            while self.running:
                try:
                    # 接收消息
                    message = self.socket.recv_string()
                    logger.info(f"收到消息，长度: {len(message)}")
                    
                    # 处理消息
                    response = self._process_message(message)
                    
                    # 发送响应
                    self.socket.send_string(response)
                    logger.info(f"发送响应，长度: {len(response)}")
                    
                except zmq.ZMQError as e:
                    if self.running:
                        logger.error(f"ZeroMQ错误: {e}")
                    break
                except Exception as e:
                    logger.error(f"处理消息时发生错误: {e}")
                    if self.running:
                        error_response = json.dumps({
                            "type": "error",
                            "error": f"内部服务器错误: {str(e)}"
                        })
                        self.socket.send_string(error_response)
                    
        except Exception as e:
            logger.error(f"服务器循环发生错误: {e}")
        finally:
            self._cleanup()
    
    def _cleanup(self):
        """清理资源"""
        if self.socket:
            self.socket.close()
        if self.context:
            self.context.term()
        self.socket = None
        self.context = None
        logger.info("ZeroMQ服务器资源已清理")
    
    def start(self):
        """启动服务器"""
        if self.running:
            logger.warning("服务器已经在运行")
            return
        
        self.running = True
        self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self.server_thread.start()
        logger.info("ZeroMQ服务器启动成功")
    
    def stop(self):
        """停止服务器"""
        if not self.running:
            return
        
        self.running = False
        logger.info("正在停止ZeroMQ服务器...")
        
        # 如果socket存在，发送一个中断信号
        if self.socket:
            try:
                # 创建一个临时的客户端来中断recv
                temp_context = zmq.Context()
                temp_socket = temp_context.socket(zmq.REQ)
                temp_socket.setsockopt(zmq.LINGER, 0)
                temp_socket.connect(f"tcp://{self.host}:{self.port}")
                temp_socket.send_string("shutdown")
                temp_socket.close()
                temp_context.term()
            except:
                pass
        
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5.0)
        
        self._cleanup()
        logger.info("ZeroMQ服务器已停止")
    
    def is_running(self) -> bool:
        """检查服务器是否在运行"""
        return bool(self.running and self.server_thread and self.server_thread.is_alive())
    
    def get_address(self) -> str:
        """获取服务器地址"""
        return f"tcp://{self.host}:{self.port}"


def main():
    """命令行入口点：启动ZeroMQ服务器"""
    import argparse
    import signal
    import sys
    import time

    parser = argparse.ArgumentParser(description="启动ZeroMQ服务器")
    parser.add_argument("--host", default="127.0.0.1", help="服务器绑定的主机地址 (默认: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5555, help="服务器绑定的端口号 (默认: 5555)")
    args = parser.parse_args()

    server = ZeroMQServer(host=args.host, port=args.port)
    
    def signal_handler(sig, frame):
        print("\n收到停止信号，正在关闭服务器...")
        server.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print(f"启动ZeroMQ服务器在 {server.get_address()}")
    server.start()
    
    try:
        while server.is_running():
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
    
    print("服务器已停止")


if __name__ == "__main__":
    main()

