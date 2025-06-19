"""
QKA 事件驱动框架
提供发布-订阅模式的事件系统，支持异步和同步事件处理
"""

import asyncio
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
import threading
import queue
import traceback
from qka.utils.logger import logger


class EventType(Enum):
    """事件类型枚举"""
    # 数据相关事件
    DATA_LOADED = "data_loaded"
    DATA_ERROR = "data_error"
    
    # 回测相关事件
    BACKTEST_START = "backtest_start"
    BACKTEST_END = "backtest_end"
    BACKTEST_ERROR = "backtest_error"
    
    # 交易相关事件
    ORDER_CREATED = "order_created"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_ERROR = "order_error"
    
    # 策略相关事件
    STRATEGY_START = "strategy_start"
    STRATEGY_END = "strategy_end"
    STRATEGY_ERROR = "strategy_error"
    SIGNAL_GENERATED = "signal_generated"
    
    # 风险管理事件
    RISK_CHECK = "risk_check"
    RISK_ALERT = "risk_alert"
    
    # 系统事件
    SYSTEM_START = "system_start"
    SYSTEM_SHUTDOWN = "system_shutdown"
    HEARTBEAT = "heartbeat"


@dataclass
class Event:
    """事件基类"""
    event_type: EventType
    data: Any = None
    timestamp: datetime = None
    source: str = None
    event_id: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.event_id is None:
            self.event_id = f"{self.event_type.value}_{self.timestamp.strftime('%Y%m%d_%H%M%S_%f')}"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        result['event_type'] = self.event_type.value
        result['timestamp'] = self.timestamp.isoformat()
        return result


@dataclass
class DataEvent(Event):
    """数据事件"""
    symbol: str = None
    period: str = None
    count: int = None


@dataclass
class OrderEvent(Event):
    """订单事件"""
    order_id: str = None
    symbol: str = None
    action: str = None  # buy/sell
    quantity: int = None
    price: float = None
    order_type: str = None


@dataclass
class SignalEvent(Event):
    """信号事件"""
    symbol: str = None
    signal_type: str = None  # buy/sell/hold
    strength: float = None  # 信号强度 0-1
    reason: str = None


class EventHandler(ABC):
    """事件处理器基类"""
    
    @abstractmethod
    def handle(self, event: Event) -> Optional[Any]:
        """处理事件"""
        pass
    
    def can_handle(self, event: Event) -> bool:
        """判断是否可以处理该事件"""
        return True


class AsyncEventHandler(EventHandler):
    """异步事件处理器基类"""
    
    @abstractmethod
    async def handle_async(self, event: Event) -> Optional[Any]:
        """异步处理事件"""
        pass
    
    def handle(self, event: Event) -> Optional[Any]:
        """同步接口，内部调用异步方法"""
        return asyncio.run(self.handle_async(event))


class EventEngine:
    """事件引擎"""
    
    def __init__(self, max_queue_size: int = 10000):
        """
        初始化事件引擎
        
        Args:
            max_queue_size: 事件队列最大大小
        """
        self._handlers: Dict[EventType, List[Union[EventHandler, Callable]]] = defaultdict(list)
        self._event_queue = queue.Queue(maxsize=max_queue_size)
        self._running = False
        self._worker_thread = None
        self._event_history: List[Event] = []
        self._max_history_size = 1000
        
        # 统计信息
        self._event_count = defaultdict(int)
        self._error_count = 0
    
    def subscribe(self, event_type: EventType, handler: Union[EventHandler, Callable]):
        """
        订阅事件
        
        Args:
            event_type: 事件类型
            handler: 事件处理器或回调函数
        """
        self._handlers[event_type].append(handler)
        logger.debug(f"事件订阅: {event_type.value} -> {handler}")
    
    def unsubscribe(self, event_type: EventType, handler: Union[EventHandler, Callable]):
        """取消订阅"""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.debug(f"取消事件订阅: {event_type.value} -> {handler}")
    
    def emit(self, event: Event, sync: bool = False):
        """
        发送事件
        
        Args:
            event: 事件对象
            sync: 是否同步处理
        """
        if sync:
            self._process_event(event)
        else:
            try:
                self._event_queue.put_nowait(event)
            except queue.Full:
                logger.error(f"事件队列已满，丢弃事件: {event.event_type.value}")
    
    def emit_simple(self, event_type: EventType, data: Any = None, source: str = None, sync: bool = False):
        """
        发送简单事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
            source: 事件源
            sync: 是否同步处理
        """
        event = Event(event_type=event_type, data=data, source=source)
        self.emit(event, sync)
    
    def start(self):
        """启动事件引擎"""
        if self._running:
            logger.warning("事件引擎已经在运行")
            return
        
        self._running = True
        self._worker_thread = threading.Thread(target=self._run, daemon=True)
        self._worker_thread.start()
        
        logger.info("事件引擎已启动")
        self.emit_simple(EventType.SYSTEM_START, {"timestamp": datetime.now()})
    
    def stop(self):
        """停止事件引擎"""
        if not self._running:
            return
        
        self.emit_simple(EventType.SYSTEM_SHUTDOWN, {"timestamp": datetime.now()})
        self._running = False
        
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        
        logger.info("事件引擎已停止")
    
    def _run(self):
        """事件处理主循环"""
        while self._running:
            try:
                # 带超时的获取事件，避免阻塞
                event = self._event_queue.get(timeout=1)
                self._process_event(event)
                self._event_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"事件处理异常: {e}\n{traceback.format_exc()}")
                self._error_count += 1
    
    def _process_event(self, event: Event):
        """处理单个事件"""
        try:
            # 记录事件历史
            self._add_to_history(event)
            self._event_count[event.event_type] += 1
            
            # 获取处理器列表
            handlers = self._handlers.get(event.event_type, [])
            
            if not handlers:
                logger.debug(f"没有找到事件处理器: {event.event_type.value}")
                return
            
            # 执行处理器
            for handler in handlers:
                try:
                    if isinstance(handler, EventHandler):
                        if handler.can_handle(event):
                            handler.handle(event)
                    elif callable(handler):
                        handler(event)
                except Exception as e:
                    logger.error(f"事件处理器执行失败: {handler}, 事件: {event.event_type.value}, 错误: {e}")
                    self._error_count += 1
        
        except Exception as e:
            logger.error(f"事件处理异常: {e}\n{traceback.format_exc()}")
            self._error_count += 1
    
    def _add_to_history(self, event: Event):
        """添加到事件历史"""
        self._event_history.append(event)
        
        # 保持历史记录大小限制
        if len(self._event_history) > self._max_history_size:
            self._event_history = self._event_history[-self._max_history_size:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "event_count": dict(self._event_count),
            "error_count": self._error_count,
            "queue_size": self._event_queue.qsize(),
            "handler_count": {
                event_type.value: len(handlers) 
                for event_type, handlers in self._handlers.items()
            },
            "is_running": self._running
        }
    
    def get_event_history(self, event_type: Optional[EventType] = None, limit: int = 100) -> List[Event]:
        """
        获取事件历史
        
        Args:
            event_type: 筛选事件类型
            limit: 限制返回数量
        """
        history = self._event_history
        
        if event_type:
            history = [e for e in history if e.event_type == event_type]
        
        return history[-limit:]


# 全局事件引擎实例
event_engine = EventEngine()


# 便捷的装饰器函数
def event_handler(event_type: EventType):
    """
    事件处理器装饰器
    
    Examples:
        @event_handler(EventType.ORDER_FILLED)
        def on_order_filled(event):
            print(f"订单成交: {event.data}")
    """
    def decorator(func):
        event_engine.subscribe(event_type, func)
        return func
    return decorator


# 便捷函数
def emit_event(event_type: EventType, data: Any = None, source: str = None, sync: bool = False):
    """发送事件的便捷函数"""
    event_engine.emit_simple(event_type, data, source, sync)


def start_event_engine():
    """启动事件引擎"""
    event_engine.start()


def stop_event_engine():
    """停止事件引擎"""
    event_engine.stop()


if __name__ == '__main__':
    # 测试事件系统
    
    @event_handler(EventType.DATA_LOADED)
    def on_data_loaded(event):
        print(f"数据加载完成: {event.data}")
    
    @event_handler(EventType.ORDER_FILLED)
    def on_order_filled(event):
        print(f"订单成交: {event.data}")
    
    # 启动事件引擎
    start_event_engine()
    
    # 发送测试事件
    emit_event(EventType.DATA_LOADED, {"symbol": "000001", "count": 1000})
    emit_event(EventType.ORDER_FILLED, {"order_id": "123", "price": 10.5})
    
    # 等待处理完成
    import time
    time.sleep(1)
    
    # 查看统计信息
    print("事件统计:", event_engine.get_statistics())
    
    # 停止事件引擎
    stop_event_engine()
