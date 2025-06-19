"""
QKA 配置管理系统
提供统一的配置管理，支持环境变量、配置文件和代码配置
"""

import os
import json
from typing import Any, Dict, Optional
from pathlib import Path
from dataclasses import dataclass, asdict


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_cash: float = 1_000_000  # 初始资金
    commission_rate: float = 0.0003  # 手续费率
    slippage: float = 0.001  # 滑点率
    min_trade_amount: int = 100  # 最小交易股数
    max_position_ratio: float = 0.3  # 单只股票最大仓位比例
    benchmark: str = '000300.SH'  # 基准指数


@dataclass  
class DataConfig:
    """数据配置"""
    default_source: str = 'akshare'  # 默认数据源
    cache_enabled: bool = True  # 是否启用缓存
    cache_dir: str = './data_cache'  # 缓存目录
    cache_expire_days: int = 7  # 缓存过期天数
    quality_check: bool = True  # 是否进行数据质量检查
    auto_download: bool = True  # 是否自动下载缺失数据


@dataclass
class TradingConfig:
    """交易配置"""
    server_host: str = '0.0.0.0'
    server_port: int = 8000
    token_auto_generate: bool = True
    order_timeout: int = 30  # 订单超时时间(秒)
    max_retry_times: int = 3  # 最大重试次数
    heartbeat_interval: int = 30  # 心跳间隔(秒)


@dataclass
class LogConfig:
    """日志配置"""
    level: str = 'INFO'
    console_output: bool = True
    file_output: bool = True
    log_dir: str = './logs'
    max_file_size: str = '10MB'
    backup_count: int = 10
    format: str = '[%(levelname)s][%(asctime)s][%(name)s] %(message)s'


@dataclass
class PlotConfig:
    """绘图配置"""
    theme: str = 'plotly_white'
    figure_height: int = 600
    figure_width: int = 1000
    color_scheme: str = 'default'  # default, dark, colorful
    show_grid: bool = True
    auto_open: bool = True


class Config:
    """QKA 配置管理器"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径，为None时使用默认配置
        """
        # 默认配置
        self.backtest = BacktestConfig()
        self.data = DataConfig()
        self.trading = TradingConfig()
        self.log = LogConfig()
        self.plot = PlotConfig()
        
        # 加载配置文件
        if config_file and os.path.exists(config_file):
            self.load_from_file(config_file)
        
        # 加载环境变量配置
        self.load_from_env()
    
    def load_from_file(self, config_file: str):
        """从配置文件加载配置"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 更新各个配置段
            if 'backtest' in config_data:
                self._update_config(self.backtest, config_data['backtest'])
            if 'data' in config_data:
                self._update_config(self.data, config_data['data'])
            if 'trading' in config_data:
                self._update_config(self.trading, config_data['trading'])
            if 'log' in config_data:
                self._update_config(self.log, config_data['log'])
            if 'plot' in config_data:
                self._update_config(self.plot, config_data['plot'])
                
        except Exception as e:
            print(f"加载配置文件失败: {e}")
    
    def load_from_env(self):
        """从环境变量加载配置"""
        # 回测配置
        if os.getenv('QKA_INITIAL_CASH'):
            self.backtest.initial_cash = float(os.getenv('QKA_INITIAL_CASH'))
        if os.getenv('QKA_COMMISSION_RATE'):
            self.backtest.commission_rate = float(os.getenv('QKA_COMMISSION_RATE'))
        
        # 数据配置
        if os.getenv('QKA_DATA_SOURCE'):
            self.data.default_source = os.getenv('QKA_DATA_SOURCE')
        if os.getenv('QKA_CACHE_DIR'):
            self.data.cache_dir = os.getenv('QKA_CACHE_DIR')
          # 交易配置
        if os.getenv('QKA_SERVER_PORT'):
            self.trading.server_port = int(os.getenv('QKA_SERVER_PORT'))
    
    def _update_config(self, config_obj, config_dict: Dict[str, Any]):
        """更新配置对象"""
        for key, value in config_dict.items():
            if hasattr(config_obj, key):
                setattr(config_obj, key, value)
    
    def save_to_file(self, config_file: str):
        """保存配置到文件"""
        config_data = {
            'backtest': asdict(self.backtest),
            'data': asdict(self.data),
            'trading': asdict(self.trading),
            'log': asdict(self.log),
            'plot': asdict(self.plot)
        }
        
        # 确保目录存在（只有当目录路径不为空时）
        dir_path = os.path.dirname(config_file)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'backtest': asdict(self.backtest),
            'data': asdict(self.data),
            'trading': asdict(self.trading),
            'log': asdict(self.log),
            'plot': asdict(self.plot)
        }
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """获取配置值"""
        section_obj = getattr(self, section, None)
        if section_obj:
            return getattr(section_obj, key, default)
        return default
    
    def set(self, section: str, key: str, value: Any):
        """设置配置值"""
        section_obj = getattr(self, section, None)
        if section_obj:
            setattr(section_obj, key, value)


# 全局配置实例
config = Config()


def load_config(config_file: Optional[str] = None) -> Config:
    """
    加载配置文件
    
    Args:
        config_file: 配置文件路径
        
    Returns:
        Config对象
        
    Examples:
        # 使用默认配置
        config = load_config()
        
        # 从文件加载配置
        config = load_config('config.json')
        
        # 访问配置
        print(config.backtest.initial_cash)
        print(config.data.default_source)
    """
    global config
    config = Config(config_file)
    return config


def create_sample_config(file_path: str = 'qka_config.json'):
    """
    创建示例配置文件
    
    Args:
        file_path: 配置文件路径
    """
    sample_config = Config()
    sample_config.save_to_file(file_path)
    print(f"示例配置文件已创建: {file_path}")


if __name__ == '__main__':
    # 创建示例配置文件
    create_sample_config()
    
    # 测试配置加载
    cfg = load_config('qka_config.json')
    print("配置加载完成:")
    print(f"初始资金: {cfg.backtest.initial_cash:,}")
    print(f"数据源: {cfg.data.default_source}")
    print(f"服务器端口: {cfg.trading.server_port}")
