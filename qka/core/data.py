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
    
    Attributes:
        symbols (List[str]): 股票代码列表
        period (str): 数据周期，如 '1d'、'1m' 等
        adjust (str): 复权方式，如 'qfq'、'hfq'、'bfq'
        factor (Callable): 因子计算函数
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
        factor: Callable[[pd.DataFrame], pd.DataFrame] = lambda df: df,
        source: str = 'baostock',
        pool_size: int = 10,
        datadir: Optional[Path] = None
    ):
        """
        初始化数据对象

        Args:
            symbols: 股票代码列表，如 ['000001.SZ', '600000.SH']
            period: 数据周期，如 '1d'（日线）、'1m'（分钟）
            adjust: 复权方式，'qfq'（前复权）、'hfq'（后复权）、'bfq'（不复权）
            factor: 因子计算函数，接收 DataFrame 返回 DataFrame，用于扩展自定义因子
            source: 数据来源，'baostock'（默认）、'akshare'、'qmt'
            pool_size: 并发下载线程数
            datadir: 缓存根目录，默认为当前工作目录下的 datadir/
        """
        self.symbols = symbols or []
        self.period = period
        self.adjust = adjust
        self.factor = factor
        self.source = source
        self.pool_size = pool_size

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
        下载单个股票的数据
        
        Args:
            symbol (str): 股票代码
            
        Returns:
            Path: 数据文件路径
        """
        path = self.target_dir / f"{symbol}.parquet"

        if path.exists():
             return path

        if self.source == 'akshare':
            df = self._get_from_akshare(symbol)
        elif self.source == 'baostock':
            df = self._get_from_baostock(symbol)
        else:
            df = pd.DataFrame()

        if len(df) == 0:
            return path

        table = pa.Table.from_pandas(df)
        pq.write_table(table, path)

        return path

    def get(self, lazy: bool = False):
        """
        获取历史数据。

        并发下载所有股票数据，应用因子计算，并返回合并后的数据。

        Args:
            lazy: 是否以懒加载模式返回 dask DataFrame（支持大规模数据分区迭代）。
                  默认 False，返回 compute() 后的 pandas DataFrame（向后兼容）。

        Returns:
            lazy=False: pd.DataFrame，列名格式 {symbol}_{factor}
            lazy=True: dd.DataFrame，列为 MultiIndex (symbol, factor)
            没有数据时抛出 RuntimeError
        """
        if not self.symbols:
            return pd.DataFrame()

        # 缓存
        if lazy:
            if hasattr(self, '_cached_dask') and self._cached_dask is not None:
                return self._cached_dask
        else:
            if hasattr(self, '_cached') and self._cached is not None:
                return self._cached

        # baostock 需要先登录，且其 C/S 架构不支持多线程并发
        bs_logged_in = False
        if self.source == 'baostock':
            lg = bs.login()
            if lg.error_code != '0':
                raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
            bs_logged_in = True

        errors = []
        try:
            if self.source == 'baostock':
                # baostock 串行下载（C/S 架构不支持并发）
                for symbol in tqdm(self.symbols, desc="下载数据"):
                    try:
                        self._download(symbol)
                    except Exception as e:
                        errors.append(f"{symbol}: {e}")
                        logger.warning(f"下载 {symbol} 失败: {e}")
            else:
                # 其他数据源（akshare 等）并发下载
                with ThreadPoolExecutor(max_workers=self.pool_size) as executor:
                    futures = {
                        executor.submit(self._download, symbol): symbol
                        for symbol in self.symbols
                    }
                    with tqdm(total=len(self.symbols), desc="下载数据") as pbar:
                        for future in as_completed(futures):
                            symbol = futures[future]
                            try:
                                future.result()
                            except Exception as e:
                                errors.append(f"{symbol}: {e}")
                                logger.warning(f"下载 {symbol} 失败: {e}")
                            pbar.update(1)
                            pbar.set_postfix_str(f"当前: {symbol}")
            if errors:
                logger.warning(f"共 {len(errors)} 只股票下载失败: {errors[:3]}...")
        finally:
            if bs_logged_in:
                bs.logout()

        if lazy:
            # 懒加载模式：返回 dask DataFrame，列名 {symbol}_{factor}
            dfs = []
            for symbol in self.symbols:
                parquet_path = self.target_dir / f"{symbol}.parquet"
                if not parquet_path.exists():
                    logger.warning(f"数据文件不存在，跳过: {parquet_path}")
                    continue
                ddf = dd.read_parquet(str(parquet_path))
                ddf = self.factor(ddf)
                column_mapping = {col: f'{symbol}_{col}' for col in ddf.columns}
                dfs.append(ddf.rename(columns=column_mapping))

            if not dfs:
                raise RuntimeError(
                    f"所有股票数据加载失败（共 {len(self.symbols)} 只），"
                    f"请检查网络连接和股票代码是否正确"
                )

            ddf = dd.concat(dfs, axis=1, join='outer')
            self._cached_dask = ddf
            return ddf

        else:
            # 全量模式（默认）：与之前一致，向后兼容
            dfs = []
            for symbol in self.symbols:
                parquet_path = self.target_dir / f"{symbol}.parquet"
                if not parquet_path.exists():
                    logger.warning(f"数据文件不存在，跳过: {parquet_path}")
                    continue
                df = dd.read_parquet(str(parquet_path))
                df = self.factor(df)
                column_mapping = {col: f'{symbol}_{col}' for col in df.columns}
                dfs.append(df.rename(columns=column_mapping))

            if not dfs:
                raise RuntimeError(
                    f"所有股票数据加载失败（共 {len(self.symbols)} 只），"
                    f"请检查网络连接和股票代码是否正确"
                )

            ddf = dd.concat(dfs, axis=1, join='outer')
            self._cached = ddf.compute()
            return self._cached

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

    def _get_from_baostock(self, symbol: str) -> pd.DataFrame:
        """
        从 baostock 获取单个股票的数据。

        Args:
            symbol (str): 股票代码，支持带后缀如 000001.SZ 或 600000.SH

        Returns:
            pd.DataFrame: 股票数据，以 date 为索引，包含 open, high, low, close, volume, amount 列
        """
        # baostock 代码格式：sz.000001 / sh.600000
        bs_code = symbol.replace('.SZ', '.sz').replace('.SH', '.sh').replace('.BJ', '.bj')

        # adjustflag: 1=不复权, 2=前复权, 3=后复权
        adjust_map = {'bfq': '1', 'qfq': '2', 'hfq': '3'}
        adjustflag = adjust_map.get(self.adjust, '2')

        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close,volume,amount",
            start_date='1990-01-01',
            end_date='2050-12-31',
            frequency='d',
            adjustflag=adjustflag,
        )
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
