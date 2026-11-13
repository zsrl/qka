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


class BaostockMixin:
    def _get_from_baostock(
        self, symbol: str,
        start_date: str = '1990-01-01',
        end_date: str = '2050-12-31',
        extra_fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        从 baostock 获取单个股票的数据。

        Args:
            symbol: 标的代码，任意写法（600519.SH 或 sh.600519），内部统一转换
            start_date: 起始日期，格式 YYYY-MM-DD，默认 1990-01-01
            end_date: 截止日期，格式 YYYY-MM-DD，默认 2050-12-31
            extra_fields: 本次请求的扩展字段列表。None 时使用 self.extra_fields；
                调用方（_download）可传入"当前配置 ∪ 缓存已有列"的并集，保证列只增不减

        Returns:
            pd.DataFrame: 股票数据，以 date 为索引，包含 open, high, low, close, volume, amount
            及 extra_fields 指定的扩展列（如有）
        """
        # adjustflag: 1=不复权, 2=前复权, 3=后复权
        adjust_map = {'bfq': '1', 'qfq': '2', 'hfq': '3'}
        adjustflag = adjust_map.get(self.adjust, '2')

        # 基础字段 + extra_fields 扩展字段（缺省用 self.extra_fields）
        extra = list(extra_fields) if extra_fields is not None else self.extra_fields
        fields = ",".join(["date"] + self.BAOSTOCK_BASE_FIELDS + extra)

        # baostock 只认 sh.600519 写法 ⇒ 无论调用方用哪种写法都统一转换
        bs_symbol = self.to_baostock_symbol(symbol)

        rs = bs.query_history_k_data_plus(
            bs_symbol,
            fields,
            start_date=start_date,
            end_date=end_date,
            frequency='d',
            adjustflag=adjustflag,
        )
        if rs.error_code != '0':
            raise RuntimeError(f"baostock 查询 {symbol}({bs_symbol}) 失败: {rs.error_msg}")
        # 官网标准写法：get_row_data() 逐行取 + next() 翻页，避免 get_data() 的 df.append()
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        df = pd.DataFrame(data_list, columns=rs.fields) if data_list else pd.DataFrame()

        if len(df) == 0:
            return df

        # baostock 返回的数值列是字符串，转数值类型（基础列 + 本次请求的扩展字段）
        numeric_cols = self.BAOSTOCK_BASE_FIELDS + extra
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        return df

    # ── 取数分发 ────────────────────────────────────────────────

