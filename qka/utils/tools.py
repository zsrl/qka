"""
QKA 基础工具类
提供通用的工具函数和类
"""

import time
import hashlib
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable
from functools import wraps
import inspect
from pathlib import Path
import pickle
import json


class Singleton(type):
    """单例模式元类"""
    _instances = {}
    _lock = threading.Lock()
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class Cache:
    """简单的内存缓存"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        """
        初始化缓存
        
        Args:
            max_size: 最大缓存条目数
            ttl: 过期时间(秒)
        """
        self.max_size = max_size
        self.ttl = ttl
        self._cache = {}
        self._access_times = {}
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            if key not in self._cache:
                return None
            
            # 检查是否过期
            if time.time() - self._access_times[key] > self.ttl:
                self._remove(key)
                return None
            
            # 更新访问时间
            self._access_times[key] = time.time()
            return self._cache[key]
    
    def set(self, key: str, value: Any):
        """设置缓存值"""
        with self._lock:
            # 如果缓存已满，移除最老的条目
            if len(self._cache) >= self.max_size and key not in self._cache:
                oldest_key = min(self._access_times.keys(), 
                               key=lambda k: self._access_times[k])
                self._remove(oldest_key)
            
            self._cache[key] = value
            self._access_times[key] = time.time()
    
    def _remove(self, key: str):
        """移除缓存条目"""
        self._cache.pop(key, None)
        self._access_times.pop(key, None)
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()
    
    def size(self) -> int:
        """获取缓存大小"""
        return len(self._cache)


class Timer:
    """计时器工具"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
    
    def start(self):
        """开始计时"""
        self.start_time = time.time()
    
    def stop(self):
        """停止计时"""
        self.end_time = time.time()
    
    def elapsed(self) -> float:
        """获取已耗时间(秒)"""
        if self.start_time is None:
            return 0
        
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, *args):
        self.stop()


def timer(func: Callable) -> Callable:
    """计时装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        func_name = f"{func.__module__}.{func.__name__}"
        print(f"⏱️ {func_name} 执行时间: {end_time - start_time:.4f}秒")
        
        return result
    return wrapper


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """重试装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            current_delay = delay
            
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts >= max_attempts:
                        raise e
                    
                    print(f"🔄 {func.__name__} 第{attempts}次尝试失败: {e}, {current_delay}秒后重试")
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            return None
        return wrapper
    return decorator


def memoize(ttl: Optional[int] = None):
    """记忆化装饰器"""
    def decorator(func: Callable) -> Callable:
        cache = {}
        cache_times = {}
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 创建缓存键
            key = _create_cache_key(func, args, kwargs)
            
            # 检查缓存
            if key in cache:
                if ttl is None or (time.time() - cache_times[key]) < ttl:
                    return cache[key]
                else:
                    # 过期，移除缓存
                    del cache[key]
                    del cache_times[key]
            
            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            cache[key] = result
            cache_times[key] = time.time()
            
            return result
        
        # 添加清除缓存的方法
        wrapper.clear_cache = lambda: cache.clear() or cache_times.clear()
        
        return wrapper
    return decorator


def _create_cache_key(func: Callable, args: tuple, kwargs: dict) -> str:
    """创建缓存键"""
    key_parts = [func.__name__]
    
    # 添加位置参数
    for arg in args:
        if hasattr(arg, '__dict__'):
            key_parts.append(str(hash(str(sorted(arg.__dict__.items())))))
        else:
            key_parts.append(str(hash(str(arg))))
    
    # 添加关键字参数
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}={hash(str(v))}")
    
    key_string = "|".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


class FileUtils:
    """文件操作工具类"""
    
    @staticmethod
    def ensure_dir(path: Union[str, Path]):
        """确保目录存在"""
        Path(path).mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def save_json(data: Any, file_path: Union[str, Path], indent: int = 2):
        """保存JSON文件"""
        FileUtils.ensure_dir(Path(file_path).parent)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
    
    @staticmethod
    def load_json(file_path: Union[str, Path]) -> Any:
        """加载JSON文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def save_pickle(data: Any, file_path: Union[str, Path]):
        """保存pickle文件"""
        FileUtils.ensure_dir(Path(file_path).parent)
        with open(file_path, 'wb') as f:
            pickle.dump(data, f)
    
    @staticmethod
    def load_pickle(file_path: Union[str, Path]) -> Any:
        """加载pickle文件"""
        with open(file_path, 'rb') as f:
            return pickle.load(f)
    
    @staticmethod
    def get_file_size(file_path: Union[str, Path]) -> int:
        """获取文件大小(字节)"""
        return Path(file_path).stat().st_size
    
    @staticmethod
    def get_file_mtime(file_path: Union[str, Path]) -> datetime:
        """获取文件修改时间"""
        return datetime.fromtimestamp(Path(file_path).stat().st_mtime)


class DateUtils:
    """日期时间工具类"""
    
    @staticmethod
    def is_trading_day(date: datetime) -> bool:
        """判断是否为交易日(简单实现，只排除周末)"""
        return date.weekday() < 5
    
    @staticmethod
    def get_trading_days(start_date: datetime, end_date: datetime) -> List[datetime]:
        """获取指定期间的交易日列表"""
        days = []
        current = start_date
        
        while current <= end_date:
            if DateUtils.is_trading_day(current):
                days.append(current)
            current += timedelta(days=1)
        
        return days
    
    @staticmethod
    def format_datetime(dt: datetime, format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
        """格式化日期时间"""
        return dt.strftime(format_str)
    
    @staticmethod
    def parse_datetime(date_str: str, format_str: str = '%Y-%m-%d') -> datetime:
        """解析日期时间字符串"""
        return datetime.strptime(date_str, format_str)
    
    @staticmethod
    def get_date_range(days: int, end_date: Optional[datetime] = None) -> tuple:
        """获取日期范围"""
        if end_date is None:
            end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return start_date, end_date


class MathUtils:
    """数学工具类"""
    
    @staticmethod
    def safe_divide(a: float, b: float, default: float = 0) -> float:
        """安全除法，避免除零错误"""
        return a / b if b != 0 else default
    
    @staticmethod
    def clamp(value: float, min_val: float, max_val: float) -> float:
        """将值限制在指定范围内"""
        return max(min_val, min(value, max_val))
    
    @staticmethod
    def percent_change(old_value: float, new_value: float) -> float:
        """计算百分比变化"""
        if old_value == 0:
            return 0
        return (new_value - old_value) / old_value * 100


class ValidationUtils:
    """验证工具类"""
    
    @staticmethod
    def is_valid_symbol(symbol: str) -> bool:
        """验证股票代码格式"""
        import re
        # 简单的A股股票代码验证
        pattern = r'^(000|002|300|600|688)\d{3}\.(SZ|SH)$'
        return bool(re.match(pattern, symbol))
    
    @staticmethod
    def is_positive_number(value: Any) -> bool:
        """验证是否为正数"""
        try:
            return float(value) > 0
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def is_valid_date_range(start_date: str, end_date: str) -> bool:
        """验证日期范围是否有效"""
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            return start <= end
        except ValueError:
            return False


def format_number(num: float, precision: int = 2, use_separator: bool = True) -> str:
    """格式化数字显示"""
    if use_separator:
        return f"{num:,.{precision}f}"
    else:
        return f"{num:.{precision}f}"


def format_percentage(ratio: float, precision: int = 2) -> str:
    """格式化百分比显示"""
    return f"{ratio * 100:.{precision}f}%"


def format_currency(amount: float, currency: str = '¥', precision: int = 2) -> str:
    """格式化货币显示"""
    return f"{currency}{amount:,.{precision}f}"


if __name__ == '__main__':
    # 测试缓存
    cache = Cache(max_size=3, ttl=2)
    cache.set('key1', 'value1')
    cache.set('key2', 'value2')
    print(f"缓存大小: {cache.size()}")
    print(f"key1: {cache.get('key1')}")
    
    # 测试计时器
    with Timer() as t:
        time.sleep(0.1)
    print(f"计时: {t.elapsed():.3f}秒")
    
    # 测试装饰器
    @timer
    @retry(max_attempts=2)
    def test_func():
        print("测试函数执行")
        return "success"
    
    result = test_func()
    print(f"结果: {result}")
    
    # 测试工具函数
    print(f"格式化数字: {format_number(123456.789)}")
    print(f"格式化百分比: {format_percentage(0.1234)}")
    print(f"格式化货币: {format_currency(123456.78)}")
    
    print("工具类测试完成")
