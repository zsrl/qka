"""
事后分析模块

包含需要在全序列范围内计算的函数（非逐 bar 可算），
禁止用于实时交易和回测策略。
"""

from collections import namedtuple

import numpy as np
import pandas as pd
from statsmodels.tsa.filters.hp_filter import hpfilter

Segment = namedtuple('Segment', ['start', 'end', 'direction', 'change'])
AlphaBeta = namedtuple('AlphaBeta', ['alpha', 'beta'])


class Analysis:
    """
    事后分析工具集。

    所有方法均为无状态的静态分析，接受数据作为参数，
    不做回测、不做实时判断。

    Methods:
        zigzag:          HP 滤波 + Zigzag 趋势分段
        alpha_beta:      OLS 回归，返回 AlphaBeta（α 已年化）
        sharpe_ratio:    夏普比率（年化）
        max_drawdown:    最大回撤
        information_ratio: 信息比率（年化）

    Example:
        >>> from qka import Data, Analysis
        >>> data = Data(symbols=['sh.000300'])
        >>> df = data.get()
        >>> analysis = Analysis()
        >>> segs = analysis.zigzag(df['sh.000300|close'], threshold=0.3, min_days=90)
        >>> ab = analysis.alpha_beta(df['sh.000300|returns'].dropna(),
        ...                           df['benchmark|returns'].dropna())
    """

    def zigzag(self, series, threshold=0.3, min_days=90, lamb=1600):
        """
        HP 滤波 + Zigzag 趋势分段。

        对价格序列做 Hodrick–Prescott 滤波去噪，在趋势线上运行 Zigzag 状态机
        识别交替的上行/下行段，短于 min_days 的段被相邻段合并吸收。

        ⚠️ 包含未来函数：
           - HP 滤波是双边滤波，序列末尾新增数据后，末尾段的趋势线可能微调
           - Zigzag 需要后续价格突破 threshold 才能确认当前转折点
           仅供事后分析，禁止用于回测策略。

        Args:
            series: pandas Series，index 为日期（datetime），values 为价格
            threshold: 反转阈值，默认 0.3。峰顶回落 30% 确认顶，谷底反弹 30% 确认底
            min_days: 最小段长（自然日），默认 90。短于此的段被前后段三合一吸收
            lamb: HP 滤波平滑参数，默认 1600（日线数据标准值）

        Returns:
            list[Segment]: 分段列表，按时序排列。每个 Segment 包含：
                - start:  段起始日期（pd.Timestamp）
                - end:    段结束日期（pd.Timestamp）
                - direction:  '上行' 或 '下行'
                - change:  段内涨跌幅（百分比，如 +368.1 或 -57.2）
        """
        if not isinstance(series, pd.Series):
            raise TypeError(f'series 必须是 pandas Series，got {type(series)}')
        if series.empty:
            return []

        close = series.dropna()
        if len(close) < 10:
            raise ValueError(f'数据点不足（{len(close)}），需要至少 10 个点做 HP 滤波')

        # ── HP 滤波 ──
        log_price = np.log(close.values)
        _, trend_log = hpfilter(log_price, lamb=lamb)
        hp_series = pd.Series(np.exp(trend_log), index=close.index)

        # ── Zigzag 状态机 ──
        segments_raw = _zigzag_core(hp_series, threshold)

        # ── 短段合并 ──
        segments = _merge_short_segments(hp_series, segments_raw, min_days)

        return [Segment(s['start'], s['end'], s['dir'], s['chg']) for s in segments]

    def alpha_beta(self, returns, bench_returns, rf=0.0, periods_per_year=252):
        """
        OLS 回归：Rp - Rf = α + β × (Rm - Rf)，返回詹森 α。

        Args:
            returns: array-like，收益率序列（与 periods_per_year 对应频率）
            bench_returns: array-like，基准收益率序列
            rf: 年化无风险利率，默认 0
            periods_per_year: 年化周期数，日线=252，周线=52，月线=12

        Returns:
            AlphaBeta(alpha=float, beta=float)，α 已年化
        """
        rp = np.asarray(returns, dtype=float)
        rm = np.asarray(bench_returns, dtype=float)

        mask = ~(np.isnan(rp) | np.isnan(rm))
        rp, rm = rp[mask], rm[mask]

        if len(rp) < 2:
            return AlphaBeta(alpha=np.nan, beta=np.nan)

        rf_per_period = rf / periods_per_year

        cov = np.cov(rp, rm, ddof=1)
        beta_val = cov[0, 1] / cov[1, 1]
        alpha_val = ((np.mean(rp) - rf_per_period) - beta_val * (np.mean(rm) - rf_per_period)) * periods_per_year

        return AlphaBeta(alpha=alpha_val, beta=beta_val)

    def sharpe_ratio(self, returns, rf=0.0, periods_per_year=252):
        """
        夏普比率（年化）。

        Args:
            returns: array-like，收益率序列（与 periods_per_year 对应频率）
            rf: 年化无风险利率，默认 0
            periods_per_year: 年化周期数，日线=252，周线=52，月线=12

        Returns:
            float
        """
        rp = np.asarray(returns, dtype=float)
        rp = rp[~np.isnan(rp)]

        if len(rp) < 2:
            return np.nan

        rf_per_period = rf / periods_per_year
        excess = np.mean(rp) - rf_per_period
        std = np.std(rp, ddof=1)

        if std == 0:
            return np.nan

        return float(excess / std * np.sqrt(periods_per_year))

    def max_drawdown(self, returns):
        """
        最大回撤。

        Args:
            returns: array-like，日收益率

        Returns:
            float，正数（0.35 = 35% 回撤）
        """
        rp = np.asarray(returns, dtype=float)
        rp = rp[~np.isnan(rp)]

        if len(rp) < 1:
            return np.nan

        equity = np.cumprod(1 + rp)
        running_max = np.maximum.accumulate(equity)
        drawdown = 1 - equity / running_max

        return float(np.max(drawdown))

    def information_ratio(self, returns, bench_returns, periods_per_year=252):
        """
        信息比率（年化）。

        Args:
            returns: array-like，收益率序列
            bench_returns: array-like，基准收益率序列
            periods_per_year: 年化周期数，日线=252，周线=52，月线=12

        Returns:
            float
        """
        rp = np.asarray(returns, dtype=float)
        rm = np.asarray(bench_returns, dtype=float)

        mask = ~(np.isnan(rp) | np.isnan(rm))
        rp, rm = rp[mask], rm[mask]

        if len(rp) < 2:
            return np.nan

        excess = rp - rm
        return float(np.mean(excess) / np.std(excess, ddof=1) * np.sqrt(periods_per_year))


def _zigzag_core(trend_series, threshold):
    """Zigzag 状态机：在趋势线上识别交替的顶和底。"""
    s = trend_series.values
    dates = trend_series.index
    n = len(s)

    # 初始方向：前 60 天涨→找顶，跌→找底
    lookahead = min(60, n // 4)
    looking_for_peak = s[lookahead] > s[0]

    turning_points = []
    extreme_val = s[0]
    extreme_idx = 0

    for i in range(1, n):
        if looking_for_peak:
            if s[i] > extreme_val:
                extreme_val, extreme_idx = s[i], i
            if extreme_idx > 0 and (extreme_val - s[i]) / extreme_val > threshold:
                turning_points.append((extreme_idx, 'peak', extreme_val))
                extreme_val, extreme_idx = s[i], i
                looking_for_peak = False
        else:
            if s[i] < extreme_val:
                extreme_val, extreme_idx = s[i], i
            if extreme_idx > 0 and (s[i] - extreme_val) / extreme_val > threshold:
                turning_points.append((extreme_idx, 'trough', extreme_val))
                extreme_val, extreme_idx = s[i], i
                looking_for_peak = True

    if not turning_points:
        total_chg = (s[-1] - s[0]) / s[0] * 100
        return [{'start': dates[0], 'end': dates[-1],
                 'dir': '上行' if total_chg >= 0 else '下行', 'chg': total_chg,
                 'dur': (dates[-1] - dates[0]).days}]

    # 从转折点构建初始段
    segs = []
    seg_start = 0
    direction = '上行' if turning_points[0][1] == 'peak' else '下行'

    for idx, kind, val in turning_points:
        if idx <= seg_start:
            continue
        dur = (dates[idx] - dates[seg_start]).days
        chg = (val - s[seg_start]) / s[seg_start] * 100
        segs.append({'start': dates[seg_start], 'end': dates[idx],
                     'dir': direction, 'chg': chg, 'dur': dur})
        seg_start = idx
        direction = '下行' if direction == '上行' else '上行'

    if seg_start < n - 1:
        dur = (dates[-1] - dates[seg_start]).days
        chg = (s[-1] - s[seg_start]) / s[seg_start] * 100
        segs.append({'start': dates[seg_start], 'end': dates[-1],
                     'dir': direction, 'chg': chg, 'dur': dur})

    return segs


def _merge_short_segments(trend_series, segs, min_days):
    """合并短于 min_days 的段：与前后段三合一，然后同向段合并。"""
    if min_days <= 0 or not segs:
        return segs

    s = trend_series.values
    dates = trend_series.index

    # 吸收短段
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(segs):
            if segs[i]['dur'] >= min_days:
                i += 1
                continue
            changed = True
            if 0 < i < len(segs) - 1:
                m_start = segs[i - 1]['start']
                m_end = segs[i + 1]['end']
                i_start = segs[i - 1]['start']
            elif i == 0 and len(segs) > 1:
                m_start = segs[i]['start']
                m_end = segs[i + 1]['end']
                i_start = segs[i]['start']
            elif i == len(segs) - 1 and len(segs) > 1:
                m_start = segs[i - 1]['start']
                m_end = segs[i]['end']
                i_start = segs[i - 1]['start']
            else:
                i += 1
                continue

            # 用索引重算涨跌幅，避免价格版本不一致
            start_idx = dates.get_loc(m_start)
            end_idx = dates.get_loc(m_end)
            m_chg = (s[end_idx] - s[start_idx]) / s[start_idx] * 100
            m_dur = (m_end - m_start).days

            del_start = dates.get_loc(i_start)
            segs[i - 1:i + 2] = [{'start': m_start, 'end': m_end,
                                  'dir': '上行' if m_chg >= 0 else '下行',
                                  'chg': m_chg, 'dur': m_dur}]
            i -= 1

    # 合并连续同向段
    i = 1
    while i < len(segs):
        if segs[i]['dir'] == segs[i - 1]['dir']:
            m_start = segs[i - 1]['start']
            m_end = segs[i]['end']
            start_idx = dates.get_loc(m_start)
            end_idx = dates.get_loc(m_end)
            m_chg = (s[end_idx] - s[start_idx]) / s[start_idx] * 100
            m_dur = (m_end - m_start).days
            segs[i - 1:i + 1] = [{'start': m_start, 'end': m_end,
                                  'dir': segs[i - 1]['dir'],
                                  'chg': m_chg, 'dur': m_dur}]
        else:
            i += 1

    return segs
