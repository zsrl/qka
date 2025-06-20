import time
from datetime import datetime
from typing import List, Dict
import pandas as pd
from qka.utils.logger import logger
from .base import DataSource

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
