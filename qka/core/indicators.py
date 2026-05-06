"""
QKA 技术指标模块

提供基于 ta 库的技术指标计算封装，通过 TAAccessor 暴露给策略使用。
所有指标从 DataAccessor 获取历史数据，返回当前 bar 的横截面计算结果。

用法：
    class MyStrategy(Strategy):
        def on_bar(self, date):
            # 简单指标
            sma20 = self.ta.sma('close', length=20)
            ema14 = self.ta.ema('close', length=14)
            rsi14 = self.ta.rsi('close', length=14)
            atr14 = self.ta.atr(high='high', low='low', close='close', length=14)

            # 多输出指标（返回 DataFrame）
            macd = self.ta.macd('close', fast=12, slow=26, signal=9)
            bb = self.ta.bbands('close', length=20, std=2)

            # 自定义指标
            custom = self.ta.custom('close', func=lambda x: x.rolling(10).mean())
"""

from typing import Callable, Optional, Union
import pandas as pd
import numpy as np
import ta as _ta_lib


class TAAccessor:
    """技术指标访问器。

    绑定到 Strategy.ta，委托 DataAccessor 获取历史数据计算指标。
    所有方法返回当前 bar 的横截面 Series（index=股票代码）。
    """

    def __init__(self, data_accessor):
        """
        Args:
            data_accessor: DataAccessor 实例
        """
        self._data = data_accessor

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _buffered_history(self, factor: str, min_length: int) -> pd.DataFrame:
        """获取足够长的历史窗口，保证指标可计算。"""
        window = max(min_length * 3, 50)
        hist = self._data.history(factor, window=window)
        if hist.empty:
            return pd.DataFrame()
        return hist

    def _apply_to_stocks(
        self, hist: pd.DataFrame, min_length: int, func: Callable
    ) -> pd.Series:
        """对每只股票的历史序列应用指标函数，取最新值。"""
        result = {}
        for col in hist.columns:
            series = hist[col].dropna()
            if len(series) < min_length:
                continue
            try:
                val = func(series)
                if isinstance(val, (pd.Series, pd.DataFrame)):
                    val = val.iloc[-1]
                if isinstance(val, (int, float, np.floating, np.integer)):
                    result[col] = float(val)
                elif val is not None:
                    result[col] = val
            except Exception:
                continue
        return pd.Series(result, dtype=float)

    # ------------------------------------------------------------------
    # 趋势指标
    # ------------------------------------------------------------------

    def sma(self, factor: str = 'close', length: int = 20) -> pd.Series:
        """简单移动平均线 (Simple Moving Average)

        Args:
            factor: 因子名，默认 'close'
            length: 窗口期，默认 20

        Returns:
            pd.Series，index=股票代码
        """
        hist = self._buffered_history(factor, length)
        if hist.empty:
            return pd.Series(dtype=float)
        return self._apply_to_stocks(
            hist, length,
            lambda s: _ta_lib.trend.sma_indicator(s, window=length)
        )

    def ema(self, factor: str = 'close', length: int = 14) -> pd.Series:
        """指数移动平均线 (Exponential Moving Average)

        Args:
            factor: 因子名，默认 'close'
            length: 窗口期，默认 14

        Returns:
            pd.Series，index=股票代码
        """
        hist = self._buffered_history(factor, length)
        if hist.empty:
            return pd.Series(dtype=float)
        return self._apply_to_stocks(
            hist, length,
            lambda s: _ta_lib.trend.ema_indicator(s, window=length)
        )

    def wma(self, factor: str = 'close', length: int = 14) -> pd.Series:
        """加权移动平均线 (Weighted Moving Average)

        Args:
            factor: 因子名，默认 'close'
            length: 窗口期，默认 14

        Returns:
            pd.Series，index=股票代码
        """
        hist = self._buffered_history(factor, length)
        if hist.empty:
            return pd.Series(dtype=float)
        return self._apply_to_stocks(
            hist, length,
            lambda s: _ta_lib.trend.wma_indicator(s, window=length)
        )

    # ------------------------------------------------------------------
    # 动量指标
    # ------------------------------------------------------------------

    def rsi(self, factor: str = 'close', length: int = 14) -> pd.Series:
        """相对强弱指标 (Relative Strength Index)

        Args:
            factor: 因子名，默认 'close'
            length: 窗口期，默认 14

        Returns:
            pd.Series，取值范围 [0, 100]
        """
        hist = self._buffered_history(factor, length)
        if hist.empty:
            return pd.Series(dtype=float)
        return self._apply_to_stocks(
            hist, length,
            lambda s: _ta_lib.momentum.rsi(s, window=length)
        )

    def macd(
        self,
        factor: str = 'close',
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> pd.DataFrame:
        """MACD 指标 (Moving Average Convergence Divergence)

        返回 DataFrame，包含三列：
        - macd: MACD 快慢线差
        - signal: 信号线
        - histogram: 柱状图 (macd - signal)

        Args:
            factor: 因子名
            fast: 快线周期，默认 12
            slow: 慢线周期，默认 26
            signal: 信号线周期，默认 9

        Returns:
            pd.DataFrame，列=['macd', 'signal', 'histogram']
        """
        hist = self._buffered_history(factor, slow)
        if hist.empty:
            return pd.DataFrame(columns=['macd', 'signal', 'histogram'])

        macd_vals, sig_vals, hist_vals = {}, {}, {}
        for col in hist.columns:
            series = hist[col].dropna()
            if len(series) < slow:
                continue
            try:
                m = _ta_lib.trend.MACD(
                    series,
                    window_slow=slow,
                    window_fast=fast,
                    window_sign=signal,
                )
                macd_vals[col] = float(m.macd().iloc[-1])
                sig_vals[col] = float(m.macd_signal().iloc[-1])
                hist_vals[col] = float(m.macd_diff().iloc[-1])
            except Exception:
                continue

        return pd.DataFrame({
            'macd': pd.Series(macd_vals, dtype=float),
            'signal': pd.Series(sig_vals, dtype=float),
            'histogram': pd.Series(hist_vals, dtype=float),
        })

    # ------------------------------------------------------------------
    # 波动率指标
    # ------------------------------------------------------------------

    def bbands(
        self,
        factor: str = 'close',
        length: int = 20,
        std: int = 2,
    ) -> pd.DataFrame:
        """布林带 (Bollinger Bands)

        返回 DataFrame，包含三列：
        - upper: 上轨 (MA + k * std)
        - middle: 中轨 (MA)
        - lower: 下轨 (MA - k * std)

        Args:
            factor: 因子名
            length: 窗口期，默认 20
            std: 标准差倍数，默认 2

        Returns:
            pd.DataFrame，列=['upper', 'middle', 'lower']
        """
        hist = self._buffered_history(factor, length)
        if hist.empty:
            return pd.DataFrame(columns=['upper', 'middle', 'lower'])

        up_vals, mid_vals, low_vals = {}, {}, {}
        for col in hist.columns:
            series = hist[col].dropna()
            if len(series) < length:
                continue
            try:
                bb = _ta_lib.volatility.BollingerBands(
                    series, window=length, window_dev=std
                )
                up_vals[col] = float(bb.bollinger_hband().iloc[-1])
                mid_vals[col] = float(bb.bollinger_mavg().iloc[-1])
                low_vals[col] = float(bb.bollinger_lband().iloc[-1])
            except Exception:
                continue

        return pd.DataFrame({
            'upper': pd.Series(up_vals, dtype=float),
            'middle': pd.Series(mid_vals, dtype=float),
            'lower': pd.Series(low_vals, dtype=float),
        })

    def atr(
        self,
        high: str = 'high',
        low: str = 'low',
        close: str = 'close',
        length: int = 14,
    ) -> pd.Series:
        """平均真实波幅 (Average True Range)

        需要三个因子：最高价、最低价、收盘价。

        Args:
            high: 最高价因子名
            low: 最低价因子名
            close: 收盘价因子名
            length: 窗口期，默认 14

        Returns:
            pd.Series，index=股票代码
        """
        def _atr_for_stock(h, l, c):
            h_s = h.dropna()
            l_s = l.dropna()
            c_s = c.dropna()
            idx = h_s.index.intersection(l_s.index).intersection(c_s.index)
            if len(idx) < length:
                return None
            return _ta_lib.volatility.average_true_range(
                h_s.loc[idx], l_s.loc[idx], c_s.loc[idx], window=length
            )

        hist_h = self._buffered_history(high, length)
        hist_l = self._buffered_history(low, length)
        hist_c = self._buffered_history(close, length)
        if hist_h.empty or hist_l.empty or hist_c.empty:
            return pd.Series(dtype=float)

        result = {}
        for col in hist_c.columns:
            if col not in hist_h.columns or col not in hist_l.columns:
                continue
            try:
                atr_series = _atr_for_stock(hist_h[col], hist_l[col], hist_c[col])
                if atr_series is not None and len(atr_series) > 0:
                    result[col] = float(atr_series.iloc[-1])
            except Exception:
                continue
        return pd.Series(result, dtype=float)

    # ------------------------------------------------------------------
    # 自定义指标
    # ------------------------------------------------------------------

    def custom(
        self,
        factor: str = 'close',
        func: Optional[Callable] = None,
        length: Optional[int] = None,
        **kwargs,
    ) -> pd.Series:
        """自定义指标。

        传入一个可调用对象，接收 pd.Series 返回 pd.Series 或标量。

        Args:
            factor: 因子名
            func: 可调用对象，fn(series, **kwargs) -> pd.Series 或标量
            length: 最小所需数据长度（可选）
            **kwargs: 透传给 func 的额外参数

        Returns:
            pd.Series，index=股票代码
        """
        if func is None:
            raise ValueError("custom() 需要提供 func 参数")

        min_len = length or 1
        hist = self._buffered_history(factor, min_len)
        if hist.empty:
            return pd.Series(dtype=float)

        # 过滤掉透传给 func 的 buffer_ratio
        kwargs.pop('buffer_ratio', None)

        result = {}
        for col in hist.columns:
            series = hist[col].dropna()
            if len(series) < min_len:
                continue
            try:
                val = func(series, **kwargs)
                if isinstance(val, (pd.Series, pd.DataFrame)):
                    val = val.iloc[-1]
                if isinstance(val, (int, float, np.floating, np.integer)):
                    result[col] = float(val)
                elif val is not None:
                    result[col] = val
            except Exception:
                continue
        return pd.Series(result, dtype=float)
