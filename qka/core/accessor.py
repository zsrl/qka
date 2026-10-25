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
        # 同一根 bar 内 get() 的结果是不变的，缓存起来复用。
        # 实测一次回测里 get 被调 28953 次（平均每根 bar 17 次），每次都重建
        # 451 项 dict + Series，累计 15 秒。缓存后每根 bar 每个因子只建一次。
        self._cache: dict[str, pd.Series] = {}

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
            self._cache.clear()          # 换 bar：上一根 bar 的横截面全失效
        else:
            self._cache.pop(factor, None)  # 同一 bar 内同因子被重推，旧值作废
        for symbol, value in data.items():
            self._buffer[factor][symbol].append(value)

    def get(self, factor: str) -> pd.Series:
        """
        获取当前 bar 的横截面数据。

        Args:
            factor: 因子名，如 'close', 'volume'

        Returns:
            pd.Series，index=股票代码，values=最新值

        注意：返回值是同一根 bar 内共享的缓存对象，**只读**，不要原地修改。
        """
        cached = self._cache.get(factor)
        if cached is not None:
            return cached
        data = {sym: vals[-1] for sym, vals in self._buffer.get(factor, {}).items()}
        series = pd.Series(data)
        self._cache[factor] = series
        return series

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
        self._cache.clear()
