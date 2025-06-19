# Config API 参考

::: qka.core.config
    options:
      show_root_heading: true
      show_source: true
      heading_level: 2
      members_order: source
      show_signature_annotations: true
      separate_signature: true
      
## 配置示例

### 基本用法

```python
from qka.core.config import Config

# 创建配置实例
config = Config()

# 从文件加载配置
config.load_from_file('config.yaml')

# 获取配置值
database_url = config.get('database.url', 'sqlite:///default.db')
debug_mode = config.get('debug', False)

# 设置配置值
config.set('api.timeout', 30)
config.set('logging.level', 'INFO')
```

### 环境变量配置

```python
import os

# 设置环境变量
os.environ['QKA_DEBUG'] = 'true'
os.environ['QKA_DATABASE_URL'] = 'postgresql://localhost/qka'

# 加载环境变量配置
config = Config()
config.load_from_env()

# 访问配置
debug = config.get('debug')  # True
db_url = config.get('database.url')  # postgresql://localhost/qka
```

### 配置文件示例

#### YAML格式 (config.yaml)

```yaml
# QKA量化系统配置文件

# 数据库配置
database:
  url: "sqlite:///qka.db"
  pool_size: 10
  echo: false

# API配置
api:
  host: "0.0.0.0"
  port: 8000
  timeout: 30
  rate_limit: 100

# 日志配置
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "logs/qka.log"
  max_size: "10MB"
  backup_count: 5

# 交易配置
trading:
  commission: 0.001
  slippage: 0.0005
  initial_capital: 100000

# 风险管理
risk:
  max_position_size: 0.1
  max_drawdown: 0.2
  stop_loss: 0.05

# 策略配置
strategy:
  default_lookback: 252
  rebalance_frequency: "monthly"
  
# 通知配置
notifications:
  email:
    enabled: false
    smtp_server: "smtp.gmail.com"
    port: 587
  wechat:
    enabled: false
    webhook_url: ""
```

#### JSON格式 (config.json)

```json
{
  "database": {
    "url": "sqlite:///qka.db",
    "pool_size": 10,
    "echo": false
  },
  "api": {
    "host": "0.0.0.0",
    "port": 8000,
    "timeout": 30
  },
  "logging": {
    "level": "INFO",
    "file": "logs/qka.log"
  }
}
```

### 配置验证

```python
from qka.core.config import Config

config = Config()

# 定义配置验证规则
validation_rules = {
    'database.url': {'required': True, 'type': str},
    'api.port': {'required': True, 'type': int, 'min': 1, 'max': 65535},
    'trading.commission': {'type': float, 'min': 0, 'max': 1},
    'logging.level': {'type': str, 'choices': ['DEBUG', 'INFO', 'WARNING', 'ERROR']}
}

# 验证配置
try:
    config.validate(validation_rules)
    print("配置验证通过")
except ConfigError as e:
    print(f"配置验证失败: {e}")
```

### 动态配置更新

```python
# 监听配置文件变化
config.watch_file('config.yaml', auto_reload=True)

# 注册配置变更回调
@config.on_change('database.url')
def on_database_change(old_value, new_value):
    print(f"数据库配置从 {old_value} 更改为 {new_value}")
    # 重新初始化数据库连接
    reconnect_database(new_value)

# 手动重新加载配置
config.reload()
```

### 配置模板生成

```python
# 生成示例配置文件
config.create_sample_config('sample_config.yaml')

# 生成配置模板
template = config.get_config_template()
print(template)
```

## 最佳实践

1. **配置文件管理**
   - 使用版本控制管理配置模板
   - 敏感信息使用环境变量
   - 不同环境使用不同配置文件

2. **配置验证**
   - 应用启动时验证必需配置
   - 定义清晰的验证规则
   - 提供有意义的错误信息

3. **配置更新**
   - 谨慎使用动态配置更新
   - 关键配置变更需要重启服务
   - 记录配置变更日志

4. **安全考虑**
   - 敏感配置信息加密存储
   - 限制配置文件访问权限
   - 审计配置变更操作
