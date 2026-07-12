"""
QKA策略模块

提供策略开发的抽象基类，定义策略开发的标准接口和事件处理机制。
"""

from abc import ABC, abstractmethod
import pandas as pd


class Strategy(ABC):
    """
    策略抽象基类

    所有自定义策略都应该继承此类，并实现 on_bar 方法。

    broker / sizing / _data 由 Backtest.run() 在执行时注入，
    策略本身不需要在 __init__ 中创建它们。

    Attributes:
        broker (Broker): 交易经纪商实例，由 Backtest 注入
        sizing (SizingAccessor): 仓位计算工具，由 Backtest 注入
        _data (DataAccessor): 数据访问器，由 Backtest 注入
    """

    def __init__(self):
        """
        初始化策略。

        子类用 super().__init__() 调用即可，不需要传任何参数。
        broker / sizing / _data 由 Backtest.run() 在执行时注入。
        """
        pass

    def get(self, factor: str):
        """
        获取当前 bar 的横截面数据。

        仅当 Backtest.run() 注入 _data 后可用。

        Args:
            factor: 因子名，如 'close', 'volume'

        Returns:
            pd.Series，index=股票代码，values=最新值
        """
        return self._data.get(factor)

    def history(self, factor: str, window: int = 20):
        """
        获取因子的历史窗口数据。

        Args:
            factor: 因子名
            window: 窗口大小

        Returns:
            pd.DataFrame，行=日期，列=股票代码
        """
        return self._data.history(factor, window)

    @abstractmethod
    def on_bar(self, date):
        """
        每个 bar 的处理逻辑，必须由子类实现。

        使用 self.get(factor) / self.history(factor, window) 获取数据。

        Args:
            date: 当前日期（pd.Timestamp）
        """
