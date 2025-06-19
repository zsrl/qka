"""
QKA 基础功能测试
测试配置管理、事件系统和日志系统是否正常工作
"""

def test_config_system():
    """测试配置管理系统"""
    print("=" * 30)
    print("测试配置管理系统")
    print("=" * 30)
    
    try:
        from qka.core.config import config, create_sample_config
        
        # 创建示例配置
        create_sample_config("test_config.json")
        print("✅ 配置文件创建成功")
        
        # 测试配置访问
        print(f"初始资金: {config.backtest.initial_cash:,}")
        print(f"数据源: {config.data.default_source}")
        print("✅ 配置系统正常")
        
    except Exception as e:
        print(f"❌ 配置系统错误: {e}")
        import traceback
        traceback.print_exc()


def test_event_system():
    """测试事件系统"""
    print("\n" + "=" * 30)
    print("测试事件系统")
    print("=" * 30)
    
    try:
        from qka.core.events import EventType, event_handler, emit_event, start_event_engine, stop_event_engine
        import time
        
        # 定义事件处理器
        @event_handler(EventType.DATA_LOADED)
        def on_data_loaded(event):
            print(f"📊 收到数据加载事件: {event.data}")
        
        # 启动事件引擎
        start_event_engine()
        print("✅ 事件引擎启动成功")
        
        # 发送测试事件
        emit_event(EventType.DATA_LOADED, {"test": "data"})
        time.sleep(0.5)  # 等待事件处理
        
        # 停止事件引擎
        stop_event_engine()
        print("✅ 事件系统正常")
        
    except Exception as e:
        print(f"❌ 事件系统错误: {e}")
        import traceback
        traceback.print_exc()


def test_logging_system():
    """测试日志系统"""
    print("\n" + "=" * 30)
    print("测试日志系统")
    print("=" * 30)
    
    try:
        from qka.utils.logger import create_logger
        
        # 创建日志记录器
        logger = create_logger('test', colored_console=True)
        
        logger.info("日志系统测试 - 信息")
        logger.warning("日志系统测试 - 警告")
        logger.error("日志系统测试 - 错误")
        
        print("✅ 日志系统正常")
        
    except Exception as e:
        print(f"❌ 日志系统错误: {e}")
        import traceback
        traceback.print_exc()


def test_tools():
    """测试工具类"""
    print("\n" + "=" * 30)
    print("测试工具类")
    print("=" * 30)
    
    try:
        from qka.utils.tools import Cache, Timer, format_number
        import time
        
        # 测试缓存
        cache = Cache(max_size=10, ttl=60)
        cache.set('test_key', 'test_value')
        value = cache.get('test_key')
        print(f"缓存测试: {value}")
        
        # 测试计时器
        with Timer() as t:
            time.sleep(0.01)
        print(f"计时器测试: {t.elapsed():.4f}秒")
        
        # 测试格式化
        formatted = format_number(123456.789)
        print(f"格式化测试: {formatted}")
        
        print("✅ 工具类正常")
        
    except Exception as e:
        print(f"❌ 工具类错误: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主测试函数"""
    print("🧪 QKA 基础功能测试开始\n")
    
    test_config_system()
    test_event_system()
    test_logging_system()
    test_tools()
    
    print("\n" + "=" * 30)
    print("🎉 测试完成")
    print("=" * 30)


if __name__ == "__main__":
    main()
