# 配置管理

QKA 提供了强大而灵活的配置管理系统，支持多种配置方式和模块化配置。

## 快速开始

### 创建配置文件

```python
from qka.core.config import create_sample_config

# 创建示例配置文件
create_sample_config('my_config.json')
```

### 加载配置

```python
import qka
from qka.core.config import load_config

# 加载自定义配置
config = load_config('my_config.json')

# 使用全局配置
print(f"初始资金: {qka.config.backtest.initial_cash:,}")
print(f"数据源: {qka.config.data.default_source}")
```

## 配置结构

### 回测配置 (BacktestConfig)

```python
# 访问回测配置
config.backtest.initial_cash = 2_000_000      # 初始资金
config.backtest.commission_rate = 0.0003      # 手续费率
config.backtest.slippage = 0.001              # 滑点率
config.backtest.min_trade_amount = 100        # 最小交易股数
config.backtest.max_position_ratio = 0.3      # 单只股票最大仓位比例
config.backtest.benchmark = '000300.SH'       # 基准指数
```

### 数据配置 (DataConfig)

```python
# 访问数据配置
config.data.default_source = 'akshare'        # 默认数据源
config.data.cache_enabled = True              # 是否启用缓存
config.data.cache_dir = './data_cache'        # 缓存目录
config.data.cache_expire_days = 7             # 缓存过期天数
config.data.quality_check = True              # 数据质量检查
config.data.auto_download = True              # 自动下载缺失数据
```

### 交易配置 (TradingConfig)

```python
# 访问交易配置
config.trading.server_host = '0.0.0.0'        # 服务器地址
config.trading.server_port = 8000             # 服务器端口
config.trading.token_auto_generate = True     # 自动生成token
config.trading.order_timeout = 30             # 订单超时时间(秒)
config.trading.max_retry_times = 3            # 最大重试次数
config.trading.heartbeat_interval = 30        # 心跳间隔(秒)
```

### 日志配置 (LogConfig)

```python
# 访问日志配置
config.log.level = 'INFO'                     # 日志级别
config.log.console_output = True              # 控制台输出
config.log.file_output = True                 # 文件输出
config.log.log_dir = './logs'                 # 日志目录
config.log.max_file_size = '10MB'             # 最大文件大小
config.log.backup_count = 10                  # 备份文件数量
```

### 绘图配置 (PlotConfig)

```python
# 访问绘图配置
config.plot.theme = 'plotly_white'            # 图表主题
config.plot.figure_height = 600               # 图表高度
config.plot.figure_width = 1000               # 图表宽度
config.plot.color_scheme = 'default'          # 色彩方案
config.plot.show_grid = True                  # 显示网格
config.plot.auto_open = True                  # 自动打开图表
```

## 配置方式

### 1. 配置文件

创建 JSON 格式的配置文件：

```json
{
  "backtest": {
    "initial_cash": 2000000,
    "commission_rate": 0.0002,
    "benchmark": "000300.SH"
  },
  "data": {
    "default_source": "qmt",
    "cache_enabled": true,
    "cache_dir": "./cache"
  },
  "trading": {
    "server_port": 9000,
    "order_timeout": 60
  }
}
```

加载配置：

```python
from qka.core.config import load_config

config = load_config('production.json')
```

### 2. 环境变量

支持通过环境变量覆盖配置：

```bash
# 设置环境变量
export QKA_INITIAL_CASH=5000000
export QKA_DATA_SOURCE=qmt
export QKA_SERVER_PORT=9000
export QKA_COMMISSION_RATE=0.0002
export QKA_CACHE_DIR=/tmp/qka_cache
```

环境变量会自动覆盖配置文件中的值。

### 3. 代码配置

直接在代码中修改配置：

```python
import qka

# 修改全局配置
qka.config.backtest.initial_cash = 3_000_000
qka.config.data.default_source = 'tushare'
qka.config.trading.server_port = 8080

# 或者创建新的配置实例
from qka.core.config import Config

custom_config = Config()
custom_config.backtest.initial_cash = 5_000_000
```

## 高级用法

### 配置继承

```python
from qka.core.config import Config

# 基础配置
base_config = Config('base.json')

# 继承并修改
prod_config = Config()
prod_config.__dict__.update(base_config.__dict__)
prod_config.backtest.initial_cash = 10_000_000
prod_config.save_to_file('production.json')
```

### 动态配置更新

```python
# 运行时修改配置
def update_config_for_market_hours():
    if is_market_open():
        qka.config.data.auto_download = True
        qka.config.trading.heartbeat_interval = 10
    else:
        qka.config.data.auto_download = False
        qka.config.trading.heartbeat_interval = 60
```

### 配置验证

```python
def validate_config(config):
    """验证配置的有效性"""
    assert config.backtest.initial_cash > 0, "初始资金必须大于0"
    assert config.backtest.commission_rate >= 0, "手续费率不能为负数"
    assert config.trading.server_port > 1024, "端口号必须大于1024"
    
    print("✅ 配置验证通过")

# 使用验证
validate_config(qka.config)
```

## 最佳实践

### 1. 环境分离

为不同环境创建不同的配置文件：

```
config/
├── development.json    # 开发环境
├── testing.json       # 测试环境
├── staging.json       # 预发布环境
└── production.json    # 生产环境
```

```python
import os
from qka.core.config import load_config

# 根据环境变量选择配置
env = os.getenv('QKA_ENV', 'development')
config = load_config(f'config/{env}.json')
```

### 2. 敏感信息处理

敏感信息(如API密钥)建议通过环境变量配置：

```bash
# .env 文件
QKA_API_KEY=your_secret_api_key
QKA_DATABASE_URL=postgresql://user:pass@localhost/db
```

```python
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 在配置中使用
api_key = os.getenv('QKA_API_KEY')
```

### 3. 配置备份

```python
from qka.core.config import Config
from datetime import datetime

def backup_config():
    """备份当前配置"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'config_backup_{timestamp}.json'
    qka.config.save_to_file(backup_file)
    print(f"配置已备份到: {backup_file}")

# 定期备份
backup_config()
```

## 配置示例

### 开发环境配置

```json
{
  "backtest": {
    "initial_cash": 1000000,
    "commission_rate": 0.0003
  },
  "data": {
    "default_source": "akshare",
    "cache_enabled": true,
    "cache_dir": "./dev_cache"
  },
  "log": {
    "level": "DEBUG",
    "console_output": true
  }
}
```

### 生产环境配置

```json
{
  "backtest": {
    "initial_cash": 10000000,
    "commission_rate": 0.0002
  },
  "data": {
    "default_source": "qmt",
    "cache_enabled": true,
    "cache_dir": "/var/cache/qka"
  },
  "log": {
    "level": "INFO",
    "file_output": true,
    "log_dir": "/var/log/qka"
  },
  "trading": {
    "server_host": "0.0.0.0",
    "server_port": 8000
  }
}
```

## API 参考

配置管理的详细API参考请查看 [Config API文档](../api/core/config.md)。

### 主要类和函数

- **Config** - 主配置管理类
- **load_config** - 加载配置函数
- **create_sample_config** - 创建示例配置函数

更多详细信息和使用示例请参考API文档页面。
