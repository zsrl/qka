"""
QKA策略模块

提供策略开发的抽象基类，定义策略开发的标准接口和事件处理机制。
"""

from abc import ABC, abstractmethod
from qka.core.broker import Broker
from qka.core.accessor import DataAccessor
from qka.core.sizing import SizingAccessor


class Strategy(ABC):
    """
    策略抽象基类

    所有自定义策略都应该继承此类，并实现 on_bar 方法。

    Attributes:
        broker (Broker): 交易经纪商实例，用于执行交易操作
        sizing (SizingAccessor): 仓位计算工具，提供 self.sizing.percent() 等方法
        _data (DataAccessor): 数据访问器，提供 self.get() 和 self.history() 接口
    """

    def __init__(self, cash: float = 100000.0):
        """
        初始化策略

        Args:
            cash: 初始资金，默认 10 万元
        """
        self.broker = Broker(initial_cash=cash)
        self.sizing = SizingAccessor(self.broker)
        self._data = DataAccessor(max_window=750)

    def get(self, factor: str):
        """
        获取当前 bar 的横截面数据。

        替代旧的 on_bar(date, get) 中的 get 参数。
        仅当 on_bar 通过 self._data 注入数据后才能使用。

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

        --- 用法 ---

        class MyStrategy(Strategy):
            def on_bar(self, date):
                # 横截面数据（当前 bar 所有股票）
                close = self.get('close')

                # 历史序列（过去 N 天）
                hist = self.history('close', 20)

                # 仓位管理
                size = self.sizing.percent(0.1, float(close['000001.SZ']))

                # 交易操作
                if not close.empty and '000001.SZ' in close.index:
                    price = float(close['000001.SZ'])
                    size = self.sizing.percent(0.1, price)
                    self.broker.buy('000001.SZ', price, size)

        Args:
            date: 当前日期（pd.Timestamp）
        """
