"""
QKA 模拟标的数据模块

提供 Simulate 类：描述一只由 qka 现场生成的行情序列（不下载、不读缓存）。
把它放进 Data(symbols=[...]) 即可，写法与真实标的完全同构。
"""

from qka.utils.logger import logger


class Simulate:
    """
    模拟标的：一只由 qka 现场造出来的行情。

    用法与真实标的写法完全一致，区别只在 symbols 里放的是它而不是代码字符串：

    ```python
    from qka import Data, Simulate

    data = Data(symbols=[
        'sh.600900',                                       # 真实标的，照常下载
        Simulate('sim.a', drift=0.0, reversion=0.08, vol=0.018),
    ])
    df = data.get(start_date='2023-01-01', end_date='2025-12-31')
    ```

    行情按「带趋势的均值回复」在对数价格上演化：

        r_t = drift + reversion * (logAnchor - logP_{t-1}) + vol * eps_t

    eps_t ~ N(0, 1)。三个参数各管一件事：

    - drift (μ)：日漂移。正=上涨、负=下跌、0=无方向
    - reversion (θ)：均值回复强度。越大越黏在中枢附近（半衰期 = ln2 / θ）；0 = 不回复
    - vol (σ)：日波动率。如 0.015 约等于每日上下 1.5%

    drift=0 且 reversion=0 时退化为纯随机游走。

    Attributes:
        symbol (str): 标的代码，同时用作 DataFrame 的列前缀（如 sim.a|close）
        drift (float): 日漂移 μ
        reversion (float): 均值回复强度 θ
        vol (float): 日波动率 σ
    """

    def __init__(
        self,
        symbol: str,
        drift: float = 0.0,
        reversion: float = 0.0,
        vol: float = 0.012,
    ):
        """
        初始化模拟标的。

        Args:
            symbol: 标的代码，自定义即可（如 'sim.a'）。不能为空，且不能与同一
                Data 里的其他标的重复
            drift: 日漂移 μ，正=上涨、负=下跌、0=无方向，默认 0
            reversion: 均值回复强度 θ，必须 >= 0（越大越黏在中枢附近），默认 0
            vol: 日波动率 σ，必须 > 0（如 0.015 约等于每日上下 1.5%），默认 0.012
        """
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError(f"symbol 必须是非空字符串，got {symbol!r}")
        self.symbol = symbol.strip()
        self.drift = float(drift)
        self.reversion = float(reversion)
        self.vol = float(vol)

        if self.reversion < 0:
            raise ValueError(f"reversion 必须 >= 0，got {self.reversion}")
        if self.vol <= 0:
            raise ValueError(f"vol 必须 > 0，got {self.vol}")

        logger.debug(f"Simulate 标的已创建: {self}")

    def __repr__(self) -> str:
        return (
            f"Simulate(symbol={self.symbol!r}, drift={self.drift}, "
            f"reversion={self.reversion}, vol={self.vol})"
        )
