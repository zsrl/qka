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


class TdxMixin:
    def _get_from_tdx(
        self, symbol: str,
        start_date: str = '1990-01-01',
        end_date: str = '2050-12-31',
        extra_fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        从本机「支持 TQ 策略」的通达信客户端获取单只标的的日线数据。

        返回结构与 _get_from_baostock 一致（date 索引 + open/high/low/close/
        volume/amount），两处口径在本源内直接对齐：
        - **volume**：通达信给的就是「股」，与 baostock 口径一致，原样使用
        - **amount**：通达信单位是「万元」，×10000 换算成「元」

        复权由通达信自己按 dividend_type 算好（front=前复权 / back=后复权 /
        none=不复权），本处只做口径映射，不自行计算复权。

        取数前必须先 ``refresh_kline``：通达信本地只存「下载过」的 K 线，直接查
        没下载过的标的只会得到最新一根（历史静默缺失）。refresh_kline 让客户端
        把该标的的 K 线补齐，本地已有时也会很快返回。

        extra_fields 对通达信行情无意义（当前仅接行情，无扩展列），此处不处理。
        """
        # 周期映射（当前仅日线）
        period_map = {'1d': '1d'}
        if self.period not in period_map:
            raise RuntimeError(
                f"tdx 源暂不支持周期 {self.period!r}（可选: {list(period_map)}）"
            )

        # 复权映射：通达信 front=前复权 / back=后复权 / none=不复权
        adjust_map = {'bfq': 'none', 'qfq': 'front', 'hfq': 'back'}
        dividend_type = adjust_map.get(self.adjust, 'front')

        tdx_symbol = self.to_tdx_symbol(symbol)
        tq = tdx.get_tq()

        # 通达信只认 YYYYMMDD
        start = pd.Timestamp(start_date).strftime('%Y%m%d')
        end = pd.Timestamp(end_date).strftime('%Y%m%d')

        # 先让客户端补齐该标的的 K 线（失败返回 None），否则历史会静默缺失
        if tq.refresh_kline(stock_list=[tdx_symbol],
                            period=period_map[self.period]) is None:
            raise RuntimeError(
                f"通达信刷新 K 线缓存失败（{tdx_symbol}）："
                "请确认「TQ 版通达信」客户端已启动并已登录。"
            )

        try:
            raw = tq.get_market_data(
                stock_list=[tdx_symbol],
                start_time=start,
                end_time=end,
                dividend_type=dividend_type,
                period=period_map[self.period],
            )
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"通达信查询 {symbol}({tdx_symbol}) 失败: {e}") from e

        # 无任何数据时返回空 dict
        if not raw:
            return pd.DataFrame()

        # 每张字段表都是「日期为索引、列为代码」的宽表，只取当前这一列
        cols = {}
        for src, dst in self.TDX_FIELD_MAP.items():
            tbl = raw.get(src)
            if tbl is None or tdx_symbol not in getattr(tbl, 'columns', []):
                return pd.DataFrame()
            cols[dst] = tbl[tdx_symbol]

        df = pd.DataFrame(cols)
        df.index = pd.DatetimeIndex(df.index)
        df.index.name = 'date'
        df['amount'] = df['amount'] * 10000            # 万元 → 元
        df = df[df['close'].notna()]                   # 去掉多标的并集索引带出的空行
        df = df[~df.index.duplicated(keep='last')].sort_index()
        for col in self.BAOSTOCK_BASE_FIELDS:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
