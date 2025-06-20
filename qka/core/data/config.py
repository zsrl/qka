# 全局默认数据源配置
_DEFAULT_DATA_SOURCE = 'akshare'

def set_source(source: str) -> None:
    """
    设置全局默认数据源
    
    Args:
        source: 数据源类型 ('qmt', 'akshare')
    
    Examples:
        import qka
        
        # 设置默认使用QMT数据源
        qka.set_source('qmt')
        
        # 之后创建数据对象就不需要指定source了
        data_obj = qka.data(stocks=['000001.SZ', '600000.SH'])
    """
    global _DEFAULT_DATA_SOURCE
    from qka.utils.logger import logger
    
    # 导入数据源映射
    from .sources import DATA_SOURCE_MAPPING
    
    if source.lower() not in DATA_SOURCE_MAPPING:
        available_sources = ', '.join(DATA_SOURCE_MAPPING.keys())
        raise ValueError(f"不支持的数据源类型: {source}，支持的数据源: {available_sources}")
    
    _DEFAULT_DATA_SOURCE = source.lower()
    logger.info(f"已设置默认数据源为: {source}")

def get_source() -> str:
    """
    获取当前默认数据源
    
    Returns:
        当前默认数据源名称
    """
    return _DEFAULT_DATA_SOURCE
