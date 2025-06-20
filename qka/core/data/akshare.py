from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
from qka.utils.logger import logger
from .base import DataSource

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
