from xtquant import xtdata

class QMTData:
    def __init__(self, stocks, indicators):
        self.stocks = stocks
        self.indicators = indicators
    
    def get(self, period, start_time='', end_time=''):

        for stock in self.stocks:
            xtdata.download_history_data(stock_code=stock, period=period, start_time=start_time, end_time=end_time, incrementally=True)
        
        res = xtdata.get_local_data(stock_list=self.stocks, period=period, start_time=start_time, end_time=end_time)

        return res

def data(**args):
    return QMTData(**args)
