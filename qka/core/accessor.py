"""
QKA 数据访问器模块

提供基于滚动窗口的数据访问接口，支持横截面查询 (get) 和历史序列查询 (history)。
内部使用 deque 维护固定大小的滚动缓存，在分区迭代时跨分区延续。
"""

from collections import deque, defaultdict
from typing import Optional
import pandas as pd


class DataAccessor:
    """
    滚动窗口数据访问器。

    用法：
        每 bar 调用 push(date, factor, data) 推入数据，
        然后策略中调用 get(factor) / history(factor, window) 查询。

    Attributes:
        max_window (int): 最大缓存天数
    """

    def __init__(self, max_window: int = 250):
        """
        Args:
            max_window: 滚动窗口大小，默认 250 个交易日
        """
        self._max_window = max_window
        # _buffer[factor][symbol] = deque(values, maxlen=max_window)
        self._buffer: dict[str, dict[str, deque]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=max_window))
        )
        self._dates: deque = deque(maxlen=max_window)
        self._last_date = None  # 避免同一 bar 内多次 push 重复记录日期

    def push(self, date, factor: str, data: dict):
        """
        推入一个因子在某天的横截面数据。

        Args:
            date: 当前日期
            factor: 因子名，如 'close', 'volume'
            data: {symbol: value} 字典
        """
        # 同一 bar 只记录一次日期（可能推入多个 factor）
        if date != self._last_date:
            self._dates.append(date)
            self._last_date = date
        for symbol, value in data.items():
            self._buffer[factor][symbol].append(value)

    def get(self, factor: str) -> pd.Series:
        """
        获取当前 bar 的横截面数据。

        Args:
            factor: 因子名，如 'close', 'volume'

        Returns:
            pd.Series，index=股票代码，values=最新值
        """
        data = {sym: vals[-1] for sym, vals in self._buffer.get(factor, {}).items()}
        return pd.Series(data)

    def history(self, factor: str, window: int = 20) -> pd.DataFrame:
        """
        获取因子的历史窗口数据。

        Args:
            factor: 因子名
            window: 窗口大小

        Returns:
            pd.DataFrame，行=日期，列=股票代码
        """
        data = {}
        for sym, vals in self._buffer.get(factor, {}).items():
            lst = list(vals)
            data[sym] = lst[-window:]

        dates = list(self._dates)[-window:]
        return pd.DataFrame(data, index=dates)

    def clear(self):
        """清空所有缓存（分区切换时使用）"""
        self._buffer.clear()
        self._dates.clear()
        self._last_date = None
