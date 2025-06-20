def data(stocks=None, sector=None, source=None):
    """
    创建数据对象的工厂函数
    
    Args:
        stocks: 股票代码列表
        sector: 板块名称
        source: 数据源类型 ('qmt', 'akshare')，可选参数，如果不指定则使用全局默认数据源
    
    Returns:
        Data对象
        
    Examples:
        import qka
        
        # 设置默认数据源
        qka.set_source('qmt')
        
        # 使用默认数据源创建数据对象
        data_obj = qka.data(stocks=['000001.SZ', '600000.SH'])
        
        # 临时指定其他数据源
        data_ak = qka.data(stocks=['000001', '600000'], source='akshare')
        
        # 获取板块数据
        data_sector = qka.data(sector='沪深A股')
        
        # 获取历史数据
        hist_data = data_obj.get('1d', '2024-01-01', '2024-12-31')
    """
    # 如果没有指定source，使用全局默认数据源
    if source is None:
        from .config import _DEFAULT_DATA_SOURCE
        source = _DEFAULT_DATA_SOURCE
    
    from .base import Data
    return Data(source, stocks, sector)
