from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import pandas as pd
from qka.utils.logger import logger
from .base import DataBase

class AkshareData(DataBase):
    """Akshare数据源"""
    
    def __init__(
        self, 
        time_range: Tuple[str, str] = None,
        symbols: List[str] = None,
        period: str = '1d',
        factors: List[str] = None
    ):
        super().__init__(time_range, symbols, period, factors)
        try:
            import akshare as ak
            self.ak = ak
        except ImportError:
            logger.error("无法导入akshare，请安装: pip install akshare")
            raise
    
    
    def get(self, period: str = None, start_time: str = '', end_time: str = '') -> Dict[str, pd.DataFrame]:
        """获取Akshare历史数据"""
        if not self.symbols:
            logger.warning("未指定股票列表")
            return {}
        
        # 使用传入的参数或初始化时的参数
        if period is None:
            period = self.period
            
        if not start_time and not end_time and self.time_range:
            start_time, end_time = self.time_range
        
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
        
        for stock in self.symbols:
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
    
    def subscribe(self, callback):
        """Akshare暂不支持实时数据订阅"""
        logger.warning("Akshare数据源暂不支持实时数据订阅")
        raise NotImplementedError("Akshare数据源暂不支持实时数据订阅")
