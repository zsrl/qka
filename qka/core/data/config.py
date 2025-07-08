"""
QKA全局配置管理

提供简洁的配置接口
"""

from qka.utils.logger import logger


class Config:
    """全局配置管理类"""
    
    def __init__(self):
        self._source = 'akshare'  # 默认数据源
        # 未来可以在这里添加其他配置项
        # self._cache_enabled = True
        # self._log_level = 'INFO'
        # self._timeout = 30
    
    def __call__(self, source: str = None, **kwargs):
        """
        设置全局配置
        
        Args:
            source: 数据源类型 ('qmt', 'akshare')
            **kwargs: 其他配置参数（预留扩展）
        
        Returns:
            当前配置对象，支持链式调用
        """
        if source is not None:
            # 简单验证
            available_sources = ['qmt', 'akshare']
            if source.lower() not in available_sources:
                available = ', '.join(available_sources)
                raise ValueError(f"不支持的数据源类型: {source}，支持的数据源: {available}")
            
            self._source = source.lower()
            logger.info(f"已设置默认数据源为: {source}")
        
        # 处理其他配置参数（预留扩展）
        for key, value in kwargs.items():
            if hasattr(self, f'_{key}'):
                setattr(self, f'_{key}', value)
                logger.info(f"已设置配置项 {key} = {value}")
            else:
                logger.warning(f"未知的配置项: {key}")
        
        return self


# 全局配置实例
config = Config()
