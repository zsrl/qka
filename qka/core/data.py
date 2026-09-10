"""
QKA数据模块

提供统一的数据获取、缓存和管理功能，支持多数据源、多周期、多因子的数据获取。
"""

from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import baostock as bs
import dask.dataframe as dd
from typing import List, Dict, Optional, Callable
from qka.utils.logger import logger
from qka.core import indicator

# qka 内置指标裸名集合，用于 dispatch 识别（无需 qka. 前缀）
_QKA_BUILTIN_NAMES = frozenset({
    'alpha', 'beta', 'sharpe', 'max_drawdown',
    'information_ratio', 'rolling_zigzag',
})


def _is_qka_indicator(ind_type):
    """判断指标类型是否为 qka 内置指标（支持 qka. 前缀或裸名）。"""
    return (isinstance(ind_type, str) and
            (ind_type.startswith('qka.') or ind_type in _QKA_BUILTIN_NAMES))

class Data():
    """
    数据管理类
    
    负责股票数据的获取、缓存和管理，支持多数据源、并发下载和自定义因子计算。
    通过 `indicators` 参数统一处理技术指标和自定义因子，在数据加载时一次性预计算。
    
    Attributes:
        symbols (List[str]): 股票代码列表，baostock 格式如 sz.000001、sh.600000
        period (str): 数据周期，如 '1d'、'1m' 等
        adjust (str): 复权方式，如 'qfq'、'hfq'、'bfq'
        indicators (dict | Callable): 预计算指标/因子
        source (str): 数据源，默认 'baostock'
        pool_size (int): 并发下载线程数
        datadir (Path): 数据缓存目录
        target_dir (Path): 目标存储目录
        extra_fields (List[str]): baostock 扩展字段（选股/估值用），如 ['peTTM', 'pbMRQ', 'turn']
    """
    
    # baostock query_history_k_data_plus 完整支持的基础字段（除 date 索引外）
    BAOSTOCK_BASE_FIELDS = ["open", "high", "low", "close", "volume", "amount"]
    # 可通过 extra_fields 追加的扩展字段白名单（行情/估值/选股类）
    BAOSTOCK_EXTRA_FIELDS = [
        "preclose",    # 前收盘价
        "turn",        # 换手率(%)
        "tradestatus", # 交易状态(1=正常, 0=停牌)
        "pctChg",      # 涨跌幅(%)
        "isST",        # 是否 ST(1=是, 0=否)
        "peTTM",       # 市盈率(TTM)
        "pbMRQ",       # 市净率(MRQ)
        "psTTM",       # 市销率(TTM)
        "pcfNcfTTM",   # 市现率(TTM)
    ]

    def __init__(
        self, 
        symbols: Optional[List[str]] = None,
        benchmark: Optional[str] = None,
        period: str = '1d',
        adjust: str = 'qfq',
        source: str = 'baostock',
        pool_size: int = 10,
        datadir: Optional[Path] = None,
        indicators: Optional[dict] = None,
        extra_fields: Optional[List[str]] = None,
        warmup: int = 0,
    ):
        """
        初始化数据对象

        Args:
            symbols: 股票代码列表，baostock 格式如 ['sz.000001', 'sh.600000']
            benchmark: 基准代码，如 'sh.000300'。基准数据以 benchmark| 前缀加入最终 DataFrame，
                       仅供辅助计算（β/α 等），不参与指标计算
            period: 数据周期，如 '1d'（日线）、'1m'（分钟）
            adjust: 复权方式，'qfq'（前复权）、'hfq'（后复权）、'bfq'（不复权）
            source: 数据来源，默认 'baostock'
            pool_size: 并发下载线程数
            datadir: 缓存目录路径
            indicators: 预计算指标/因子，支持三种格式：
            extra_fields: baostock 扩展字段列表（选股/估值用，如 ['peTTM', 'pbMRQ', 'turn']），
                可选值见 BAOSTOCK_EXTRA_FIELDS。追加的列同样遵循 {symbol}|{field} 命名，
                如 'sh.600000|peTTM'。注意：首次下载后缓存字段固定，变更 extra_fields
                会自动检测列缺失并重新下载对应股票。

            warmup: 指标预热天数（默认 0）。回测/取数时自动多读取 warmup 个交易日的历史数据
                用于计算指标，使第 1 个交易日即可拿到有效指标值，无需在策略里手写
                `if len(hist) < N: continue` 跳过前 N 根 bar。仅用于计算，不会增加 on_bar 调用次数。

                **1. 字典（混搭 ta 函数和自定义因子）：**
                ```python
                {
                    'sma_5':  ('ta.trend.sma_indicator', 'close', 5),
                    'rsi_14': ('ta.momentum.rsi', 'close', 14),
                    'macd':   ('ta.trend.macd_diff', 'close', 26, 12, 9),
                    'atr_14': ('ta.volatility.average_true_range', 'high', 'low', 'close', 14),
                    'ma5':    lambda df: df['close'].rolling(5).mean(),
                }
                ```
                每个条目独立产一列，直接透传 ta 库全部指标。
                列名参数（'close'/'high' 等）放在 ta 路径之后、数值参数之前；
                多列函数（如 ATR）连续列出所有列名即可。
                
                **2. 函数（自定义因子）：**
                ```python
                indicators=lambda df: df.assign(ma5=df['close'].rolling(5).mean())
                ```
                函数接收单只股票的 DataFrame，返回添加了额外列的 DataFrame。
        """
        self.symbols = symbols or []
        self.benchmark = benchmark
        self.period = period
        self.adjust = adjust
        self.source = source
        self.pool_size = pool_size
        self.warmup = warmup

        # extra_fields 白名单校验 + 去重
        self.extra_fields = []
        for f in (extra_fields or []):
            if f not in self.BAOSTOCK_EXTRA_FIELDS:
                raise ValueError(
                    f"extra_fields 含不支持的字段: {f}。"
                    f"可选: {self.BAOSTOCK_EXTRA_FIELDS}"
                )
            if f not in self.extra_fields:
                self.extra_fields.append(f)

        # 统一处理 indicators 参数
        if callable(indicators):
            # 函数形式 → 保存为 callable
            self._indicators = indicators
        elif isinstance(indicators, dict):
            # 字典形式
            self._indicators = indicators
        elif indicators is None:
            self._indicators = {}
        else:
            raise TypeError(
                f"indicators 必须是 dict、callable 或 None，got {type(indicators)}"
            )

        # 初始化缓存目录
        if datadir is None:
            # 默认使用当前工作目录下的 datadir
            self.datadir = Path.cwd() / "datadir"
        else:
            self.datadir = Path(datadir)
        
        self.datadir.mkdir(parents=True, exist_ok=True)

        self.target_dir = self.datadir / self.source / self.period / (self.adjust or "bfq")
        self.target_dir.mkdir(parents=True, exist_ok=True)

    def _cache_missing_extra_fields(self, path: Path) -> bool:
        """检查已有 parquet 缓存是否缺少 extra_fields 指定的列。"""
        if not self.extra_fields or not path.exists():
            return False
        try:
            cols = set(pq.read_schema(path).names)
        except Exception:
            return True
        return any(f not in cols for f in self.extra_fields)

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
        for f in self.BAOSTOCK_EXTRA_FIELDS:
            if f in existing and f not in merged:
                merged.append(f)
        return merged

    def _download(
        self, symbol: str,
        download_start: str = None,
        download_end: str = None,
    ) -> Path:
        """
        按需下载单个股票数据。

        首次下载只拉请求范围（非全量）。已存在时检查缓存覆盖范围，
        只补下载缺失的部分（前面缺失补前面，后面缺失补后面），合并去重写回。
        若缓存缺少 extra_fields 指定的列（如从无扩展字段升级到有），则全量重新下载。

        Args:
            symbol: 股票代码
            download_start: 下载起始日期，格式 YYYY-MM-DD。None 表示拉全量（1990-01-01）
            download_end: 下载截止日期，格式 YYYY-MM-DD。None 表示到今天

        Returns:
            Path: 数据文件路径

        Raises:
            RuntimeError: 数据源返回空数据（首次下载时）
        """
        path = self.target_dir / f"{symbol}.parquet"
        default_start = '1990-01-01'
        default_end = pd.Timestamp.now().strftime("%Y-%m-%d")

        # 实际请求的扩展字段 = 当前配置 ∪ 缓存已有扩展列（列只增不减，不互相覆盖）
        merged_extra = self._merged_extra_fields(path)

        # ── 首次下载：只拉请求范围（缓存缺失 extra_fields 列时也全量重下）──
        if not path.exists() or self._cache_missing_extra_fields(path):
            df = self._get_from_baostock(
                symbol,
                start_date=download_start or default_start,
                end_date=download_end or default_end,
                extra_fields=merged_extra,
            )
            if len(df) == 0:
                raise RuntimeError(f"{symbol}: baostock 返回空数据")
            table = pa.Table.from_pandas(df)
            pq.write_table(table, path)
            return path

        # ── 增量更新：检查缓存覆盖，补缺失范围 ──
        if self.source != 'baostock':
            return path

        existing = pd.read_parquet(path)
        if not isinstance(existing.index, pd.DatetimeIndex):
            return path

        cache_min = existing.index.min()
        cache_max = existing.index.max()
        pieces = [existing]
        changed = False

        # 往前补
        req_start = pd.Timestamp(download_start) if download_start else None
        if req_start is not None and req_start < cache_min:
            end_before = (cache_min - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            df_before = self._get_from_baostock(
                symbol, start_date=download_start, end_date=end_before,
                extra_fields=merged_extra,
            )
            if len(df_before) > 0:
                pieces.insert(0, df_before)
                changed = True

        # 往后补
        req_end = pd.Timestamp(download_end) if download_end else pd.Timestamp.now()
        if req_end > cache_max:
            start_after = (cache_max + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            df_after = self._get_from_baostock(
                symbol,
                start_date=start_after,
                end_date=download_end or default_end,
                extra_fields=merged_extra,
            )
            if len(df_after) > 0:
                pieces.append(df_after)
                changed = True

        if changed:
            combined = pd.concat(pieces)
            combined = combined[~combined.index.duplicated(keep='last')]
            combined = combined.sort_index()
            table = pa.Table.from_pandas(combined)
            pq.write_table(table, path)

        return path

    def _needs_download(
        self, symbol: str,
        download_start: str = None,
        download_end: str = None,
    ) -> bool:
        """
        判断股票是否需要网络下载。
        缓存不存在、不覆盖请求范围、或需要拉最新数据时返回 True。
        """
        path = self.target_dir / f"{symbol}.parquet"
        if not path.exists() or self._cache_missing_extra_fields(path):
            return True
        if self.source != 'baostock':
            return False
        existing = pd.read_parquet(path)
        if not isinstance(existing.index, pd.DatetimeIndex):
            return False
        cache_min = existing.index.min()
        cache_max = existing.index.max()
        today = pd.Timestamp.now().floor('D')

        if download_start is not None and pd.Timestamp(download_start) < cache_min:
            return True
        if download_end is not None and pd.Timestamp(download_end) > cache_max:
            return True
        # 无 end_date 时检查是否有最新数据
        if download_end is None and cache_max < today:
            return True
        return False

    def get(self, lazy: bool = False, start_date: str = None, end_date: str = None):
        """
        获取历史数据。

        并发下载所有股票数据，应用因子计算，并返回合并后的数据。

        Args:
            lazy: 是否以懒加载模式返回 dask DataFrame（支持大规模数据分区迭代）。
                  默认 False，返回 compute() 后的 pandas DataFrame（向后兼容）。
            start_date: 起始日期，格式 YYYY-MM-DD。用于从缓存中截取数据范围，
                        避免全量加载。传 None 表示从最早可用数据开始。
            end_date: 截止日期，格式 YYYY-MM-DD。传 None 表示到最新可用数据。

        Returns:
            lazy=False: pd.DataFrame，列名格式 {symbol}|{factor}
            lazy=True: dd.DataFrame，列名格式 {symbol}|{factor}
            没有数据时抛出 RuntimeError

        注意：有指标时，start_date 会自动向后扩展 max_window 个交易日读取缓存，
        确保指标有足够的预热数据。最终返回的 DataFrame 仍严格限定在 [start_date, end_date]。
        """
        if not self.symbols:
            return pd.DataFrame()

        # 计算指标预热窗口
        max_window = self._min_rows_for_indicators()

        # 构建 parquet predicate pushdown 过滤（日期 + 指标预热扩展）
        pq_filters = None
        read_start = None
        if start_date is not None or end_date is not None or max_window > 0:
            pq_filters = []
            if start_date is not None:
                read_start = pd.Timestamp(start_date)
            if max_window > 0:
                if read_start is not None:
                    # 向后扩展，确保指标有足够的预热数据
                    read_start = read_start - pd.offsets.BDay(max_window * 2)
                # 无 start_date 但有指标时，不需要扩展（从头读即可）
            if read_start is not None:
                pq_filters.append(('date', '>=', read_start))
            if end_date is not None:
                pq_filters.append(('date', '<=', pd.Timestamp(end_date)))
            if not pq_filters:
                pq_filters = None

        # 计算网络下载范围（带预热扩展的 start_date）
        download_start = read_start.strftime("%Y-%m-%d") if read_start is not None else None
        download_end = end_date

        # 筛选需要网络下载的股票（含基准）
        all_symbols = list(self.symbols)
        if self.benchmark and self.benchmark not in all_symbols:
            all_symbols.append(self.benchmark)
        need_download = [
            s for s in all_symbols
            if self._needs_download(s, download_start, download_end)
        ]

        # 仅当有股票需要下载时才登录 baostock
        bs_logged_in = False
        if need_download and self.source == 'baostock':
            lg = bs.login()
            if lg.error_code != '0':
                raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
            bs_logged_in = True

        errors = []
        try:
            if need_download:
                if self.source == 'baostock':
                    for symbol in tqdm(need_download, desc="下载数据"):
                        try:
                            self._download(symbol, download_start, download_end)
                        except Exception as e:
                            errors.append(f"{symbol}: {e}")
                            print(f"\n[警告] 下载 {symbol} 失败: {e}")
                else:
                    with ThreadPoolExecutor(max_workers=self.pool_size) as executor:
                        futures = {
                            executor.submit(
                                self._download, symbol, download_start, download_end,
                            ): symbol
                            for symbol in need_download
                        }
                        with tqdm(total=len(need_download), desc="下载数据") as pbar:
                            for future in as_completed(futures):
                                symbol = futures[future]
                                try:
                                    future.result()
                                except Exception as e:
                                    errors.append(f"{symbol}: {e}")
                                    print(f"\n[警告] 下载 {symbol} 失败: {e}")
                                pbar.update(1)
                                pbar.set_postfix_str(f"当前: {symbol}")
            if errors:
                raise RuntimeError(
                    f"共 {len(errors)} 只股票下载失败:\n" +
                    "\n".join(f"  - {e}" for e in errors)
                )
        finally:
            if bs_logged_in:
                bs.logout()

        if lazy:
            # 懒加载模式：返回 dask DataFrame，列名 {symbol}|{factor}
            dfs = []
            for symbol in self.symbols:
                parquet_path = self.target_dir / f"{symbol}.parquet"
                if not parquet_path.exists():
                    logger.warning(f"数据文件不存在，跳过: {parquet_path}")
                    continue
                ddf = dd.read_parquet(str(parquet_path), filters=pq_filters)
                ddf['returns'] = ddf['close'].diff() / ddf['close'].shift(1)
                ddf = self._apply_indicators(ddf)
                column_mapping = {col: f'{symbol}|{col}' for col in ddf.columns}
                dfs.append(ddf.rename(columns=column_mapping))

            if not dfs:
                raise RuntimeError(
                    f"所有股票数据加载失败（共 {len(self.symbols)} 只），"
                    f"请检查网络连接和股票代码是否正确"
                )

            ddf = dd.concat(dfs, axis=1, join='outer')
            # 切片回用户请求的日期范围（去掉指标预热扩展部分）
            if start_date is not None and max_window > 0:
                cutoff = pd.Timestamp(start_date)
                ddf = ddf.loc[cutoff:]

            # 基准数据
            if self.benchmark:
                ddf = self._add_benchmark(ddf, self.target_dir, pq_filters)

            # qka 内置指标（需要 benchmark 和 symbol 前缀）
            ddf = self._apply_qka_indicators(ddf)

            return ddf

        else:
            # 全量模式（默认）
            dfs = []
            for symbol in self.symbols:
                parquet_path = self.target_dir / f"{symbol}.parquet"
                if not parquet_path.exists():
                    logger.warning(f"数据文件不存在，跳过: {parquet_path}")
                    continue
                df = dd.read_parquet(str(parquet_path), filters=pq_filters)
                df['returns'] = df['close'].diff() / df['close'].shift(1)
                df = self._apply_indicators(df)
                column_mapping = {col: f'{symbol}|{col}' for col in df.columns}
                dfs.append(df.rename(columns=column_mapping))

            if not dfs:
                raise RuntimeError(
                    f"所有股票数据加载失败（共 {len(self.symbols)} 只），"
                    f"请检查网络连接和股票代码是否正确"
                )

            ddf = dd.concat(dfs, axis=1, join='outer')
            result = ddf.compute()
            # 切片回用户请求的日期范围
            if start_date is not None and max_window > 0:
                result = result[result.index >= pd.Timestamp(start_date)]

            # 基准数据
            if self.benchmark:
                result = self._add_benchmark(result, self.target_dir, pq_filters)

            # qka 内置指标（需要 benchmark 和 symbol 前缀）
            result = self._apply_qka_indicators(result)

            return result

    def _add_benchmark(self, df, target_dir, pq_filters):
        """将基准数据的 returns 以 benchmark| 前缀追加到 DataFrame。"""
        bench_path = target_dir / f"{self.benchmark}.parquet"
        if not bench_path.exists():
            logger.warning(f"基准数据文件不存在: {bench_path}")
            return df
        bench_df = pd.read_parquet(bench_path, filters=pq_filters)
        bench_df['returns'] = bench_df['close'].diff() / bench_df['close'].shift(1)
        bench_returns = bench_df['returns'].rename('benchmark|returns')

        if isinstance(df, dd.DataFrame):
            # dask: 用 assign 加列，pandas Series 会自动对齐分区
            return df.assign(**{'benchmark|returns': bench_returns})
        else:
            df['benchmark|returns'] = bench_returns.reindex(df.index)
            return df

    def _apply_indicators(self, df):
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
        inds = self._indicators

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
            # 先用样本分区计算指标，获得准确的 meta（含新增的指标列）
            # 避免 dask 在迷你分区上推理 meta 时因窗口不足而崩溃
            sample = df.head(200)
            meta = self._compute_indicator_cols(sample.copy())
            return df.map_partitions(
                lambda partition: self._compute_indicator_cols(partition.copy()),
                meta=meta,
            )
        return self._compute_indicator_cols(df.copy())

    def _compute_indicator_cols(self, df):
        """在 pandas DataFrame 上计算指标/因子列（单只股票）。"""

        # 分区过小时跳过，避免 ta-lib 在 dask meta 推断时崩溃
        min_rows = self._min_rows_for_indicators()
        if len(df) < min_rows:
            return df

        for col_name, spec in self._indicators.items():
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

            # qka 内置指标：跳过，由 _apply_qka_indicators 集中处理
            if _is_qka_indicator(ind_type):
                continue

            args = list(spec[1:])

            # 收集前面连续的字符串参数作为列名（遇到第一个非字符串即停）
            factors = []
            rest_start = 0
            for i, arg in enumerate(args):
                if isinstance(arg, str):
                    factors.append(arg)
                    rest_start = i + 1
                else:
                    break
            if not factors:
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

            if len(factors) == 1:
                df[col_name] = fn(df[factors[0]], *rest)
            else:
                df[col_name] = fn(*[df[f] for f in factors], *rest)

        return df

    def _apply_qka_indicators(self, df):
        """应用 qka 内置指标（带 symbol 前缀，含 benchmark 数据）。

        必须在 concat + 加 benchmark 之后调用，此时列名格式为
        {symbol}|returns 和 benchmark|returns。

        Args:
            df: 合并后的 DataFrame（列名已带 symbol 前缀）

        Returns:
            DataFrame: 含 qka 指标列
        """
        inds = self._indicators
        if not inds or not isinstance(inds, dict):
            return df

        qka_specs = [
            (col_name, spec) for col_name, spec in inds.items()
            if isinstance(spec, (list, tuple))
            and _is_qka_indicator(spec[0])
        ]
        if not qka_specs:
            return df

        if isinstance(df, dd.DataFrame):
            sample = df.head(200)
            meta = self._compute_qka_indicator_cols(sample, qka_specs)
            return df.map_partitions(
                lambda p: self._compute_qka_indicator_cols(p, qka_specs),
                meta=meta,
            )
        return self._compute_qka_indicator_cols(df, qka_specs)

    def _compute_qka_indicator_cols(self, df, qka_specs):
        """在已合并的 DataFrame 上计算 qka 内置指标。"""
        for col_key, spec in qka_specs:
            fn_name = spec[0].split('.', 1)[1] if spec[0].startswith('qka.') else spec[0]
            args = list(spec[1:])

            try:
                fn = getattr(indicator, fn_name)
            except AttributeError:
                logger.warning(f"qka 内置指标不存在: {fn_name}，跳过")
                continue

            # 为每只股票计算
            for symbol in self.symbols:
                col = f'{symbol}|{col_key}'
                try:
                    df[col] = fn(df, symbol, *args)
                except ValueError as e:
                    logger.warning(f"计算 {col_key} 失败: {e}")
                    df[col] = np.nan

        return df

    def _min_rows_for_indicators(self):
        """计算所有指标所需的最小行数（含显式预热天数）。

        遍历所有指标条目的整数参数，取最大值作为窗口上限的保守估计，
        再与显式 warmup 取较大者。
        """
        if not self._indicators or not isinstance(self._indicators, dict):
            return self.warmup
        max_window = 0
        for spec in self._indicators.values():
            if callable(spec) or not isinstance(spec, (list, tuple)):
                continue
            # spec[1:] 中跳过所有前导字符串（列名），收集剩余整数
            rest = list(spec[1:])
            idx = 0
            while idx < len(rest) and isinstance(rest[idx], str):
                idx += 1
            for v in rest[idx:]:
                if isinstance(v, int):
                    max_window = max(max_window, v)
        return max(max_window, self.warmup)

    def _get_from_baostock(
        self, symbol: str,
        start_date: str = '1990-01-01',
        end_date: str = '2050-12-31',
        extra_fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        从 baostock 获取单个股票的数据。

        Args:
            symbol: baostock 格式股票代码，如 sz.000001、sh.600000
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

        rs = bs.query_history_k_data_plus(
            symbol,
            fields,
            start_date=start_date,
            end_date=end_date,
            frequency='d',
            adjustflag=adjustflag,
        )
        if rs.error_code != '0':
            raise RuntimeError(f"baostock 查询 {symbol}({bs_code}) 失败: {rs.error_msg}")
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
