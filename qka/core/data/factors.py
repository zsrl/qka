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


class FactorMixin:
    def _add_benchmark(self, df, target_dir, pq_filters):
        """将基准数据的 returns 以 benchmark| 前缀追加到 DataFrame。"""
        bench_path = target_dir / f"{self.benchmark}.parquet"
        if not bench_path.exists():
            logger.warning(f"基准数据文件不存在: {bench_path}")
            return df
        bench_df = pd.read_parquet(bench_path, filters=pq_filters)
        bench_df['returns'] = bench_df['close'].diff() / bench_df['close'].shift(1)
        # 基准同样掐头：规则对所有序列一视同仁（"来啥废啥"，不猜哪天上市）
        if self.drop_head > 0:
            if len(bench_df) > self.drop_head:
                cutoff = bench_df.index[self.drop_head - 1]
                bench_df['returns'] = bench_df['returns'].where(bench_df.index > cutoff)
            else:
                bench_df['returns'] = np.nan
        bench_returns = bench_df['returns'].rename('benchmark|returns')

        if isinstance(df, dd.DataFrame):
            # dask: 用 assign 加列，pandas Series 会自动对齐分区
            return df.assign(**{'benchmark|returns': bench_returns})
        else:
            df['benchmark|returns'] = bench_returns.reindex(df.index)
            return df


    def _drop_head_returns(self, result):
        """掐头（默认路径用）：每条序列的前 drop_head 根，returns 记空。

        语义是「来啥废啥」—— 不猜哪天上市、不做探测：取回来的数据，开头 N 根
        一律当垫场。调用方把 start 传在上市日，N 根垫场就正好是「上市后前 N 个
        交易日」；start 传得更晚，也只是白掐 20 根（少 20 个样本），数值永远是对的。

        为什么放在停牌补齐之后：补齐会按补好的 close 重算 returns，先掐会被洗回来。

        定位"一只票自己的前 N 根"：按 close 非空计数（宽表里上市前的行 close 是
        空的，不算数）；基准列没有 close，退而按 returns 自身的非空值计数。
        """
        if self.drop_head <= 0:
            return result
        for col in [c for c in result.columns if c.endswith('|returns')]:
            base = col[:-len('|returns')]
            close_col = result[f'{base}|close'] if f'{base}|close' in result.columns else None
            counter = close_col if close_col is not None else result[col]
            head = counter.notna().cumsum() <= self.drop_head
            result.loc[head, col] = np.nan
        return result


    def _drop_head_lazy(self, ddf):
        """掐头（懒加载路径用）：单票自己的序列，前 drop_head 根 returns 记空。

        懒加载时每只票还是独立的 dask 帧（尚未拼宽表），帧的开头就是它自己的头。
        用「第 N 个索引标签」做切点：比它晚的行保留，早的（含第 N 根）记空。
        """
        if self.drop_head <= 0:
            return ddf
        # 注意：dask 的 .head(n) 本身就会触发计算、返回 pandas 对象，
        # 后面不能再 .compute()（会 AttributeError）。Backtest 走的正是 lazy 路径。
        labels = ddf.index.to_series().head(self.drop_head)
        if labels.empty:
            return ddf
        if len(labels) < self.drop_head:
            # 序列总共不到 N 根：整条记空
            return ddf.map_partitions(lambda part: part.assign(returns=np.nan))
        cutoff = labels.iloc[-1]
        return ddf.map_partitions(
            lambda part: part.assign(returns=part['returns'].where(part.index > cutoff))
        )


    def _all_factors_with_cache(self, result):
        """算所有因子 —— 内置 / ta / 自定义，**同一处、同一时机**（基准注入之后）。

        缓存仍按因子粒度分两笔账（内置走 `_qka_factors_with_cache`，其余走
        `_factors_with_cache`），但它们是同一个阶段的两笔账，不是两条路径：
        两者都在基准注入之后执行，都能看到基准。

        🚨 为什么必须有基准之后才算：因子可能定义成「相对大盘」的量（β、残差波动、
           相关系数…）。内置的和自定义的在这个问题上没有任何区别 —— 所以不存在
           「自定义因子先算一遍、内置因子后算一遍」这种分法。
        """
        if not self._factors:
            return result
        result = self._factors_with_cache(result)
        result = self._qka_factors_with_cache(result)
        return result


    def _apply_all_factors(self, df):
        """所有因子一处算（无缓存路径；懒加载 / dask 走这里）。df 已含基准。"""
        inds = self._factors
        if not inds:
            return df
        if callable(inds):
            # 旧版整表函数形式：直接把整表交给它
            if isinstance(df, dd.DataFrame):
                return df.map_partitions(lambda p: inds(p.copy()))
            return inds(df.copy())
        if isinstance(df, dd.DataFrame):
            sample = df.head(self._min_rows_for_factors())
            meta = self._compute_all_factor_cols(sample.copy())
            return df.map_partitions(
                lambda p: self._compute_all_factor_cols(p.copy()), meta=meta)
        return self._compute_all_factor_cols(df.copy())


    def _compute_all_factor_cols(self, df, only=None):
        """逐票把该票的全部因子算出来，写回 `{symbol}|{因子}` 列。

        🚨 内置指标和自定义因子在这里没有区别：都是「拿这只票的数据，吐一列」。
           差别只有函数从哪来 —— 内置的从 qka.core.indicator 取，自定义的是传进来的
           函数对象，ta 的是从 `ta.xxx.yyy` 这个路径 import 出来的。
        """
        if not isinstance(self._factors, dict):
            return df
        col_index = self._columns_by_symbol(df.columns)
        has_bench = 'benchmark|returns' in df.columns

        for symbol in self.symbols:
            cols = col_index.get(symbol)
            if not cols:
                continue
            plain = self._symbol_slice(df, symbol, cols)
            if plain.empty:
                continue
            # 基准给到自定义因子时叫 bench —— 与内置看到的 benchmark|returns 同源同值
            if has_bench:
                plain['bench'] = df['benchmark|returns'].reindex(plain.index)

            for name, spec in self._factors.items():
                if only is not None and name not in only:
                    continue
                series = self._one_factor(plain, symbol, name, spec)
                if series is not None:
                    df[f'{symbol}|{name}'] = series.reindex(df.index)
        return df


    def _one_factor(self, plain, symbol, name, spec):
        """算单个因子。返回一列 Series，认不出/算失败返回 None。

        plain: 这只票的表，列名**已去前缀**（open/high/low/close/volume/amount/returns），
               外加一列 bench（基准收益，有基准时才有）。
        """
        # ① 自定义函数：直接调，它自己决定用不用 bench
        if callable(spec):
            try:
                res = spec(plain)
            except Exception as e:                              # noqa: BLE001
                logger.warning(f'计算 {symbol}|{name} 失败: {type(e).__name__}: {e}')
                return None
            if isinstance(res, pd.DataFrame):
                return res[name] if name in res.columns else None
            return res

        if not isinstance(spec, (list, tuple)) or not spec:
            logger.warning(f'因子 {name} 的定义必须是 tuple 或 callable，跳过')
            return None

        ind_type, args = spec[0], list(spec[1:])

        # ② qka 内置指标：从 indicator 模块取函数，喂「带前缀的小表」
        if _is_qka_factor(ind_type):
            opts = args.pop() if args and isinstance(args[-1], dict) else {}
            lim = opts.get('max_abs_return')
            fn_name = ind_type.split('.', 1)[1] if ind_type.startswith('qka.') else ind_type
            fn = getattr(indicator, fn_name, None)
            if fn is None:
                logger.warning(f'qka 内置指标不存在: {fn_name}，跳过')
                return None
            work = pd.DataFrame({f'{symbol}|returns': plain['returns']})
            if 'bench' in plain.columns:
                work['benchmark|returns'] = plain['bench']
                if lim:
                    for c in work.columns:
                        work[c] = work[c].where(work[c].abs() <= lim)
            rf_kwargs = {}
            if (self.risk_free is not None and _accepts_rf(fn)
                    and not _rf_given_positionally(fn, args)):
                rf_kwargs['rf'] = self.risk_free
            try:
                return fn(work, symbol, *args, **rf_kwargs)
            except ValueError as e:
                logger.warning(f'计算 {symbol}|{name} 失败: {e}')
                return None

        # ③ ta 指标：'ta.trend.sma_indicator' + 列名 + 参数
        cols, rest_start = [], 0
        for i, arg in enumerate(args):
            if isinstance(arg, str):
                cols.append(arg)
                rest_start = i + 1
            else:
                break
        if not cols:
            logger.warning(f'因子 {name} 缺少计算列名，跳过')
            return None
        rest = args[rest_start:]
        if not isinstance(ind_type, str) or '.' not in ind_type:
            logger.warning(f'因子 {name} 的类型必须为 "ta.xxx.yyy" 格式，跳过: {ind_type}')
            return None
        import importlib
        module_name, func_name = ind_type.rsplit('.', 1)
        try:
            fn = getattr(importlib.import_module(module_name), func_name)
        except (ImportError, AttributeError) as e:
            logger.warning(f'无法加载指标函数 {ind_type}: {e}')
            return None
        try:
            if len(cols) == 1:
                return fn(plain[cols[0]], *rest)
            return fn(*[plain[f] for f in cols], *rest)
        except Exception as e:                                  # noqa: BLE001
            logger.warning(f'计算 {symbol}|{name} 失败: {type(e).__name__}: {e}')
            return None


    def _apply_factors(self, df):
        """
        对单只股票的数据应用预定义的指标/因子。

        支持三种形式：
        - 空 dict → 跳过
        - callable → 旧版 factor 风格，接收 df 返回 df
        - dict → 混合 TA 指标和自定义 callable

        Args:
            df: 单只股票的 DataFrame

        Returns:
            DataFrame: 包含原始列和指标列
        """
        inds = self._factors

        # 空 → 跳过
        if not inds:
            return df

        # 单函数形式（旧版 factor 的替代）
        if callable(inds):
            if isinstance(df, dd.DataFrame):
                return df.map_partitions(lambda p: inds(p.copy()))
            return inds(df.copy())

        # 字典形式
        if isinstance(df, dd.DataFrame):
            # 样本行数完全由 warmup 决定（用户显式声明前置窗口），不写死兜底值。
            # warmup=0 表示用户不预留前置数据，lambda 指标可能因此无法物化——属用户责任。
            sample = df.head(self._min_rows_for_factors())
            meta = self._compute_factor_cols(sample.copy())
            return df.map_partitions(
                lambda partition: self._compute_factor_cols(partition.copy()),
                meta=meta,
            )
        return self._compute_factor_cols(df.copy())


    def _compute_factor_cols(self, df, only=None):
        """在 pandas DataFrame 上计算指标/因子列（单只股票）。

        Args:
            df: 单票 DataFrame
            only: 只算这几个列名（None = 全算）。因子缓存按因子粒度补算时用。
        """

        # 分区过小时跳过，避免 ta-lib 在 dask meta 推断时崩溃。
        # 只补尾巴时这张表必然比「全局最长窗口」短（10 年期 2500、1 年期只要 250），
        # 门槛得按**本次要算的那几个因子**自己的窗口来定，否则 1 年期因子会被
        # 2500 行的全局门槛整个拦掉、算出一片空白（2026-10-21 改）。
        need = 0
        if only:
            for _n in only:
                need = max(need, self._spec_window(self._factors.get(_n)))
        if need <= 0:
            need = self._min_rows_for_factors()
        if len(df) < need:
            return df

        for col_name, spec in self._factors.items():
            if only is not None and col_name not in only:
                continue
            # 自定义因子（callable 值）
            if callable(spec):
                result = spec(df)
                if isinstance(result, pd.DataFrame):
                    # 多列返回 → 逐列添加
                    for c in result.columns:
                        df[c] = result[c]
                else:
                    # 单值返回 → 列名 = key
                    df[col_name] = result
                continue

            # TA 指标（tuple 值）
            if not isinstance(spec, (list, tuple)):
                logger.warning(f"指标 {col_name} 的规格必须为 tuple 或 callable，跳过")
                continue

            ind_type = spec[0]

            # qka 内置指标：跳过，由 _apply_qka_factors 集中处理
            if _is_qka_factor(ind_type):
                continue

            args = list(spec[1:])

            # 收集前面连续的字符串参数作为列名（遇到第一个非字符串即停）
            cols = []
            rest_start = 0
            for i, arg in enumerate(args):
                if isinstance(arg, str):
                    cols.append(arg)
                    rest_start = i + 1
                else:
                    break
            if not cols:
                logger.warning(f"指标 {col_name} 缺少计算列名，跳过")
                continue
            rest = args[rest_start:]

            # 动态解析 ta 函数路径：'ta.trend.sma_indicator' → 导入并调用
            if not isinstance(ind_type, str) or '.' not in ind_type:
                logger.warning(f"指标 {col_name} 的类型必须为 'ta.xxx.yyy' 格式，跳过: {ind_type}")
                continue

            import importlib
            parts = ind_type.rsplit('.', 1)
            if len(parts) != 2:
                logger.warning(f"指标 {col_name} 类型格式错误: {ind_type}")
                continue
            module_name, func_name = parts
            try:
                mod = importlib.import_module(module_name)
                fn = getattr(mod, func_name)
            except (ImportError, AttributeError) as e:
                logger.warning(f"无法加载指标函数 {ind_type}: {e}")
                continue

            if len(cols) == 1:
                df[col_name] = fn(df[cols[0]], *rest)
            else:
                df[col_name] = fn(*[df[f] for f in cols], *rest)

        return df


    def _apply_qka_factors(self, df):
        """应用 qka 内置指标（带 symbol 前缀，含 benchmark 数据）。

        必须在 concat + 加 benchmark 之后调用，此时列名格式为
        {symbol}|returns 和 benchmark|returns。

        Args:
            df: 合并后的 DataFrame（列名已带 symbol 前缀）

        Returns:
            DataFrame: 含 qka 指标列
        """
        inds = self._factors
        if not inds or not isinstance(inds, dict):
            return df

        qka_specs = [
            (col_name, spec) for col_name, spec in inds.items()
            if isinstance(spec, (list, tuple))
            and _is_qka_factor(spec[0])
        ]
        if not qka_specs:
            return df

        if isinstance(df, dd.DataFrame):
            sample = df.head(self._min_rows_for_factors())
            meta = self._compute_qka_factor_cols(sample, qka_specs)
            return df.map_partitions(
                lambda p: self._compute_qka_factor_cols(p, qka_specs),
                meta=meta,
            )
        return self._compute_qka_factor_cols(df, qka_specs)


    def _compute_qka_factor_cols(self, df, qka_specs, symbols=None):
        """在已合并的 DataFrame 上计算 qka 内置指标。

        因子定义的末位可以放一个 dict，作为**这一个因子自己的选项**，
        只作用于它的计算，不影响别人、也不影响原始 returns：
            ('qka.alpha', 250, {'max_abs_return': 0.5})
            超限的那天在因子眼里记空 —— 含这一天的滚动窗口就凑不满样本，
            因子自然算不出来（作废），原始行情和 returns 一个字不动。
        """
        for col_key, spec in qka_specs:
            fn_name = spec[0].split('.', 1)[1] if spec[0].startswith('qka.') else spec[0]
            args = list(spec[1:])
            # 末位 dict = 该因子的选项；不是 dict 就照旧当位置参数传下去
            opts = args.pop() if args and isinstance(args[-1], dict) else {}
            lim = opts.get('max_abs_return')

            try:
                fn = getattr(indicator, fn_name)
            except AttributeError:
                logger.warning(f"qka 内置指标不存在: {fn_name}，跳过")
                continue

            # 无风险利率只发给签名里真有 rf 的指标（α / 夏普）：
            # 其它指标传了关键字参数会直接报 unexpected keyword argument。
            # 因子定义里已经按位置写了 rf 的，以它为准（老的固定写法继续有效）。
            rf_kwargs = {}
            if (self.risk_free is not None and _accepts_rf(fn)
                    and not _rf_given_positionally(fn, args)):
                rf_kwargs['rf'] = self.risk_free

            # 为每只股票计算
            for symbol in (symbols if symbols is not None else self.symbols):
                col = f'{symbol}|{col_key}'
                work = df
                if lim:
                    # 净化副本：只把这只票和基准的涨降幅超限处记空，别的列原样
                    work = df.copy()
                    for c in (f'{symbol}|returns', 'benchmark|returns'):
                        if c in work.columns:
                            work[c] = work[c].where(work[c].abs() <= lim)
                try:
                    df[col] = fn(work, symbol, *args, **rf_kwargs)
                except ValueError as e:
                    logger.warning(f"计算 {col_key} 失败: {e}")
                    df[col] = np.nan

        return df


    def _min_rows_for_factors(self):
        """计算所有因子所需的最小行数（含显式预热天数）。

        遍历所有因子条目的窗口参数（整数按交易日数、'1Y' 这类按日历折算成行数），
        取最大值作为窗口上限的保守估计，再与显式 warmup 取较大者。
        """
        if not self._factors or not isinstance(self._factors, dict):
            return self.warmup
        max_window = 0
        for spec in self._factors.values():
            if callable(spec) or not isinstance(spec, (list, tuple)):
                continue
            # 窗口可能是整数（交易日数），也可能是 '1Y' / '3M' / '20D' 这样的日历写法。
            # 字符串要按交易日折算成行数，否则「数据够不够算」的门槛会漏掉它。
            for v in list(spec[1:]):
                if isinstance(v, int):
                    max_window = max(max_window, v)
                elif isinstance(v, str) and v.strip() and v.strip()[-1].upper() in 'YMD':
                    try:
                        max_window = max(max_window, indicator.window_to_rows(v))
                    except ValueError:
                        pass          # 不是窗口写法（如列名 'close_d'），忽略
        return max(max_window, self.warmup)

    # ── 因子缓存 ────────────────────────────────────────────────
    # 因子就是从行情算出来的「下一列」，所以跟行情一样纵向落盘。
    # 但目录**不按数据源/周期/复权分**（那三样是「行情」的口径），而是按**因子名**分：
    # 一个因子 = 一份独立的资产，可以单独查、单独发布、单独排名。
    #
    #     datadir/factors/{因子名}/{symbol}.parquet     （单列，索引同行情）
    #
    # 数据源 / 周期 / 复权 + 因子定义本身，一起压进文件的「配方指纹」——
    # 只要其中任一样变了，指纹就对不上，该票该因子整条重算并覆盖。

    FACTOR_DIR = 'factors'
    FACTOR_META_KEY = b'qka_factor_meta'
    FACTOR_CACHE_VERSION = 1
    _UNSET = object()

    # 停牌日要按前收填充的列（价格类）。停牌当天没有成交，价格就跟前一天一样；
    # volume / amount 不填 —— 那天确实没有成交量，硬填反而不诚实。
    SUSPENDED_FILL_COLUMNS = ('open', 'high', 'low', 'close')


    def _fill_suspended_prices(self, result):
        """把停牌日按「前收」补齐：当天价格 = 前一个交易日的收盘价。

        为什么需要：各标的只在自己的交易日有 K 线，对齐到同一张宽表后，**停牌日就是空缺**。
        而滚动类因子（α/β/波动率……）默认要求窗口内一天都不能缺 —— 只要这只票在过去 N 天里
        停过一天牌，指标就整条算不出来。

        填充口径：价格四列取前一交易日的值（当天收益率因此为 0，等价于「那天没交易」）；
        `returns` 按填充后的 close 重算。**上市前的空缺没有前值，仍然留空** ——
        不会凭空造出一段历史。

        只作用于默认（`lazy=False`）路径，由 `fill_suspended=True` 显式开启。
        """
        if not self.fill_suspended:
            return result
        col_index = self._columns_by_symbol(result.columns)
        replacements = {}
        for symbol in self.symbols:
            sym_cols = col_index.get(symbol)
            if not sym_cols:
                continue
            cols = [
                c for c in sym_cols
                if c.split('|', 1)[1] in self.SUSPENDED_FILL_COLUMNS
            ]
            if not cols:
                continue
            before = result[cols]
            filled = before.ffill()
            if filled.equals(before):
                continue        # 这只票一次没停过牌，什么都别动（省掉重算 returns）
            for c in cols:
                replacements[c] = filled[c]
            if f'{symbol}|close' in cols:
                # 口径与 get() 里一致：diff/shift，不用 pct_change（它的 fill_method 默认值在弃用中）
                close = filled[f'{symbol}|close']
                replacements[f'{symbol}|returns'] = close.diff() / close.shift(1)
        if not replacements:
            return result
        # 一次性换掉，而不是每票各写两遍（全市场就是上万次逐列插入）。
        # 拼回后按原列序重排，保证列顺序一点不变。
        names = list(replacements)
        merged = pd.concat(
            [result.drop(columns=names),
             pd.DataFrame(replacements, index=result.index)],
            axis=1,
        )
        return merged[result.columns]


    def _factor_plan(self):
        """{因子名: (定义, 指纹)}；只要有因子认不出配方就整体返回 None（这次不缓存）。

        认不出的典型是「取不到源码的可调用对象」（REPL 里现写的 lambda、
        动态拼出来的函数）——它的指纹没法跨进程稳定，宁可每次现算，
        也不能拿旧配方算出来的值冒充新值。
        """
        plan = getattr(self, '_factor_plan_cache', self._UNSET)
        if plan is not self._UNSET:
            return plan

        plan = None
        if isinstance(self._factors, dict) and self._factors:
            built = {}
            for name, spec in self._factors.items():
                fp = self._factor_signature(name, spec)
                if fp is None:
                    built = None
                    break
                built[name] = (spec, fp)
            plan = built
        self._factor_plan_cache = plan
        return plan


    def _risk_free_digest(self):
        """无风险利率的稳定摘要，进因子配方指纹用。

        序列动辄几千个点，不能整条塞进指纹 —— 取「长度 + 首尾日期 + 数值哈希」，
        内容一变指纹就变，因子缓存自动失效重算。
        """
        rf = getattr(self, 'risk_free', None)
        if rf is None:
            return None
        if not isinstance(rf, pd.Series):
            try:
                return {'scalar': float(rf)}
            except (TypeError, ValueError):
                return {'raw': str(rf)}
        if len(rf) == 0:
            return {'series': 'empty'}

        s = rf
        if not isinstance(s.index, pd.DatetimeIndex):
            s = s.copy()
            s.index = pd.to_datetime(s.index)
        values = np.asarray(pd.to_numeric(s, errors='coerce'), dtype='float64')
        return {
            'series': hashlib.sha1(np.round(values, 10).tobytes()).hexdigest(),
            'n': int(len(s)),
            'first': str(s.index[0].date()),
            'last': str(s.index[-1].date()),
        }


    def _factor_uses_rf(self, spec) -> bool:
        """这个因子定义对应的指标是否吃 `rf`。

        只有 α / 夏普吃。把无风险利率的摘要塞进所有因子的指纹会让改一次 rf
        就作废全部 32 个因子（其中 24 个跟 rf 毫无关系），白白多算四倍。
        """
        if not isinstance(spec, (list, tuple)) or not spec:
            return False
        name = spec[0]
        if not isinstance(name, str) or not _is_qka_factor(name):
            return False
        fn_name = name.split('.', 1)[1] if name.startswith('qka.') else name
        fn = getattr(indicator, fn_name, None)
        return fn is not None and _accepts_rf(fn)


    def _factor_signature(self, name, spec):
        """单个因子的配方指纹（定义 + 数据口径）；认不出返回 None。

        数据口径 = 数据源 / 周期 / 复权 / **停牌是否补齐** / **掐头根数** —— 任一样变了，
        算出来的值就不一样，指纹必须跟着变，否则缓存会拿旧口径的值冒充新值。
        """
        payload = self._spec_payload(spec)
        if payload is None:
            return None
        blob = json.dumps({
            'v': self.FACTOR_CACHE_VERSION,
            'name': name,
            'spec': payload,
            'source': self.source,
            'period': self.period,
            'adjust': self.adjust,
            'fill_suspended': self.fill_suspended,
            'drop_head': self.drop_head,
            # 无风险利率变了，α / 夏普的值就变了 —— 只对这两个系列的因子
            # 让指纹跟着变，别把不相关的因子一起作废
            'risk_free': (self._risk_free_digest()
                          if self._factor_uses_rf(spec) else None),
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha1(blob.encode('utf-8')).hexdigest()

    @staticmethod

    @staticmethod
    def _spec_payload(spec):
        """把一份因子定义转成可稳定序列化的结构；认不出返回 None。

        末位的 dict 是「该因子自己的选项」（如 max_abs_return），也要进指纹 ——
        选项变了，算出来的值就不一样，缓存必须跟着失效。
        """
        if callable(spec):
            src = _callable_source(spec)
            return None if src is None else {'fn': src}
        if isinstance(spec, (list, tuple)):
            items = []
            for x in spec:
                if isinstance(x, dict):
                    if not all(isinstance(k, str) and isinstance(v, (str, int, float, bool))
                               for k, v in x.items()):
                        return None
                    items.append({k: x[k] for k in sorted(x)})
                elif isinstance(x, (str, int, float, bool)):
                    items.append(x)
                else:
                    return None
            return items
        return None


    def _recompute_target(self, full, cached, window=None, probe_col=None):
        """算出「这次要重算哪一段」。

        - 没有缓存 → 整段算（返回 full）
        - 缓存全盖住 → 不用算（返回 None）
        - 只缺尾巴 → **只算尾巴**（往前只留该因子自己那一个窗口当预热）
        - 前面也缺 → 整段算

        ⚠️ 预热只留「一个窗口」，不是两倍（2026-10-21 改）：算第 t 天的值，滚动
        窗口最多用到 t-window+1 那天的数据，而调用方只把缓存末日之后的行写回，
        多留的窗口纯属白算。之前固定按「全局最长窗口 × 2」= 5000 个工作日回溯，
        等于把 2007 年以来的因子全部重算一遍，连只需 250 天的 1 年期因子也被拖着走。

        ⚠️ 预热按**交易日位置**回溯，不按工作日推算：`BDay(2500)` 只覆盖约 1712 个
        交易日（节假日不算工作日），长窗口因子会预热不足、尾部一串 NaN。
        """
        if cached is None:
            return full
        if cached.index.min() <= full.index.min() and cached.index.max() >= full.index.max():
            return None
        if cached.index.min() > full.index.min():
            # 组合宽表的索引是「所有标的日期的并集」：该票上市之前那些行，本来
            # 就没有它的数据，缓存从上市日起就是完整的 —— 不能因此判成「前面缺、
            # 整段重算」（2026-10-21 改）。之前这里只比 index.min()，导致除全场
            # 最早上市那只票以外，**每一只票每次都被判成整段重算**，增量形同虚设。
            # 真正的「缓存残缺」要看：该票明明有数据，缓存却没盖住那段。
            probe = probe_col if (probe_col and probe_col in full.columns) else None
            if probe is None:
                return full
            head = full.loc[full.index < cached.index.min(), probe]
            if head.notna().any():
                return full
        win = window if isinstance(window, int) and window > 0 else 0
        if win <= 0:
            win = self._min_rows_for_factors()
        if win <= 0:
            # 窗口完全靠猜（lambda + 没声明 warmup）⇒ 不敢只补尾巴，整段重算
            return full
        # cached 末日在这张表里的行号；它之后的每一行才是真正要新算的
        pos = int(full.index.searchsorted(cached.index.max(), side='right')) - 1
        start = pos - win
        if pos < 0 or start <= 0:
            # 历史还不够一个窗口（或缓存末日对不上这张表），谈不上「只补尾巴」
            return full
        return full.iloc[start:].copy()

    @staticmethod

    @staticmethod
    def _spec_window(spec) -> int:
        """从因子定义里取窗口，**统一换算成行数**；取不到返回 0。

        整数原样；字符串（'1Y' / '3M' / '20D'）按交易日折算 —— 见
        `indicator.window_to_rows`。增量预热要用它算「往回留多少行」。
        """
        if not isinstance(spec, (list, tuple)):
            return 0
        win = 0
        for v in list(spec[1:]):
            if isinstance(v, int):
                win = max(win, v)
            elif isinstance(v, str) and v.strip() and v.strip()[-1].upper() in 'YMD':
                try:
                    win = max(win, indicator.window_to_rows(v))
                except ValueError:
                    pass          # 不是窗口写法（如列名），忽略
        return win

    @staticmethod

    @staticmethod
    def _columns_by_symbol(columns):
        """一次遍历建「票 → 它有哪些列」的索引。

        全市场宽表 6 万列，而下面几处都是按票走的：若每票都重新扫一遍全部列名，
        就是 7556 × 6 万次字符串比较 —— 光这一项就足以把整轮跑批拖垮。
        """
        groups = {}
        for col in columns:
            if '|' in col:
                groups.setdefault(col.split('|', 1)[0], []).append(col)
        return groups

    @staticmethod

    @staticmethod
    def _symbol_slice(result, symbol, cols=None):
        """从宽表里取出该票的列、去掉 {symbol}| 前缀（缺失返回空表）。

        `cols` 传 ``_columns_by_symbol`` 里该票那一份，省掉一次全表扫描。
        """
        prefix = f'{symbol}|'
        if cols is None:
            cols = [c for c in result.columns if c.startswith(prefix)]
        sub = result[cols].copy()
        sub.columns = [c[len(prefix):] for c in cols]
        return sub

    @staticmethod

    @staticmethod
    def _collect_slice(symbol, sub, names):
        """把该票新算出来的列收进 ``{列名: 序列}``，交给调用方最后一次性拼上。

        逐列写进结果表会让 pandas 在内存里碎成几万块（每插一列就可能多出一个
        block），此后每次读写都得逐个遍历这些块。收集起来一次 concat，块数就稳住。
        """
        prefix = f'{symbol}|'
        return {
            f'{prefix}{name}': sub[name]
            for name in names
            if name in sub.columns
        }

    @staticmethod

    @staticmethod
    def _attach_columns(result, collected):
        """把收集到的列**一次**拼上。

        这是整套流程里唯一「往结果表加列」的动作 —— 一次 concat 取代原先的
        几万次逐列插入。

        要先剔掉宽表里同名的列：因子存在行情文件里，拼宽表时它们会被当作行情
        一起读进来；不剔就直接 concat，会拼出重复列，之后任何按列名取数据的
        地方都会出问题（实测：加第二个因子时整个流程崩在索引对齐上）。
        """
        if not collected:
            return result
        overlap = [c for c in collected if c in result.columns]
        if overlap:
            result = result.drop(columns=overlap)
        new = pd.DataFrame(collected, index=result.index)
        return pd.concat([result, new], axis=1)


    def _qka_factor_names(self):
        """`self._factors` 里属于 qka 内置因子（α/β/夏普…）的列名，按声明顺序。"""
        if not isinstance(self._factors, dict):
            return []
        return [
            n for n, spec in self._factors.items()
            if isinstance(spec, (list, tuple)) and _is_qka_factor(spec[0])
        ]


    def _order_columns(self, result, qka_names):
        """把列重排回重构前的顺序，纯粹为了不改变既有行为。

        重构前：每票的行情列 → returns → ta/自定义因子，逐票成组；然后是 benchmark，
        最后是 qka 内置因子（**先按因子名、再按标的**）。
        因子缓存把那两类因子都挪到帧尾贴上，顺序就散了。消费者虽然都按列名取值，
        但没理由让它们替我们承担这个差异。
        """
        known = set(self.symbols)
        qka_cols = {f'{s}|{n}' for n in qka_names for s in self.symbols}
        groups, rest, tail = {}, [], []
        for col in result.columns:
            if col in qka_cols:
                tail.append(col)
                continue
            symbol = col.split('|', 1)[0] if '|' in col else None
            if symbol in known:
                groups.setdefault(symbol, []).append(col)
            else:
                rest.append(col)
        order = []
        for symbol in self.symbols:
            order.extend(groups.get(symbol, ()))
        order.extend(rest)
        order.extend(tail)
        return result[order]


    def _factors_with_cache(self, result):
        """逐票把 ta / 自定义因子算出来：命中缓存直接用，没命中才现算并写回。

        只用于默认（非懒加载）路径。懒加载路径行为完全不变。
        新列先收在 collected 里，循环结束一次拼上（见 `_attach_columns`）。
        """
        if not self._factors:
            return result
        # 没开因子缓存 → plan 强制为 None，走下面「现算不落盘」那条路
        plan = self._factor_plan() if self.factor_cache else None
        col_index = self._columns_by_symbol(result.columns)
        collected = {}
        # {symbol: {因子名: (序列, 指纹)}} —— 攒够一轮再写盘，见 _flush_factor_columns
        pending = {}
        for symbol in self.symbols:
            cols = col_index.get(symbol)
            if not cols:
                continue
            sub = self._symbol_slice(result, symbol, cols)
            if sub.empty:
                continue
            # 基准也交给自定义因子（叫 bench）—— 此时 benchmark 已注入，
            # 自定义因子和内置因子看到的是同一份基准收益
            if 'benchmark|returns' in result.columns:
                sub['bench'] = result['benchmark|returns'].reindex(sub.index)

            # 模拟标的没有缓存文件；没开缓存 / 配方认不出也一样 —— 一律现算不落盘
            if plan is None or symbol in self._sim_specs:
                before = set(sub.columns)
                sub = self._apply_factors(sub)
                collected.update(self._collect_slice(
                    symbol, sub, [c for c in sub.columns if c not in before]
                ))
                continue

            names = [
                n for n, (spec, _fp) in plan.items()
                if not (isinstance(spec, (list, tuple)) and _is_qka_factor(spec[0]))
            ]
            pending_cols = {}
            for name in names:
                spec, fp = plan[name]
                cached = self._read_factor_cache(name, symbol, fp)
                target = self._recompute_target(
                    sub, cached, self._spec_window(spec),
                    probe_col='close' if 'close' in sub.columns else None)
                if target is None:
                    sub[name] = cached.reindex(sub.index)
                    continue
                self._compute_factor_cols(target, only={name})
                if target is sub:
                    series = sub[name]
                else:
                    # 只把缓存末日**之后**的行写回，历史值原样沿用缓存：后复权历史
                    # 不会被将来的分红改写，早于缓存末日的因子值不可能变，重算它们
                    # 纯属白烧 CPU；尾巴头部那些预热行同样不该覆盖老值。
                    fresh = target[name][target.index > cached.index.max()]
                    series = fresh.reindex(sub.index).combine_first(
                        cached.reindex(sub.index)
                    )
                    sub[name] = series
                pending_cols[name] = (series, fp)
            if pending_cols:
                pending[symbol] = pending_cols
            collected.update(self._collect_slice(symbol, sub, names))
        self._flush_factor_columns(pending)
        return self._attach_columns(result, collected)


    def _qka_factors_with_cache(self, result):
        """逐票把 qka 内置因子（α/β/夏普…）算出来；开了因子缓存才吃缓存。需在 benchmark 之后调用。

        与 `_factors_with_cache` 一样：新列先收集、最后一次性拼上。另外这里不再
        拿整张宽表当计算台 —— 内置因子只看该票的 returns 加基准，给它一张只含
        这几列的小表就够了（宽表 6 万列，逐票拿它来算太贵）。
        """
        if not self.factor_cache:
            return self._apply_qka_factors(result)
        plan = self._factor_plan()
        names = []
        if plan is not None:
            names = [
                n for n, (spec, _fp) in plan.items()
                if isinstance(spec, (list, tuple)) and _is_qka_factor(spec[0])
            ]
        if not names:
            return self._apply_qka_factors(result)

        col_index = self._columns_by_symbol(result.columns)
        bench_cols = col_index.get('benchmark', [])
        collected = {}
        # {symbol: {因子名: (序列, 指纹)}} —— 攒够一轮再写盘
        pending = {}
        for name in names:
            spec, fp = plan[name]
            # 按「先因子名、再标的」的顺序贴，保持与重构前一致
            for symbol in self.symbols:
                sym_cols = col_index.get(symbol)
                if not sym_cols or f'{symbol}|returns' not in result.columns:
                    continue
                col = f'{symbol}|{name}'
                # 明确复制一份当计算台：内置因子要往它上面加列，而它是从宽表
                # 切出来的视图 —— 不复制的话 pandas 每次都会警告「在切片副本上赋值」。
                view = result[sym_cols + bench_cols].copy()
                if view.empty:
                    continue
                if symbol in self._sim_specs:
                    # 模拟标的没有缓存文件，直接算
                    self._compute_qka_factor_cols(view, [(name, spec)], symbols=[symbol])
                    collected[col] = view[col]
                    continue
                cached = self._read_factor_cache(name, symbol, fp)
                target = self._recompute_target(
                    view, cached, self._spec_window(spec),
                    probe_col=(f'{symbol}|close' if f'{symbol}|close' in view.columns
                               else None))
                if target is None:
                    collected[col] = cached.reindex(result.index)
                    continue
                # 这里给的是一张只有该票的小表，必须把标的限定成它自己
                self._compute_qka_factor_cols(target, [(name, spec)], symbols=[symbol])
                if target is view:
                    series = view[col]
                else:
                    # 同上：只写回缓存末日之后的行，历史值沿用缓存
                    fresh = target[col][target.index > cached.index.max()]
                    series = fresh.reindex(result.index).combine_first(
                        cached.reindex(result.index)
                    )
                collected[col] = series
                pending.setdefault(symbol, {})[name] = (series, fp)
        self._flush_factor_columns(pending)
        return self._attach_columns(result, collected)

