"""
QKA数据模块基础功能

包含数据基类和统一数据接口
"""

from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import akshare as ak
from typing import List, Dict, Optional, Tuple
from qka.utils.logger import logger

class Data():
    """数据基类，所有数据源都继承此类"""
    
    def __init__(
        self, 
        symbols: Optional[List[str]] = None,
        period: str = '1d',
        adjust: str = 'qfq',
        factors: Optional[List[str]] = None,
        source: str = 'akshare',
        pool_size: int = 20,
        cache_root: Optional[Path] = None
    ):
        """
        初始化数据对象
        
        Args:
            symbols: [维度1] 标的，如 ['000001.SZ', '600000.SH']
            period: [维度2] 周期，如 '1m', '5m', '1d' 等
            factors: [维度4] 因子，如 ['open', 'high', 'low', 'close', 'volume']
            source: [维度5] 数据来源 ('qmt', 'akshare')
            pool_size: 并发池大小
            cache_root: 缓存根目录，默认为项目根目录下的 datadir
        """
        self.symbols = symbols or []
        self.period = period
        self.adjust = adjust
        self.factors = factors
        self.source = source
        self.pool_size = pool_size

        # 初始化缓存目录
        if cache_root is None:
            # 默认使用当前工作目录下的 datadir
            self.cache_root = Path.cwd() / "datadir"
        else:
            self.cache_root = Path(cache_root)
        
        self.cache_root.mkdir(parents=True, exist_ok=True)

    def _load_cached_data(self, path: Path) -> pd.DataFrame:
        """从缓存文件加载数据。

        Args:
            path: parquet文件路径

        Returns:
            DataFrame: 加载的数据，date列设置为索引
        """
        table = pq.read_table(path)
        df = table.to_pandas(date_as_object=True)
        if "date" in df.columns:
            df = df.set_index("date")
        return df

    def _save_to_cache(self, df: pd.DataFrame, path: Path) -> None:
        """将数据保存到缓存文件。

        Args:
            df: 要保存的数据，date作为普通列
            path: 保存路径
        """
        table = pa.Table.from_pandas(df)
        pq.write_table(table, path)

    def _download_single_symbol(self, symbol: str, target_dir: Path, force_download: bool = False) -> Tuple[str, pd.DataFrame]:
        """下载单个股票的数据，包括缓存处理。

        Args:
            symbol: 股票代码
            target_dir: 缓存目录
            force_download: 是否强制重新下载

        Returns:
            Tuple[str, pd.DataFrame]: (股票代码, 数据框)
        """
        try:
            # 构造缓存文件路径
            fname = f"{symbol}.parquet"
            path = target_dir / fname

            # 尝试从缓存加载
            if path.exists() and not force_download:
                logger.debug(f"从缓存加载 {symbol} -> {path}")
                df = self._load_cached_data(path)
                return symbol, df

            # 下载新数据
            logger.debug(f"{self.source}: 正在下载 {symbol}")
            
            # 根据数据源调用相应的下载方法
            if self.source == 'akshare':
                df = self._get_from_akshare(symbol)
            else:
                raise ValueError(f"Unknown data source: {self.source}")

            if df is not None and not df.empty:
                # 保存到缓存
                self._save_to_cache(df.reset_index(), path)
                return symbol, df
            
            return symbol, pd.DataFrame()

        except Exception as e:
            logger.error(f"下载 {symbol} 失败: {e}")
            return symbol, pd.DataFrame()

    def get(self, force_download: bool = False) -> Dict[str, pd.DataFrame]:
        """获取历史数据，支持缓存机制和并发下载。
        
        Args:
            force_download: 是否强制重新下载，忽略缓存

        Returns:
            Dict[str, pd.DataFrame]: 股票代码到数据框的映射
        """
        # 准备缓存目录
        target_dir = self.cache_root / self.source / self.period / (self.adjust or "bfq")
        target_dir.mkdir(parents=True, exist_ok=True)

        # 使用线程池并发下载
        results: Dict[str, pd.DataFrame] = {}
        with ThreadPoolExecutor(max_workers=self.pool_size) as executor:
            # 提交所有下载任务
            future_to_symbol = {
                executor.submit(self._download_single_symbol, symbol, target_dir, force_download): symbol
                for symbol in self.symbols
            }

            # 添加tqdm进度条
            with tqdm(total=len(self.symbols), desc="下载数据") as pbar:
                for future in as_completed(future_to_symbol):
                    symbol, df = future.result()
                    results[symbol] = df
                    pbar.update(1)
                    pbar.set_postfix_str(f"当前: {symbol}")
            

        return results

    def _get_from_akshare(self, symbol: str) -> pd.DataFrame:
        """从 akshare 获取单个股票的数据。

        Args:
            symbol: 股票代码，支持带后缀如 000001.SZ 或不带后缀的 000001

        Returns:
            pd.DataFrame: 股票数据，以 date 为索引
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
        df = ak.stock_zh_a_hist(symbol=symbol, period='daily', adjust=self.adjust)

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

        # 设置索引
        return df.set_index("date")
