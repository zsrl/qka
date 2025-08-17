from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import akshare as ak
from qka.utils.logger import logger


class Downloader:
    """通用下载器。
    """

    def __init__(self, source: str = "akshare", cache_root: Optional[Path] = None):
        # 默认缓存目录：项目根下的 data/cache
        if cache_root is None:
            # qka/core/data -> 项目根向上三级
            self.cache_root = Path(__file__).resolve().parents[3] / "datadir"
        else:
            self.cache_root = Path(cache_root)

        self.cache_root.mkdir(parents=True, exist_ok=True)
        # 默认数据源，可在 download() 时被使用或覆盖
        self.source = source

    def download(self, *args, **kwargs):
        """通用调度器，按 source 分发到具体实现。
        """

        if self.source == 'akshare':
            return self.download_from_akshare(*args, **kwargs)

        raise ValueError(f"Unknown download source: {self.source}")

    def download_from_akshare(
        self,
        symbols: List[str],
        period: str = "1d",
        adjust: str = '',
        force_download: bool = False,
    ) -> Dict[str, pd.DataFrame]:
        """从 akshare 下载多个股票的数据并缓存为 parquet。

        返回一个字典：symbol -> DataFrame（以 date 为索引）。

        参数：
            symbols: 股票代码列表，支持带后缀如 000001.SZ 或不带后缀的 000001
            period: akshare 的 period 参数，如 'daily'
            adjust: akshare 的 adjust 参数
            force_download: 若为 True 则忽略本地缓存，强制重新下载
        """
        out: Dict[str, pd.DataFrame] = {}
        target_dir = self.cache_root / "akshare" / period / (adjust or "bfq")
        target_dir.mkdir(parents=True, exist_ok=True)

        column_mapping = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
        }

        for symbol in symbols:
            try:
                # file name safe
                fname = f"{symbol}.parquet"
                path = target_dir / fname

                if path.exists() and not force_download:
                    logger.debug(f"从缓存加载 {symbol} -> {path}")
                    df = pd.read_parquet(path)
                    out[symbol] = df
                    continue

                logger.debug(f"akshare: 正在下载 {symbol} (code={symbol}) period={period} adjust={adjust})")

                df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust=adjust)

                # 标准化列名，并设置索引
                df = df.rename(columns=column_mapping)
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.set_index("date")

                # 确保数值列为数值类型（包括 amount）
                numeric_cols = [c for c in ("open", "high", "low", "close", "volume", "amount") if c in df.columns]
                for col in numeric_cols:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

                # 只保留 column_mapping 中定义的列，其他列都丢弃
                # 从 column_mapping 中获取所有映射后的列名
                mapped_columns = list(column_mapping.values())
                # 只保留这些列，如果列存在的话
                available_columns = [col for col in mapped_columns if col in df.columns]
                df = df[available_columns]

                df.to_parquet(path)

                out[symbol] = df
                logger.info(f"已保存 {symbol} 到缓存: {path} (rows={len(df)})")

            except Exception as e:
                logger.error(f"下载 {symbol} 失败: {e}")
                out[symbol] = pd.DataFrame()

        return out


__all__ = ["Downloader"]
