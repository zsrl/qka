"""
QKA 内置指标模块

提供滚动窗口的内置指标函数，供 Data.indicators 的 dispatch 使用。

与 analysis.py 的分工：
- analysis.py：接收原始 Series，返回单个标量（事后分析，如一次性 α/β/夏普）
- indicator.py：接收 DataFrame + symbol，返回滚动 Series（回测指标，每 bar 一个值）

所有函数签名统一为 fn(df, symbol, *args)，由 _apply_qka_indicators 调用。
"""

import numpy as np
import pandas as pd
from statsmodels.tsa.filters.hp_filter import hpfilter

from qka.core.analysis import _zigzag_core


def alpha(df: pd.DataFrame, symbol: str, window: int,
          rf: float = 0.0, periods_per_year: int = 252) -> pd.Series:
    """滚动詹森 α（年化）。

    公式：α = Rp - [Rf + β × (Rm - Rf)]
    其中 Rp、Rm 均已年化。

    Args:
        df: 含 {symbol}|returns 和 benchmark|returns 列的 DataFrame
        symbol: 股票代码
        window: 滚动窗口（交易日数）
        rf: 无风险利率（年化），默认 0
        periods_per_year: 每年交易日数，默认 252

    Returns:
        pd.Series: 滚动 α 值
    """
    returns = df[f'{symbol}|returns']
    bench = _get_benchmark(df)
    rp = returns.rolling(window).mean() * periods_per_year
    rm = bench.rolling(window).mean() * periods_per_year
    cov = returns.rolling(window).cov(bench)
    var = bench.rolling(window).var()
    beta_series = cov / var
    return rp - (rf + beta_series * (rm - rf))


def beta(df: pd.DataFrame, symbol: str, window: int) -> pd.Series:
    """滚动 β。

    公式：β = Cov(Rp, Rm) / Var(Rm)

    Args:
        df: 含 {symbol}|returns 和 benchmark|returns 列的 DataFrame
        symbol: 股票代码
        window: 滚动窗口（交易日数）

    Returns:
        pd.Series: 滚动 β 值
    """
    returns = df[f'{symbol}|returns']
    bench = _get_benchmark(df)
    cov = returns.rolling(window).cov(bench)
    var = bench.rolling(window).var()
    return cov / var


def sharpe(df: pd.DataFrame, symbol: str, window: int,
           rf: float = 0.0, periods_per_year: int = 252) -> pd.Series:
    """滚动夏普比率（年化）。

    公式：Sharpe = (Rp - rf) / σp
    其中 Rp、σp 均已年化。

    Args:
        df: 含 {symbol}|returns 列的 DataFrame
        symbol: 股票代码
        window: 滚动窗口（交易日数）
        rf: 无风险利率（年化），默认 0
        periods_per_year: 每年交易日数，默认 252

    Returns:
        pd.Series: 滚动夏普比率
    """
    returns = df[f'{symbol}|returns']
    rp = returns.rolling(window).mean() * periods_per_year
    vol = returns.rolling(window).std() * np.sqrt(periods_per_year)
    return (rp - rf) / vol


def max_drawdown(df: pd.DataFrame, symbol: str, window: int) -> pd.Series:
    """滚动窗口最大回撤。

    在指定窗口中，从峰值到谷底的最大跌幅，返回负数（如 -0.15 表示最大回撤 15%）。

    Args:
        df: 含 {symbol}|returns 列的 DataFrame
        symbol: 股票代码
        window: 滚动窗口（交易日数）

    Returns:
        pd.Series: 滚动最大回撤（负数）
    """
    returns = df[f'{symbol}|returns']
    cum = (1 + returns).cumprod()
    cum_values = cum.values
    result = np.full(len(cum_values), np.nan)
    for i in range(window - 1, len(cum_values)):
        peak = np.max(cum_values[i - window + 1 : i + 1])
        result[i] = (cum_values[i] - peak) / peak
    return pd.Series(result, index=cum.index)


def information_ratio(df: pd.DataFrame, symbol: str, window: int,
                      periods_per_year: int = 252) -> pd.Series:
    """滚动信息比率（年化）。

    公式：IR = mean(Rp - Rm) / std(Rp - Rm)，年化。

    Args:
        df: 含 {symbol}|returns 和 benchmark|returns 列的 DataFrame
        symbol: 股票代码
        window: 滚动窗口（交易日数）
        periods_per_year: 每年交易日数，默认 252

    Returns:
        pd.Series: 滚动信息比率
    """
    returns = df[f'{symbol}|returns']
    bench = _get_benchmark(df)
    excess = returns - bench
    mean_excess = excess.rolling(window).mean() * periods_per_year
    vol_excess = excess.rolling(window).std() * np.sqrt(periods_per_year)
    return mean_excess / vol_excess


def rolling_zigzag(df: pd.DataFrame, symbol: str, window: int,
                    threshold: float = 0.3, lamb: float = 1600) -> pd.Series:
    """滚动窗口 Zigzag 趋势方向。

    对每个 bar 取过去 window 根 K 线的收盘价，做 HP 滤波 + Zigzag 状态机，
    输出当前趋势方向。不含未来函数——每个窗口只用到当前 bar 为止的数据。

    Args:
        df: 含 {symbol}|close 列的 DataFrame
        symbol: 股票代码
        window: 滚动窗口（交易日数），至少 10
        threshold: 反转阈值，默认 0.3。峰顶回落 30% 确认顶
        lamb: HP 滤波平滑参数，默认 1600（日线数据标准值）

    Returns:
        pd.Series: 1（上行）/ -1（下行）/ NaN（窗口不足）
    """
    col = f'{symbol}|close'
    if col not in df.columns:
        raise ValueError(f"rolling_zigzag 需要 {col} 列")

    close = df[col]
    values = close.values
    idx = close.index
    result = np.full(len(values), np.nan)

    if len(values) < window or window < 10:
        return pd.Series(result, index=idx)

    for i in range(window - 1, len(values)):
        win_start = i - window + 1
        win_vals = values[win_start : i + 1]
        win_idx = idx[win_start : i + 1]

        try:
            log_price = np.log(np.maximum(win_vals, 1e-10))
            _, trend_log = hpfilter(log_price, lamb=lamb)
            hp_s = pd.Series(np.exp(trend_log), index=win_idx)

            segs = _zigzag_core(hp_s, threshold)
            if segs:
                direction = segs[-1]['dir']
                result[i] = 1 if direction == '上行' else -1
            else:
                result[i] = 0
        except Exception:
            result[i] = np.nan

    return pd.Series(result, index=idx)


def _get_benchmark(df: pd.DataFrame) -> pd.Series:
    """获取基准收益率列，不存在则抛异常。"""
    col = 'benchmark|returns'
    if col not in df.columns:
        raise ValueError(
            f"指标需要基准数据（{col}），"
            f"请在 Data 构造时传入 benchmark 参数"
        )
    return df[col]
