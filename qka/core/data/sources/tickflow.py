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


class TickflowMixin:
    @classmethod
    def _reset_tickflow_clients(cls):
        """丢掉已建好的 tickflow 客户端，下次按当前 key 重建。

        由 `set_tickflow_api_key()` 调用：客户端一旦建好就缓存住，不清的话
        「先建了免费档客户端、后设 key」会静默继续走免费档。
        """
        with cls._tf_client_lock:
            cls._tf_clients.clear()

    @classmethod

    @classmethod
    def _tickflow_client(cls):
        """惰性创建并复用 TickFlow 客户端。

        有 key 走完整服务（api.tickflow.org），没有就走免费档
        （free-api.tickflow.org）。key 是**建客户端这一刻**现取的，
        所以设 key 的时机不必早于 import（见 `set_tickflow_api_key`）。
        """
        key = get_tickflow_api_key()
        cache_key = _key_fingerprint(key)
        client = cls._tf_clients.get(cache_key)
        if client is None:
            with cls._tf_client_lock:
                client = cls._tf_clients.get(cache_key)
                if client is None:
                    from tickflow import TickFlow
                    # free() 会往 stdout 打一段带 emoji 的「免费档」说明。
                    # stdout 被重定向到文件、且编码非 UTF-8 时（如打包版把后端输出
                    # 写入 GBK 日志），print emoji 会抛 UnicodeEncodeError 而中断下载，
                    # 故创建期间丢弃其标准输出。（redirect_stdout 改的是全局 sys.stdout，
                    # 并发首次创建会互相覆盖，故用锁串行化。）
                    with contextlib.redirect_stdout(io.StringIO()):
                        client = TickFlow(api_key=key) if key else TickFlow.free()
                    cls._tf_clients[cache_key] = client
        return client

    @staticmethod

    def _get_from_tickflow(
        self, symbol: str,
        start_date: str = '1990-01-01',
        end_date: str = '2050-12-31',
        extra_fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        从 TickFlow 获取单只标的的日线数据。

        返回结构与 _get_from_baostock 一致（date 索引 + open/high/low/close/
        volume/amount），但有两处口径必须转换：
        - **volume**：TickFlow 单位为「手」，×100 换算成 baostock 口径的「股」
        - **timestamp**：TickFlow 给的是「北京时间当天零点」对应的 UTC 毫秒，
          需 +8 小时还原为北京日期，否则日期整体偏一天

        extra_fields 对 TickFlow 无意义（其历史日线不含扩展列），此处不处理。
        """
        # 周期映射（当前仅日/周/月线；分钟线 TickFlow 属付费能力，未接）
        period_map = {'1d': '1d', '1w': '1w', '1M': '1M'}
        if self.period not in period_map:
            raise RuntimeError(
                f"tickflow 源暂不支持周期 {self.period!r}（可选: {list(period_map)}）"
            )
        period = period_map[self.period]

        # 复权映射：tickflow forward=前复权 / backward=后复权 / none=不复权
        adjust_map = {'bfq': 'none', 'qfq': 'forward', 'hfq': 'backward'}
        adjust = adjust_map.get(self.adjust, 'forward')

        tf_symbol = self.to_tickflow_symbol(symbol)

        # 日期 → 毫秒时间戳（右端 +1 天，保证 end_date 当天落在闭区间内）
        start_ms = int(pd.Timestamp(start_date).timestamp() * 1000)
        end_ms = int((pd.Timestamp(end_date) + pd.Timedelta(days=1)).timestamp() * 1000)

        client = self._tickflow_client()
        try:
            data = client.klines.get(
                tf_symbol,
                period=period,
                # count 必须显式给足：TickFlow 默认只返回最近 100 条，
                # 不给会静默截断长区间（全历史会只剩最近 100 个交易日）
                count=10000,
                start_time=start_ms,
                end_time=end_ms,
                adjust=adjust,
            )
        except Exception as e:
            raise RuntimeError(f"tickflow 查询 {symbol}({tf_symbol}) 失败: {e}")

        ts = (data or {}).get('timestamp')
        if not ts:
            return pd.DataFrame()

        # UTC 毫秒 → 北京日期（当天零点）
        idx = (pd.to_datetime(pd.Series(ts), unit='ms')
               + pd.Timedelta(hours=8)).dt.normalize()
        idx.name = 'date'

        df = pd.DataFrame({
            'open': data['open'],
            'high': data['high'],
            'low': data['low'],
            'close': data['close'],
            'volume': [v * 100 for v in data['volume']],   # 手 → 股
            'amount': data['amount'],
        }, index=idx)

        for col in self.BAOSTOCK_BASE_FIELDS:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df


    def _get_many_from_tickflow(
        self, symbols: List[str], start_date: str, end_date: str,
        batch_size: int = 100, max_workers: int = 4,
    ) -> dict:
        """从 TickFlow **一次取回多只**标的的日线（按日期区间，不是按条数）。

        单只走 `_get_from_tickflow`，一只一个请求；全市场 7500 只就是 7500 次，
        受限流约束要几小时。TickFlow 的 klines.batch 会把它们按 batch_size 切块、
        用 max_workers 个并发发出去，几十次请求几分钟就够。

        返回结构与 `_get_from_tickflow` 完全一致（date 索引 + OHLCV/amount），
        口径转换也一致：
        - **volume**：TickFlow 是「手」，×100 换成「股」
        - **timestamp**：北京时间零点的 UTC 表示，要换到上海时区再取日期

        Args:
            symbols: 标的列表（「代码.市场」或 sh.600519 均可）
            start_date / end_date: 要取的日期区间（含两端）。这个区间由调用方
                按「缓存缺到哪」算出来，不在这里拍一个条数。
            batch_size: 一次请求塞多少只（接口按 URL 长度自己切块）
            max_workers: SDK 内部一次并发几个请求（这是 SDK 参数，
                不是业务层开线程池）

        Returns:
            dict: {原始代码: DataFrame}。**取不到的标的不在字典里**（停牌 /
                  退市 / 新代码），由调用方决定怎么处理。
        """
        period_map = {'1d': '1d', '1w': '1w', '1M': '1M'}
        if self.period not in period_map:
            raise RuntimeError(
                f"批量取数暂不支持周期 {self.period!r}（可选: {list(period_map)}）"
            )
        adjust_map = {'bfq': 'none', 'qfq': 'forward', 'hfq': 'backward'}
        adjust = adjust_map.get(self.adjust, 'forward')

        # 日期 → 毫秒时间戳（右端 +1 天，保证 end_date 当天落在闭区间内）
        start_ms = int(pd.Timestamp(start_date).timestamp() * 1000)
        end_ms = int((pd.Timestamp(end_date) + pd.Timedelta(days=1)).timestamp() * 1000)

        # 原代码 ↔ tickflow 代码互转：batch 用它自己那套做 key，要能映射回来
        tf_of = {self.to_tickflow_symbol(s): s for s in symbols}
        client = self._tickflow_client()
        try:
            res = client.klines.batch(
                list(tf_of),
                period=period_map[self.period],
                adjust=adjust,
                # count 与区间一起给：只给区间的话服务端默认只回最近 100 条，
                # 会把长区间静默截断（单只 _get_from_tickflow 踩过同一个坑）
                count=10000,
                start_time=start_ms,
                end_time=end_ms,
                batch_size=batch_size,
                max_workers=max_workers,
            )
        except Exception as e:
            raise RuntimeError(f"tickflow 批量取数失败: {e}")

        out = {}
        for tf_sym, d in (res or {}).items():
            sym = tf_of.get(tf_sym)
            if sym is None or not d or not d.get('timestamp'):
                continue
            idx = (pd.to_datetime(pd.Series(d['timestamp']), unit='ms', utc=True)
                   .dt.tz_convert('Asia/Shanghai')
                   .dt.normalize()
                   .dt.tz_localize(None))
            idx.name = 'date'
            df = pd.DataFrame({
                'open': d['open'],
                'high': d['high'],
                'low': d['low'],
                'close': d['close'],
                'volume': [v * 100 for v in d['volume']],   # 手 → 股
                'amount': d['amount'],
            }, index=idx)
            for col in self.BAOSTOCK_BASE_FIELDS:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df = df[~df.index.duplicated(keep='last')].sort_index()
            out[sym] = df
        return out

    # ── 通达信数据源（本机 TQ 版客户端，仅 Windows）────────────────

    # 通达信 get_market_data 字段名 → qka 标准列名
    TDX_FIELD_MAP = {
        'Open': 'open', 'High': 'high', 'Low': 'low',
        'Close': 'close', 'Volume': 'volume', 'Amount': 'amount',
    }

