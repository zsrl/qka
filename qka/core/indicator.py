"""
QKA 内置指标模块

提供滚动窗口的内置指标函数，供 Data.factors 的 dispatch 使用。

与 analysis.py 的分工：
- analysis.py：接收原始 Series，返回单个标量（事后分析，如一次性 α/β/夏普）
- indicator.py：接收 DataFrame + symbol，返回滚动 Series（回测指标，每 bar 一个值）

所有函数签名统一为 fn(df, symbol, *args)，由 _apply_qka_factors 调用。
"""

import numpy as np
import pandas as pd
from statsmodels.tsa.filters.hp_filter import hpfilter

from qka.core.analysis import _zigzag_core


# ── 窗口参数：整数 = 行数，字符串 = 日历周期 ──────────────────────
#   ('qka.alpha', 250)    → 往前数 250 根 K 线（老写法，行为完全不变）
#   ('qka.alpha', '1Y')   → 过去一个日历年（约 243 个交易日，每年自动适配）
#
# 🚨 字符串**必须自己解析**，不能直接丢给 pandas：pandas 里小写 m 是「分钟」、
# 大写 M 是「月末」，`'12m'` 会被理解成 12 分钟还静默算出一堆垃圾。
# 规范写法大写（1Y / 3M / 20D），解析时大小写都认。
_WINDOW_UNITS = {'Y': 365.0, 'M': 30.0, 'D': 1.0}

# 一年按多少个交易日折算 —— 只用来定「窗口内至少要攒够几根 K 线」。
# 实测（600519 全历史，365 天窗口内行数）：中位 243，最少 235，最多 250。
# 门槛取 233（比最少的 235 再低一点）—— 取 240 的话，遇上节假日特别密的年份
# 那几天会凑不满、因子留空，白丢数据。
_TRADING_DAYS_PER_YEAR = 233

# 真正折算「一个时间窗口里该有多少根 K 线」时用这个数（实际交易日的中位数）。
# 🚨 跟上面的门槛不是一回事：门槛是「够不够算」，这个数是「要留多少行当预热」。
# 用 233 去预热 10 年期会少 100 根样本，尾部算出来的值就是错的。
_TRADING_DAYS_ACTUAL = 243


def resolve_window(window):
    """把窗口参数翻译成 (rolling 的窗口, 最小样本数)。

    Args:
        window: 整数（行数）或字符串（'1Y' / '3M' / '20D'，大小写都认）

    Returns:
        (win, min_periods)
        - 整数：win 是 int，min_periods 等于它本身 —— 与旧行为逐位一致
        - 字符串：win 是 pd.Timedelta，min_periods 是折合出来的交易日数

    Raises:
        ValueError: 写法认不出，或数值 <= 0
    """
    if isinstance(window, str):
        text = window.strip().upper()
        if not text:
            raise ValueError('窗口参数不能为空字符串')
        unit = text[-1]
        if unit not in _WINDOW_UNITS:
            raise ValueError(
                f"认不出的窗口单位 {window!r}：只支持 Y（年）/ M（月）/ D（天），如 '1Y'、'3M'、'20D'"
            )
        try:
            num = float(text[:-1])
        except ValueError:
            raise ValueError(f"认不出的窗口写法 {window!r}：应为「数字+单位」，如 '1Y'") from None
        if num <= 0:
            raise ValueError(f'窗口必须大于 0：{window!r}')
        days = num * _WINDOW_UNITS[unit]
        min_periods = max(1, int(round(days * _TRADING_DAYS_PER_YEAR / 365.0)))
        return pd.Timedelta(days=days), min_periods

    try:
        win = int(window)
    except (TypeError, ValueError):
        raise ValueError(f'窗口参数只能是整数或字符串，收到 {window!r}') from None
    if win <= 0:
        raise ValueError(f'窗口必须大于 0：{window!r}')
    return win, win


def window_to_rows(window) -> int:
    """这个窗口总共跨多少个交易日 —— 用来判断「数据够不够」和「预热要留多少行」。

    - 整数：原样返回
    - 字符串：按**实际交易日**折算（'1Y' → 243、'10Y' → 2430）。

    🚨 这里用实际交易日（243/年）而不是 `min_periods`（240/年）：差的那 3 根在
    10 年期会放大成 30 根，增量预热按 2400 行回溯的话，尾部算出来的值会比全量算的少
    30 个样本 —— 结果不一致，而且不会报错。
    """
    win, _min_periods = resolve_window(window)
    if isinstance(win, int):
        return win
    days = win / pd.Timedelta(days=1)
    return int(np.ceil(days * _TRADING_DAYS_ACTUAL / 365.0))


def _window_starts(index, window):
    """算出「每个位置对应的窗口起点行号」，供手写循环的指标使用。

    Returns:
        (starts, min_periods)：starts[i] 是第 i 行的窗口起始行号；
        窗口还不够长时给 -1，调用方跳过即可。
    """
    n = len(index)
    if isinstance(window, str):
        win, min_periods = resolve_window(window)
        left = index - win                      # DatetimeIndex - Timedelta
        starts = np.asarray(index.searchsorted(left, side='left'), dtype=np.int64)
        return starts, min_periods
    w = int(window)
    starts = np.arange(n, dtype=np.int64) - w + 1
    starts[starts < 0] = -1
    return starts, w


def alpha(df: pd.DataFrame, symbol: str, window: int,
          rf: float | pd.Series = 0.0, periods_per_year: int = 252) -> pd.Series:
    """滚动詹森 α（年化）。

    公式：α = Rp - [Rf + β × (Rm - Rf)]
    其中 Rp、Rm 均已年化。

    Args:
        df: 含 {symbol}|returns 和 benchmark|returns 列的 DataFrame
        symbol: 股票代码
        window: 滚动窗口。整数 = 交易日数（往前数多少根）；
            字符串 = 日历周期，如 '1Y'（一个日历年）/ '3M' / '20D'，大小写都认
        rf: 无风险利率（**年化**，小数）。两种写法：
            - 标量：全程同一个数，如 0.02
            - 序列（带日期索引）：**取该窗口内的平均值**，见 _rf_window_mean
        periods_per_year: 每年交易日数，默认 252

    Returns:
        pd.Series: 滚动 α 值

    Note:
        传序列时，窗口内数据不全（如序列首日之前）算不出 α（结果为 NaN）——
        宁可留空，也不拿一个来路不明的常数顶上。
    """
    returns = df[f'{symbol}|returns']
    bench = _get_benchmark(df)
    win, mp = resolve_window(window)
    rp = returns.rolling(win, min_periods=mp).mean() * periods_per_year
    rm = bench.rolling(win, min_periods=mp).mean() * periods_per_year
    cov = returns.rolling(win, min_periods=mp).cov(bench)
    var = bench.rolling(win, min_periods=mp).var()
    beta_series = cov / var
    rf = _rf_window_mean(rf, df.index, window)
    return rp - (rf + beta_series * (rm - rf))


def beta(df: pd.DataFrame, symbol: str, window: int) -> pd.Series:
    """滚动 β。

    公式：β = Cov(Rp, Rm) / Var(Rm)

    Args:
        df: 含 {symbol}|returns 和 benchmark|returns 列的 DataFrame
        symbol: 股票代码
        window: 滚动窗口。整数 = 交易日数（往前数多少根）；
            字符串 = 日历周期，如 '1Y'（一个日历年）/ '3M' / '20D'，大小写都认

    Returns:
        pd.Series: 滚动 β 值
    """
    returns = df[f'{symbol}|returns']
    bench = _get_benchmark(df)
    win, mp = resolve_window(window)
    cov = returns.rolling(win, min_periods=mp).cov(bench)
    var = bench.rolling(win, min_periods=mp).var()
    return cov / var


def sharpe(df: pd.DataFrame, symbol: str, window: int,
           rf: float | pd.Series = 0.0, periods_per_year: int = 252) -> pd.Series:
    """滚动夏普比率（年化）。

    公式：Sharpe = (Rp - rf) / σp
    其中 Rp、σp 均已年化。

    Args:
        df: 含 {symbol}|returns 列的 DataFrame
        symbol: 股票代码
        window: 滚动窗口。整数 = 交易日数（往前数多少根）；
            字符串 = 日历周期，如 '1Y'（一个日历年）/ '3M' / '20D'，大小写都认
        rf: 无风险利率（**年化**，小数）。标量 = 全程一个数；
            序列 = 取该窗口内的平均值（见 _rf_window_mean）
        periods_per_year: 每年交易日数，默认 252

    Returns:
        pd.Series: 滚动夏普比率
    """
    returns = df[f'{symbol}|returns']
    win, mp = resolve_window(window)
    rp = returns.rolling(win, min_periods=mp).mean() * periods_per_year
    vol = returns.rolling(win, min_periods=mp).std() * np.sqrt(periods_per_year)
    rf = _rf_window_mean(rf, df.index, window)
    return (rp - rf) / vol


def max_drawdown(df: pd.DataFrame, symbol: str, window: int) -> pd.Series:
    """滚动窗口最大回撤。

    在指定窗口中，从峰值到谷底的最大跌幅，返回负数（如 -0.15 表示最大回撤 15%）。

    Args:
        df: 含 {symbol}|returns 列的 DataFrame
        symbol: 股票代码
        window: 滚动窗口。整数 = 交易日数（往前数多少根）；
            字符串 = 日历周期，如 '1Y'（一个日历年）/ '3M' / '20D'，大小写都认

    Returns:
        pd.Series: 滚动最大回撤（负数）
    """
    returns = df[f'{symbol}|returns']
    cum = (1 + returns).cumprod()
    cum_values = cum.values
    result = np.full(len(cum_values), np.nan)
    # 窗口起点按参数类型算：整数按行数、字符串按日历回溯（见 _window_starts）
    starts, min_periods = _window_starts(cum.index, window)
    for i in range(len(cum_values)):
        s = starts[i]
        if s < 0 or (i - s + 1) < min_periods:
            continue
        seg = cum_values[s : i + 1]
        # 窗口内逐日刷新峰值，再取「任意时刻从峰到谷」最深的那一次。
        # 旧实现只算 (末值 - 窗口峰值) / 窗口峰值 —— 那是「当前回撤」（现在离最高点多远），
        # 会漏掉中间已经发生过的深坑：净值 1 → 1.2 → 0.6 → 1.3，旧算法给 0，
        # 实际最深跌过 -50%。与 analysis.max_drawdown 的口径也不一致。
        peak = np.maximum.accumulate(seg)
        result[i] = np.min(seg / peak - 1.0)
    return pd.Series(result, index=cum.index)


def information_ratio(df: pd.DataFrame, symbol: str, window: int,
                      periods_per_year: int = 252) -> pd.Series:
    """滚动信息比率（年化）。

    公式：IR = mean(Rp - Rm) / std(Rp - Rm)，年化。

    Args:
        df: 含 {symbol}|returns 和 benchmark|returns 列的 DataFrame
        symbol: 股票代码
        window: 滚动窗口。整数 = 交易日数（往前数多少根）；
            字符串 = 日历周期，如 '1Y'（一个日历年）/ '3M' / '20D'，大小写都认
        periods_per_year: 每年交易日数，默认 252

    Returns:
        pd.Series: 滚动信息比率
    """
    returns = df[f'{symbol}|returns']
    bench = _get_benchmark(df)
    excess = returns - bench
    win, mp = resolve_window(window)
    mean_excess = excess.rolling(win, min_periods=mp).mean() * periods_per_year
    vol_excess = excess.rolling(win, min_periods=mp).std() * np.sqrt(periods_per_year)
    return mean_excess / vol_excess


def rolling_zigzag(df: pd.DataFrame, symbol: str, window: int,
                    threshold: float = 0.3, lamb: float = 1600) -> pd.Series:
    """滚动窗口 Zigzag 趋势方向。

    对每个 bar 取过去 window 根 K 线的收盘价，做 HP 滤波 + Zigzag 状态机，
    输出当前趋势方向。不含未来函数——每个窗口只用到当前 bar 为止的数据。

    Args:
        df: 含 {symbol}|close 列的 DataFrame
        symbol: 股票代码
        window: 滚动窗口。整数 = 交易日数（往前数多少根）；
            字符串 = 日历周期，如 '1Y'（一个日历年）/ '3M' / '20D'，大小写都认，至少 10
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

    starts, min_periods = _window_starts(idx, window)
    if len(values) < min_periods or min_periods < 10:
        return pd.Series(result, index=idx)

    for i in range(len(values)):
        win_start = starts[i]
        if win_start < 0 or (i - win_start + 1) < min_periods:
            continue
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


def _rf_window_mean(rf, index, window: int):
    """把无风险利率对齐成「每个窗口内的平均值」。

    传标量时原样返回（全程一个数，老行为不变）；传序列时按下面的规则对齐。

    为什么取窗口内均值、而不是窗口起点那天的值：

        rf 用的是**短期**国债（真正的无风险利率，长端含期限溢价，不算无风险）。
        短期利率的含义是「从某天起锁定一年」，只能覆盖一年 —— 拿它去代表一个
        十年窗口的机会成本，等于说「剩下九年没有着落」。

        取窗口内均值，对应的假设是：这笔钱在整个窗口里一直滚动买入短期无风险
        资产（到期就续上），那么整个窗口的平均年化机会成本就是各期的平均。
        这也是 Fama-French 一脉的标准做法 —— 他们的「逐日扣减」在数学上就是
        这个窗口均值。

    实现要点：
        - `ffill`：某天没有国债报价（国债休市但股市开市），沿用前一日
        - `min_periods=window`：窗口内数据不全就留空，不拿半截样本硬凑
        - 序列首日之前的窗口自然为空（起点卡 2010）

    Args:
        rf: 标量或带日期索引的 Series（年化，小数）
        index: 目标 DataFrame 的索引（日期）
        window: 滚动窗口长度（交易日数）

    Returns:
        float 或 与 index 对齐的 Series
    """
    if not isinstance(rf, pd.Series):
        return rf

    s = rf
    if not isinstance(s.index, pd.DatetimeIndex):
        s = s.copy()
        s.index = pd.to_datetime(s.index)
    if index is not None and len(s) and isinstance(index, pd.DatetimeIndex):
        s = s.reindex(s.index.union(index)).ffill().reindex(index)

    win, min_periods = resolve_window(window)
    return s.rolling(win, min_periods=min_periods).mean()


def _get_benchmark(df: pd.DataFrame) -> pd.Series:
    """获取基准收益率列，不存在则抛异常。"""
    col = 'benchmark|returns'
    if col not in df.columns:
        raise ValueError(
            f"指标需要基准数据（{col}），"
            f"请在 Data 构造时传入 benchmark 参数"
        )
    return df[col]
