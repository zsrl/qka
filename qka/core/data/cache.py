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

from ._common import (
    _QKA_BUILTIN_NAMES, _accepts_rf, _callable_source, _is_qka_factor,
    _key_fingerprint, _rf_given_positionally, get_tickflow_api_key,
)


class CacheMixin:
    def _read_verified_from(self, path: Path):
        """读「已确认起点」；没有记录（老缓存）返回 None"""
        try:
            meta = pq.read_schema(path).metadata or {}
        except Exception:
            return None
        raw = meta.get(self.VERIFIED_FROM_KEY)
        if not raw:
            return None
        try:
            return pd.Timestamp(raw.decode())
        except Exception:
            return None


    def _write_verified_from(self, path: Path, table: pa.Table, verified_from) -> None:
        """把「已确认起点」写进 parquet 元数据后落盘（数据本身原样保留）"""
        meta = dict(table.schema.metadata or {})
        meta[self.VERIFIED_FROM_KEY] = verified_from.strftime('%Y-%m-%d').encode()
        pq.write_table(table.replace_schema_metadata(meta), path)


    def _cache_missing_extra_fields(self, path: Path) -> bool:
        """检查已有 parquet 缓存是否缺少 extra_fields 指定的列。"""
        if not self.extra_fields or not path.exists():
            return False
        try:
            cols = set(pq.read_schema(path).names)
        except Exception:
            return True
        return any(f not in cols for f in self.extra_fields)


    def _extra_fields_whitelist(self, source: str) -> List[str]:
        """该数据源实际支持的扩展字段（源能力不同，按源过滤）。"""
        if source == 'baostock':
            return self.BAOSTOCK_EXTRA_FIELDS
        if source == 'tdx':
            return self.TDX_EXTRA_FIELDS
        return self.TICKFLOW_EXTRA_FIELDS


    def _merged_extra_fields(self, path: Path) -> List[str]:
        """
        计算本次下载实际请求的扩展字段：当前 extra_fields 与缓存已有扩展列的并集。

        保证同一 datadir 下不同 extra_fields 配置共享缓存时，列只增不减、
        不互相覆盖（第一次只有 peTTM，第二次再加 pbMRQ 时 peTTM 仍保留）。
        """
        merged = list(self.extra_fields)
        if not path.exists():
            return merged
        try:
            existing = set(pq.read_schema(path).names)
        except Exception:
            return merged
        whitelist = self._extra_fields_whitelist(self.source)
        for f in whitelist:
            if f in existing and f not in merged:
                merged.append(f)
        return merged


    def _append_bars(self, symbol: str, bars: pd.DataFrame):
        """把新日期的行情追加进这只票的缓存，返回新增天数（None = 缓存不存在）。

        🚨 只追加缓存里**没有的日期**，历史行一个不动。
        🚨 新行的因子列留空（NaN），由之后 cache_only 的因子补算填上；
           列结构与 dtype 必须与缓存完全一致，否则 qka 读回来会错列。
        🚨 必须保留原有 parquet 元数据（因子列登记 / 已确认起点），否则下次
           `_restore_factor_columns` 认不出哪些列是因子，增量会把因子抹掉。
        """
        path = self.target_dir / f"{symbol}.parquet"
        if not path.exists():
            return None

        existing = pd.read_parquet(path)
        if not isinstance(existing.index, pd.DatetimeIndex):
            existing.index = pd.to_datetime(existing.index)
        new_rows = bars[bars.index > existing.index.max()]
        if new_rows.empty:
            return 0

        # 按缓存的列顺序造新行：行情列有值，其余（因子等派生列）留空
        add = pd.DataFrame(
            {c: (new_rows[c].to_numpy() if c in new_rows.columns else np.nan)
             for c in existing.columns},
            index=new_rows.index,
        )
        for col, dt in existing.dtypes.items():
            try:
                add[col] = add[col].astype(dt)
            except (ValueError, TypeError):
                pass

        combined = pd.concat([existing, add]).sort_index()
        combined.index.name = existing.index.name or 'date'
        # 因子列是派生数据，合并后补回旧值（口径同 _download 的增量段）
        combined = self._restore_factor_columns(combined, existing, path)

        table = pa.Table.from_pandas(combined)
        old_meta = dict(pq.read_schema(path).metadata or {})
        if old_meta:
            table = table.replace_schema_metadata(
                {**old_meta, **(table.schema.metadata or {})})
        pq.write_table(table, path)
        return len(add)


    def _rewrite_full(
        self, path: Path, symbol: str,
        download_start: str = None, download_end: str = None,
        extra_fields: Optional[List[str]] = None,
    ) -> Path:
        """整段重取并覆盖缓存（供不允许增量缓存的复权方式使用）。

        为什么要盖住缓存已存的整段：只下「请求范围」会把长历史截短；只补缺口又会
        留下范围外的老口径数据 —— 那也是缝。所以范围取「缓存已有范围 ∪ 请求范围」，
        重取回来的整段是同一个口径，整体替换。

        Args:
            path: 缓存文件路径
            symbol: 标的代码
            download_start / download_end: 本次请求范围（None 表示不设边界）
            extra_fields: 本次要请求的扩展字段

        Returns:
            Path: 数据文件路径

        Raises:
            RuntimeError: 数据源返回空数据（此时保留原缓存，绝不拿空数据覆盖）
        """
        existing = pd.read_parquet(path)
        cache_min = existing.index.min()
        cache_max = existing.index.max()

        req_start = pd.Timestamp(download_start) if download_start else None
        req_end = (pd.Timestamp(download_end) if download_end
                   else pd.Timestamp.now().floor('D'))

        range_start = min(x for x in (cache_min, req_start) if x is not None)
        range_end = max(cache_max, req_end)

        df = self._fetch(
            symbol,
            start_date=range_start.strftime('%Y-%m-%d'),
            end_date=range_end.strftime('%Y-%m-%d'),
            extra_fields=extra_fields,
        )
        if len(df) == 0:
            raise RuntimeError(
                f"{symbol}: 数据源（{self.source}）返回空数据，已保留原缓存"
            )
        # 这次就是从这个起点问的，一并记下「已确认起点」
        self._write_verified_from(path, pa.Table.from_pandas(df), range_start)
        return path


    def _strip_factor_cols(self, df, path):
        """从一只票的行情里剔掉「缓存的因子列」。

        因子现在存在行情文件里，读行情时会被一起读进来 —— 但那些是缓存产物，
        不属于行情这一层。不剔的后果：
          ① 白读一遍用不上的列；
          ② 本次没请求的因子也会混进返回结果（缓存里有几个就带几个）；
          ③ 后面拼装时会和新算出来的同名列撞上。

        要剔的是「文件里登记过的**全部**因子列」，不是本次请求的那几个 ——
        否则上轮缓存的因子会漏进结果。因子列名从文件元数据取（那是唯一可靠的
        来源）。

        dask 的 drop 是纯元数据操作，不会真去读数据。
        """
        drop = set()
        try:
            raw = (pq.read_schema(path).metadata or {}).get(self.FACTOR_META_KEY)
            metas = json.loads(raw.decode()) if raw else {}
            if isinstance(metas, dict) and 'fingerprint' not in metas:
                drop |= set(metas)
        except Exception:
            pass
        if isinstance(self._factors, dict):
            drop |= set(self._factors)
        drop = [c for c in df.columns if c in drop]
        return df.drop(columns=drop) if drop else df


    def _restore_factor_columns(self, combined, existing, path):
        """把因子列（派生数据）的旧值补回增量合并结果。

        「哪些列是因子」以文件元数据里登记的为准 —— 靠列名猜不准，而元数据是
        写因子列时一起写进去的，是唯一可靠来源。
        """
        try:
            raw = (pq.read_schema(path).metadata or {}).get(self.FACTOR_META_KEY)
            metas = json.loads(raw.decode()) if raw else {}
        except Exception:
            return combined
        if not isinstance(metas, dict) or not metas:
            return combined
        cols = [c for c in metas if c in existing.columns and c in combined.columns]
        if not cols:
            return combined
        combined[cols] = combined[cols].combine_first(
            existing[cols].reindex(combined.index))
        return combined


    def _quote_cache_path(self, symbol: str) -> Path:
        """行情文件路径 —— 因子现在也写在这里（因子就是行情表的一列）。"""
        return self.target_dir / f'{symbol}.parquet'


    def _load_quote_cached(self, symbol: str):
        """读该票的行情文件（含已有因子列），一次取数流程内只读一次。

        因子按列存在行情文件里，所以「读因子缓存」和「读行情」是同一个动作。
        逐票的读写次数从「每因子一次」降到「每票一次」。

        Returns:
            (DataFrame 或 None, {因子名: 元数据})
        """
        hit = self._quote_cache.get(symbol)
        if hit is not None:
            return hit

        path = self._quote_cache_path(symbol)
        if not path.exists():
            self._quote_cache[symbol] = (None, {})
            return None, {}

        try:
            df = pd.read_parquet(path)
            raw = (pq.read_schema(path).metadata or {}).get(self.FACTOR_META_KEY)
            metas = json.loads(raw.decode()) if raw else {}
            # 老格式是整个文件记一个 fingerprint（不区分列）。这种记录按列用不了，
            # 视作「该票没有可用的因子记录」，那些因子会按新口径重算一次。
            if not isinstance(metas, dict) or 'fingerprint' in metas:
                metas = {}
        except Exception:
            self._quote_cache[symbol] = (None, {})
            return None, {}

        if not isinstance(df.index, pd.DatetimeIndex):
            self._quote_cache[symbol] = (None, {})
            return None, {}

        self._quote_cache[symbol] = (df, metas)
        return df, metas


    def _read_factor_cache(self, name, symbol, fingerprint):
        """从行情文件里取该因子那一列；列不在 / 指纹不符 / 读不出来 → None。

        不在这里判断「盖没盖住范围」——那是 `_recompute_target` 的事：
        盖住了就一个字不算，只缺尾巴就只补尾巴。
        """
        df, metas = self._load_quote_cached(symbol)
        if df is None or name not in df.columns:
            return None
        if (metas.get(name) or {}).get('fp') != fingerprint:
            return None
        return df[name]


    def _flush_factor_columns(self, pending) -> None:
        """把这一轮新算出来的因子列并回行情文件，**每票只写一次**。

        pending = {symbol: {因子名: (序列, 指纹)}}

        必须攒够再写：parquet 不能原地加列，每次写都是整文件重写。若沿用旧的
        「算一个因子写一次」，32 个因子就要把同一只票的文件读写 32 遍 ——
        7819 只票累计几百 GB 的无效 IO。
        """
        for symbol, cols in pending.items():
            if not cols:
                continue
            df, metas = self._load_quote_cached(symbol)
            if df is None:
                continue

            out = df.copy()
            new_metas = dict(metas)
            wrote = False
            for name, (series, fp) in cols.items():
                if series is None or series.empty:
                    continue
                # series 覆盖的是「宽表的日期轴」，裁到该票自己的日期上再落盘
                out[name] = series.reindex(out.index)
                new_metas[name] = {'fp': fp, 'v': self.FACTOR_CACHE_VERSION}
                wrote = True
            if not wrote:
                continue

            path = self._quote_cache_path(symbol)
            table = pa.Table.from_pandas(out)
            meta = dict(table.schema.metadata or {})
            meta[self.FACTOR_META_KEY] = json.dumps(
                new_metas, ensure_ascii=False).encode()
            pq.write_table(table.replace_schema_metadata(meta), path)
            self._quote_cache[symbol] = (out, new_metas)

