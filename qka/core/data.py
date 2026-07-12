"""
QKA数据模块

提供统一的数据获取、缓存和管理功能，支持多数据源、多周期、多因子的数据获取。
"""

from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import akshare as ak
import baostock as bs
import dask.dataframe as dd
from typing import List, Dict, Optional, Callable
from qka.utils.logger import logger

class Data():
    """
    数据管理类
    
    负责股票数据的获取、缓存和管理，支持多数据源、并发下载和自定义因子计算。
    通过 `indicators` 参数统一处理技术指标和自定义因子，在数据加载时一次性预计算。
    
    Attributes:
        symbols (List[str]): 股票代码列表
        period (str): 数据周期，如 '1d'、'1m' 等
        adjust (str): 复权方式，如 'qfq'、'hfq'、'bfq'
        indicators (dict | Callable): 预计算指标/因子
        source (str): 数据源，如 'baostock'（默认）、'akshare'、'qmt'
        pool_size (int): 并发下载线程数
        datadir (Path): 数据缓存目录
        target_dir (Path): 目标存储目录
    """
    
    def __init__(
        self, 
        symbols: Optional[List[str]] = None,
        period: str = '1d',
        adjust: str = 'qfq',
        source: str = 'baostock',
        pool_size: int = 10,
        datadir: Optional[Path] = None,
        indicators: Optional[dict] = None,
    ):
        """
        初始化数据对象

        Args:
            symbols: 股票代码列表，如 ['000001.SZ', '600000.SH']
            period: 数据周期，如 '1d'（日线）、'1m'（分钟）
            adjust: 复权方式，'qfq'（前复权）、'hfq'（后复权）、'bfq'（不复权）
            source: 数据来源，'baostock'（默认）、'akshare'、'qmt'
            pool_size: 并发下载线程数
            datadir: 缓存目录路径
            indicators: 预计算指标/因子，支持三种格式：
                
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
        self.period = period
        self.adjust = adjust
        self.source = source
        self.pool_size = pool_size

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

    def _download(self, symbol: str) -> Path:
        """
        下载或更新单个股票的数据。

        首次下载全量数据。已存在时只增量拉取最新数据（从 parquet 最后日期到今日），
        追加合并后重新写入，确保缓存始终保持最新。

        Args:
            symbol: 股票代码

        Returns:
            Path: 数据文件路径

        Raises:
            RuntimeError: 数据源返回空数据（首次下载时）
        """
        path = self.target_dir / f"{symbol}.parquet"

        # ── 首次下载：全量 ──
        if not path.exists():
            if self.source == 'akshare':
                df = self._get_from_akshare(symbol)
            elif self.source == 'baostock':
                df = self._get_from_baostock(symbol)
            else:
                df = pd.DataFrame()

            if len(df) == 0:
                raise RuntimeError(f"{symbol}: baostock 返回空数据")
            table = pa.Table.from_pandas(df)
            pq.write_table(table, path)
            return path

        # ── 增量更新 ──
        if self.source != 'baostock':
            return path  # 仅 baostock 支持增量

        # 读已有数据的最后日期
        existing = pd.read_parquet(path)
        if not isinstance(existing.index, pd.DatetimeIndex):
            return path  # 非日期索引，跳过增量（保持原文件不变）
        last_date = existing.index.max()
        today_str = pd.Timestamp.now().strftime("%Y-%m-%d")
        next_date = (last_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        if next_date > today_str:
            return path  # 已是最新

        df_new = self._get_from_baostock(symbol, start_date=next_date)
        if len(df_new) == 0:
            return path  # 没有新数据（交易日还未到）

        # 合并去重
        combined = pd.concat([existing, df_new])
        combined = combined[~combined.index.duplicated(keep='last')]
        combined = combined.sort_index()

        table = pa.Table.from_pandas(combined)
        pq.write_table(table, path)
        return path

    def _needs_download(self, symbol: str) -> bool:
        """
        判断股票是否需要网络下载（parquet 不存在，或 baostock 有增量数据）。
        """
        path = self.target_dir / f"{symbol}.parquet"
        if not path.exists():
            return True
        if self.source != 'baostock':
            return False
        # baostock：检查是否已是最新
        existing = pd.read_parquet(path)
        if not isinstance(existing.index, pd.DatetimeIndex):
            return False
        last_date = existing.index.max()
        today_str = pd.Timestamp.now().strftime("%Y-%m-%d")
        next_date = (last_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        return next_date <= today_str

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
        if start_date is not None or end_date is not None or max_window > 0:
            pq_filters = []
            read_start = None
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

        # 筛选需要网络下载的股票
        need_download = [s for s in self.symbols if self._needs_download(s)]

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
                            self._download(symbol)
                        except Exception as e:
                            errors.append(f"{symbol}: {e}")
                            print(f"\n[警告] 下载 {symbol} 失败: {e}")
                else:
                    with ThreadPoolExecutor(max_workers=self.pool_size) as executor:
                        futures = {
                            executor.submit(self._download, symbol): symbol
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
                ddf = ddf[ddf.index >= pd.Timestamp(start_date)]
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
            return result

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

    def _min_rows_for_indicators(self):
        """计算所有指标所需的最小行数。

        遍历所有指标条目的整数参数，取最大值作为窗口上限的保守估计。
        """
        if not self._indicators or not isinstance(self._indicators, dict):
            return 0
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
        return max_window

    def _get_from_akshare(self, symbol: str) -> pd.DataFrame:
        """
        从 akshare 获取单个股票的数据。

        Args:
            symbol (str): 股票代码，支持带后缀如 000001.SZ 或不带后缀的 000001

        Returns:
            pd.DataFrame: 股票数据，以 date 为索引，包含 open, high, low, close, volume, amount 列
        """
        column_mapping = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
        }

        # 下载数据
        # akshare 不支持带 .SZ/.SH 后缀，需去除
        clean_symbol = symbol.replace('.SZ', '').replace('.SH', '').replace('.BJ', '')
        df = ak.stock_zh_a_hist(symbol=clean_symbol, period='daily', adjust=self.adjust)

        # 数据标准化处理
        # 1. 标准化列名
        df = df.rename(columns=column_mapping)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])

        # 2. 确保数值列为数值类型
        numeric_cols = [c for c in ("open", "high", "low", "close", "volume", "amount") if c in df.columns]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # 3. 只保留需要的列
        mapped_columns = list(column_mapping.values())
        available_columns = [col for col in mapped_columns if col in df.columns]
        df = df[available_columns]

        df = df.set_index('date')
        # 设置索引
        return df

    def _get_from_baostock(
        self, symbol: str,
        start_date: str = '1990-01-01',
        end_date: str = '2050-12-31',
    ) -> pd.DataFrame:
        """
        从 baostock 获取单个股票的数据。

        Args:
            symbol: 股票代码，支持带后缀如 000001.SZ 或 600000.SH
            start_date: 起始日期，格式 YYYY-MM-DD，默认 1990-01-01
            end_date: 截止日期，格式 YYYY-MM-DD，默认 2050-12-31

        Returns:
            pd.DataFrame: 股票数据，以 date 为索引，包含 open, high, low, close, volume, amount 列
        """
        # baostock 代码格式：sz.000001 / sh.600000
        # 支持两种输入格式：
        #   - 000001.SZ → code=000001, exchange=sz
        #   - sz.000001 → code=000001, exchange=sz
        parts = symbol.split('.')
        if len(parts) == 2:
            left, right = parts
            if left.isdigit():
                # 格式: 000001.SZ
                code, exchange = left, right.lower()
            else:
                # 格式: sz.000001
                code, exchange = right, left.lower()
        else:
            # 兜底：无后缀，直接当作代码
            code, exchange = symbol, 'sh'
        bs_code = f"{exchange}.{code}"

        # adjustflag: 1=不复权, 2=前复权, 3=后复权
        adjust_map = {'bfq': '1', 'qfq': '2', 'hfq': '3'}
        adjustflag = adjust_map.get(self.adjust, '2')

        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close,volume,amount",
            start_date=start_date,
            end_date=end_date,
            frequency='d',
            adjustflag=adjustflag,
        )
        if rs.error_code != '0':
            raise RuntimeError(f"baostock 查询 {symbol}({bs_code}) 失败: {rs.error_msg}")
        df = rs.get_data()

        if len(df) == 0:
            return df

        # baostock 返回的数值列是字符串，转数值类型
        numeric_cols = ["open", "high", "low", "close", "volume", "amount"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        return df
