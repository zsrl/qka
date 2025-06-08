import time
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Union
from qka.utils.logger import logger

class DataSource(ABC):
    """数据源基类"""
    
    def __init__(self, stocks: List[str] = None, sector: str = None):
        self.stocks = stocks or []
        self.sector = sector
        
    @abstractmethod
    def get_historical_data(self, period: str = '1d', start_time: str = '', end_time: str = '') -> Dict[str, pd.DataFrame]:
        """获取历史数据"""
        pass
        
    @abstractmethod
    def subscribe_realtime(self, callback):
        """订阅实时数据"""
        pass
    
    def normalize_data(self, data: Dict) -> Dict[str, pd.DataFrame]:
        """标准化数据格式为统一的DataFrame格式"""
        normalized = {}
        for symbol, df in data.items():
            if isinstance(df, pd.DataFrame):
                # 确保包含必要的列
                required_cols = ['open', 'high', 'low', 'close', 'volume']
                if all(col in df.columns for col in required_cols):
                    # 确保索引是datetime类型
                    if not isinstance(df.index, pd.DatetimeIndex):
                        if 'time' in df.columns:
                            df = df.set_index('time')
                        df.index = pd.to_datetime(df.index)
                    normalized[symbol] = df
                else:
                    logger.warning(f"股票 {symbol} 缺少必要的数据列")
        return normalized

class QMTData(DataSource):
    """QMT数据源"""
    
    def __init__(self, stocks: List[str] = None, sector: str = None):
        super().__init__(stocks, sector)
        try:
            from xtquant import xtdata
            self.xtdata = xtdata
            if sector is not None:
                self.stocks = xtdata.get_stock_list_in_sector(sector)
        except ImportError:
            logger.error("无法导入xtquant，请检查QMT是否正确安装")
            raise
    
    def get_historical_data(self, period: str = '1d', start_time: str = '', end_time: str = '') -> Dict[str, pd.DataFrame]:
        """获取QMT历史数据"""
        if not self.stocks:
            logger.warning("未指定股票列表")
            return {}
            
        # 下载数据
        for stock in self.stocks:
            self.xtdata.download_history_data(
                stock_code=stock, 
                period=period, 
                start_time=start_time, 
                end_time=end_time, 
                incrementally=True
            )
        
        # 获取本地数据
        res = self.xtdata.get_local_data(
            stock_list=self.stocks, 
            period=period, 
            start_time=start_time, 
            end_time=end_time
        )
        
        return self.normalize_data(res)
    
    def subscribe_realtime(self, callback):
        """订阅QMT实时数据"""
        delays = []

        def task(res):
            for code, item in res.items():
                rate = (item['lastPrice'] - item['lastClose']) / item['lastClose']
                timetag = datetime.fromtimestamp(item['time'] / 1000)
                current_time = datetime.fromtimestamp(time.time())
                delay_seconds = (current_time - timetag).total_seconds()
                if delay_seconds < 1000:
                    if delay_seconds > 3:
                        logger.warning(f'{code} 延迟 {delay_seconds}')
                    callback(code, item)

        self.xtdata.subscribe_whole_quote(code_list=self.stocks, callback=task)
        self.xtdata.run()

class AkshareData(DataSource):
    """Akshare数据源"""
    
    def __init__(self, stocks: List[str] = None, sector: str = None):
        super().__init__(stocks, sector)
        try:
            import akshare as ak
            self.ak = ak
        except ImportError:
            logger.error("无法导入akshare，请安装: pip install akshare")
            raise
            
        if sector is not None:
            self.stocks = self._get_stocks_by_sector(sector)
    
    def _get_stocks_by_sector(self, sector: str) -> List[str]:
        """根据板块获取股票列表"""
        try:
            if sector == "沪深A股":
                # 获取沪深A股列表
                stock_info = self.ak.stock_info_a_code_name()
                return stock_info['code'].tolist()[:100]  # 限制数量避免过多
            else:
                logger.warning(f"暂不支持板块: {sector}")
                return []
        except Exception as e:
            logger.error(f"获取板块股票失败: {e}")
            return []
    
    def get_historical_data(self, period: str = '1d', start_time: str = '', end_time: str = '') -> Dict[str, pd.DataFrame]:
        """获取Akshare历史数据"""
        if not self.stocks:
            logger.warning("未指定股票列表")
            return {}
        
        result = {}
        
        # 处理日期格式
        if start_time:
            start_date = start_time.replace('-', '') if '-' in start_time else start_time
        else:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
            
        if end_time:
            end_date = end_time.replace('-', '') if '-' in end_time else end_time
        else:
            end_date = datetime.now().strftime('%Y%m%d')
        
        for stock in self.stocks:
            try:
                # 转换股票代码格式
                if '.' in stock:
                    code = stock.split('.')[0]
                else:
                    code = stock
                
                # 获取股票历史数据
                df = self.ak.stock_zh_a_hist(
                    symbol=code,
                    period='daily',
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"  # 前复权
                )
                
                if df is not None and not df.empty:
                    # 重命名列以匹配标准格式
                    column_mapping = {
                        '日期': 'date',
                        '开盘': 'open',
                        '收盘': 'close', 
                        '最高': 'high',
                        '最低': 'low',
                        '成交量': 'volume',
                        '成交额': 'amount'
                    }
                    
                    df = df.rename(columns=column_mapping)
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.set_index('date')
                    
                    # 确保数值类型
                    numeric_cols = ['open', 'high', 'low', 'close', 'volume']
                    for col in numeric_cols:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    
                    result[stock] = df
                    logger.debug(f"成功获取 {stock} 数据，共 {len(df)} 条记录")
                
            except Exception as e:
                logger.error(f"获取 {stock} 数据失败: {e}")
                continue
        
        return self.normalize_data(result)
    
    def subscribe_realtime(self, callback):
        """Akshare暂不支持实时数据订阅"""
        logger.warning("Akshare数据源暂不支持实时数据订阅")
        raise NotImplementedError("Akshare数据源暂不支持实时数据订阅")

class Data:
    """统一数据接口"""
    
    def __init__(self, source: str = 'qmt', stocks: List[str] = None, sector: str = None):
        """
        初始化数据对象
        
        Args:
            source: 数据源类型 ('qmt', 'akshare')
            stocks: 股票代码列表
            sector: 板块名称
        """
        self.source_type = source
        
        if source.lower() == 'qmt':
            self.data_source = QMTData(stocks, sector)
        elif source.lower() == 'akshare':
            self.data_source = AkshareData(stocks, sector)
        else:
            raise ValueError(f"不支持的数据源类型: {source}")
    
    def get(self, period: str = '1d', start_time: str = '', end_time: str = '') -> Dict[str, pd.DataFrame]:
        """获取历史数据"""
        return self.data_source.get_historical_data(period, start_time, end_time)
    
    def subscribe(self, callback):
        """订阅实时数据"""
        return self.data_source.subscribe_realtime(callback)
    
    @property
    def stocks(self) -> List[str]:
        """获取股票列表"""
        return self.data_source.stocks

def data(source: str = 'qmt', stocks: List[str] = None, sector: str = None) -> Data:
    """
    创建数据对象的工厂函数
    
    Args:
        source: 数据源类型 ('qmt', 'akshare')
        stocks: 股票代码列表
        sector: 板块名称
    
    Returns:
        Data对象
    
    Examples:
        # 使用QMT数据源
        data_qmt = data('qmt', stocks=['000001.SZ', '600000.SH'])
        
        # 使用Akshare数据源
        data_ak = data('akshare', stocks=['000001', '600000'])
        
        # 获取板块数据
        data_sector = data('akshare', sector='沪深A股')
    """
    return Data(source, stocks, sector)
