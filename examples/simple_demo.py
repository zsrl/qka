"""
QKA 简化功能演示
演示阶段1的核心增强功能
"""

print("🎉 QKA 增强功能演示")
print("=" * 50)

# 1. 配置管理系统演示
print("\n📋 配置管理系统")
print("-" * 30)

from qka.core.config import config, create_sample_config

# 创建示例配置
create_sample_config("demo_config.json")
print("✅ 配置文件创建成功")

# 显示当前配置
print(f"初始资金: {config.backtest.initial_cash:,}")
print(f"手续费率: {config.backtest.commission_rate}")
print(f"数据源: {config.data.default_source}")
print(f"服务器端口: {config.trading.server_port}")

# 2. 事件系统演示
print("\n📡 事件驱动系统")
print("-" * 30)

from qka.core.events import EventType, event_handler, emit_event, start_event_engine, stop_event_engine
import time

# 定义事件处理器
@event_handler(EventType.DATA_LOADED)
def on_data_loaded(event):
    print(f"📊 数据加载事件: {event.data}")

@event_handler(EventType.SIGNAL_GENERATED)
def on_signal_generated(event):
    print(f"🎯 信号生成事件: {event.data}")

# 启动事件引擎
start_event_engine()
print("✅ 事件引擎启动成功")

# 发送测试事件
emit_event(EventType.DATA_LOADED, {"symbol": "000001.SZ", "rows": 1000})
emit_event(EventType.SIGNAL_GENERATED, {"symbol": "000002.SZ", "signal": "BUY"})

# 等待事件处理
time.sleep(1)

# 3. 日志系统演示
print("\n📝 日志系统")
print("-" * 30)

from qka.utils.logger import create_logger

logger = create_logger('demo', colored_console=True)
logger.info("这是一条信息日志")
logger.warning("这是一条警告日志")
logger.error("这是一条错误日志")

print("✅ 彩色日志显示正常")

# 4. 工具类演示
print("\n🛠️ 工具类")
print("-" * 30)

from qka.utils.tools import Cache, Timer, format_number, format_percentage

# 缓存测试
cache = Cache(max_size=10, ttl=60)
cache.set('test', 'value')
print(f"缓存测试: {cache.get('test')}")

# 计时器测试
with Timer() as t:
    time.sleep(0.01)
print(f"计时器测试: {t.elapsed():.4f}秒")

# 格式化测试
print(f"数字格式化: {format_number(123456.789)}")
print(f"百分比格式化: {format_percentage(0.1234)}")

# 获取统计信息
from qka.core.events import event_engine
stats = event_engine.get_statistics()
print(f"\n📊 事件统计:")
for event_type, count in stats['event_count'].items():
    print(f"  {event_type}: {count}次")

# 停止事件引擎
stop_event_engine()

print("\n" + "=" * 50)
print("✨ 演示完成！阶段1功能正常运行")
print("=" * 50)

print("""
🎯 阶段1完成的功能:
  ✅ 配置管理系统 - 统一的配置管理
  ✅ 事件驱动框架 - 发布-订阅模式
  ✅ 增强日志系统 - 彩色和结构化日志
  ✅ 基础工具类 - 缓存、计时器、格式化等

🔄 下一步: 阶段2 - 数据层增强
  📊 数据缓存机制
  🔍 数据质量检查
  📈 多频率数据支持
  🔄 增量数据更新
""")
