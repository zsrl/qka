from __future__ import annotations

import contextlib
import hashlib
import inspect
import io
import json
import os
import textwrap
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, List, Optional, Union

import dask.dataframe as dd
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm

from qka.core import indicator, tdx
from qka.core.simulate import Simulate
from qka.utils.logger import logger

from .._common import (
    _QKA_BUILTIN_NAMES, _accepts_rf, _callable_source, _is_qka_factor,
    _key_fingerprint, _rf_given_positionally, get_tickflow_api_key,
)


class SimMixin:
    def _trading_index(self, start_date: str, end_date: str) -> pd.DatetimeIndex:
        """
        取 [start_date, end_date] 内的真实交易日，作为模拟行情的日期轴。

        数据来自 baostock 的交易日历接口 query_trade_dates，故调用方需已登录。

        Args:
            start_date / end_date: 'YYYY-MM-DD'

        Returns:
            pd.DatetimeIndex，名称 'date'（与真实缓存 parquet 的索引名一致）

        Raises:
            RuntimeError: baostock 查询失败，或区间内一个交易日都没有
        """
        rs = bs.query_trade_dates(start_date=start_date, end_date=end_date)
        if rs.error_code != '0':
            raise RuntimeError(
                f"获取交易日历失败（{start_date} ~ {end_date}）: "
                f"[{rs.error_code}] {rs.error_msg}"
            )
        dates = []
        while rs.next():
            calendar_date, is_trading_day = rs.get_row_data()
            if is_trading_day == '1':
                dates.append(calendar_date)
        if not dates:
            raise RuntimeError(
                f"区间内没有交易日: {start_date} ~ {end_date}，请检查日期范围"
            )
        idx = pd.DatetimeIndex(pd.to_datetime(dates), name='date')
        return idx


    def _generate_symbol(self, symbol: str, idx: pd.DatetimeIndex) -> pd.DataFrame:
        """
        生成一只模拟标的的行情数据（纯内存，不走缓存、不下载）。

        对数价格按「带趋势的均值回复」演化：
            r_t = drift + reversion * (logAnchor - logP_{t-1}) + vol * eps_t
        eps_t ~ N(0, 1)。drift=0 且 reversion=0 时退化为纯随机游走。

        Args:
            symbol: Simulate 标的的代码
            idx: 日期轴（真实交易日，取自 _trading_index）

        Returns:
            pd.DataFrame，索引即 idx，含 6 个基础列，
            并按 self.extra_fields 追加扩展列 —— 与真实数据源行为一致（不给就不生成）。
        """
        spec = self._sim_specs[symbol]
        drift, reversion, vol = spec.drift, spec.reversion, spec.vol

        bars = len(idx)
        rng = np.random.default_rng()   # 每次新建 ⇒ 每次调用都是新行情

        # 1. 对数价格路径（锚点固定在起点价上，保证「震荡」真是围着起点来回）
        log_p = np.empty(bars)
        log_p[0] = np.log(self.SIM_START_PRICE)
        anchor = log_p[0]
        eps = rng.standard_normal(bars)
        for t in range(1, bars):
            log_p[t] = log_p[t - 1] + drift + reversion * (anchor - log_p[t - 1]) + vol * eps[t]
        close = np.exp(log_p)

        # 2. 涨跌停截断（相对前收），避免造出真实市场不会有的单日暴涨
        step_ret = np.clip(np.diff(close) / close[:-1], -self.SIM_LIMIT, self.SIM_LIMIT)
        close = np.concatenate([[close[0]], close[0] * np.cumprod(1.0 + step_ret)])

        # 3. OHLC：保证 high >= max(open, close)、low <= min(open, close)
        preclose = np.concatenate([[close[0]], close[:-1]])
        open_ = preclose * (1.0 + rng.normal(0.0, 0.002, bars))
        high = np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0.0, 0.003, bars)))
        low = np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0.0, 0.003, bars)))

        volume = rng.integers(1_000_000, 5_000_000, bars).astype(float)
        df = pd.DataFrame({
            'open': open_, 'high': high, 'low': low, 'close': close,
            'volume': volume, 'amount': volume * close,
        }, index=idx)

        # 4. 扩展列：只生成请求的字段（与真实源「不给就没有」一致）
        # 用「调用方原始请求」而非 self.extra_fields —— 模拟数据由 qka 现场生成，
        # 不依赖任何外部源，故不受数据源的扩展字段能力限制
        log_ratio = np.log(close / close[0])
        for field in self._requested_extra_fields:
            if field == 'preclose':
                df[field] = preclose
            elif field == 'pctChg':
                df[field] = (close / preclose - 1.0) * 100.0
            elif field == 'tradestatus':
                df[field] = 1
            elif field == 'isST':
                df[field] = 0
            elif field == 'turn':
                df[field] = np.abs(rng.normal(2.0, 0.6, bars))
            elif field in self.SIM_EXTRA_BASE:
                base, elasticity, idio_std = self.SIM_EXTRA_BASE[field]
                # 估值 = 基准值 × 价格弹性项 × 基本面自身波动项
                df[field] = base * np.exp(
                    elasticity * log_ratio
                    + self._sim_fundamental_walk(rng, bars, idio_std)
                )
        return df


    def _sim_fundamental_walk(self, rng, bars: int, idio_std: float) -> np.ndarray:
        """
        生成一条「基本面」对数扰动序列（OU 均值回复过程）。

        为什么需要它：真实世界里 PE = 市值 / 净利润，净利润是**独立于价格**演化
        的慢变量，所以真实估值与股价并不同步（实测长江电力 corr(peTTM, close)
        ≈ -0.09）。若估值列直接写成价格的等比缩放，该相关系数会逼近 +1，
        「低 PE 买入」这类策略在模拟数据上会被等价测成「价格策略」，语义失真。

        模型：z_t = phi * z_{t-1} + sigma * eps_t
        取 sigma = idio_std * sqrt(1 - phi^2) ⇒ 稳态标准差恰为 idio_std，
        故入参语义就是「估值对数偏离的量级」，可直接与真实数据对照。

        Args:
            rng: numpy Generator
            bars: 生成长度
            idio_std: 基本面自身的稳态对数波动

        Returns:
            np.ndarray，形状 (bars,)，z[0] = 0（对齐基准值起点）
        """
        phi = self.SIM_FUND_PHI
        sigma = idio_std * np.sqrt(1.0 - phi * phi)
        z = np.empty(bars)
        z[0] = 0.0
        eps = rng.standard_normal(bars)
        for t in range(1, bars):
            z[t] = phi * z[t - 1] + sigma * eps[t]
        return z

