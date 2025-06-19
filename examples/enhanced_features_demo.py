"""
QKA 增强功能演示
展示配置管理、事件系统、日志系统等新功能
"""

import time
import qka
from qka.core.config import config, load_config, create_sample_config
from qka.core.events import EventType, event_handler, emit_event, start_event_engine, stop_event_engine
from qka.core.backtest import Strategy
from qka.utils.logger import create_logger, get_structured_logger
from qka.utils.tools import timer, retry


def demo_config_system():
    """演示配置管理系统"""
    print("=" * 50)
    print("🔧 配置管理系统演示")
    print("=" * 50)
    
    # 创建示例配置文件
    create_sample_config("demo_config.json")
    
    # 加载配置
    cfg = load_config("demo_config.json")
    
    print(f"初始资金: {qka.config.backtest.initial_cash:,}")
    print(f"手续费率: {qka.config.backtest.commission_rate}")
    print(f"数据源: {qka.config.data.default_source}")
    print(f"缓存目录: {qka.config.data.cache_dir}")
    print(f"服务器端口: {qka.config.trading.server_port}")
    
    # 修改配置
    qka.config.backtest.initial_cash = 2_000_000
    print(f"修改后初始资金: {qka.config.backtest.initial_cash:,}")


def demo_event_system():
    """演示事件驱动系统"""
    print("\n" + "=" * 50)
    print("📡 事件驱动系统演示")
    print("=" * 50)
    
    # 定义事件处理器
    @event_handler(EventType.DATA_LOADED)
    def on_data_loaded(event):
        print(f"📊 数据加载完成: {event.data}")
    
    @event_handler(EventType.ORDER_FILLED)
    def on_order_filled(event):
        print(f"✅ 订单成交: {event.data}")
    
    @event_handler(EventType.SIGNAL_GENERATED)
    def on_signal_generated(event):
        print(f"🎯 信号生成: {event.data}")
    
    # 启动事件引擎
    start_event_engine()
    
    # 发送测试事件
    emit_event(EventType.DATA_LOADED, {"symbol": "000001.SZ", "rows": 1000})
    emit_event(EventType.ORDER_FILLED, {"order_id": "123", "symbol": "000001.SZ", "price": 10.5})
    emit_event(EventType.SIGNAL_GENERATED, {"symbol": "000002.SZ", "signal": "BUY", "strength": 0.8})
    
    # 等待事件处理
    time.sleep(0.5)
    
    # 查看事件统计
    stats = qka.event_engine.get_statistics()
    print(f"\n📈 事件统计:")
    for event_type, count in stats['event_count'].items():
        print(f"  {event_type}: {count}次")


def demo_logging_system():
    """演示增强日志系统"""
    print("\n" + "=" * 50)
    print("📝 增强日志系统演示")
    print("=" * 50)
    
    # 创建彩色日志记录器
    logger = create_logger('demo', colored_console=True, level='DEBUG')
    
    logger.debug("这是调试信息")
    logger.info("这是普通信息")
    logger.warning("这是警告信息")
    logger.error("这是错误信息")
    
    # 结构化日志
    struct_logger = get_structured_logger('demo_struct')
    struct_logger.info("用户登录", user_id=12345, ip="192.168.1.100", action="login")
    struct_logger.error("交易失败", symbol="000001.SZ", reason="余额不足", amount=10000)
    
    print("📁 日志文件已保存到 logs 目录")


class EnhancedStrategy(Strategy):
    """增强的策略类，集成事件系统"""
    
    def __init__(self):
        super().__init__()
        self.logger = create_logger('strategy', colored_console=True)
    
    def on_start(self, broker):
        """策略启动时的事件处理"""
        self.logger.info(f"策略 {self.name} 启动")
        emit_event(EventType.STRATEGY_START, {
            "strategy": self.name,
            "initial_cash": broker.initial_cash
        })
    
    def on_bar(self, data, broker, current_date):
        """策略核心逻辑"""
        for symbol, df in data.items():
            if len(df) < 20:
                continue
            
            current_price = df['close'].iloc[-1]
            ma20 = df['close'].rolling(20).mean().iloc[-1]
            
            # 生成交易信号
            if current_price > ma20 and broker.get_position(symbol) == 0:
                # 发送买入信号事件
                emit_event(EventType.SIGNAL_GENERATED, {
                    "symbol": symbol,
                    "signal": "BUY",
                    "price": current_price,
                    "reason": "价格突破20日均线"
                })
                
                # 执行买入
                if broker.buy(symbol, 0.3, current_price):
                    self.logger.info(f"买入 {symbol} @ {current_price:.2f}")
                    emit_event(EventType.ORDER_FILLED, {
                        "symbol": symbol,
                        "action": "BUY",
                        "price": current_price,
                        "amount": broker.get_position(symbol)
                    })
            
            elif current_price < ma20 and broker.get_position(symbol) > 0:
                # 发送卖出信号事件
                emit_event(EventType.SIGNAL_GENERATED, {
                    "symbol": symbol,
                    "signal": "SELL",
                    "price": current_price,
                    "reason": "价格跌破20日均线"
                })
                
                # 执行卖出
                if broker.sell(symbol, 1.0, current_price):
                    self.logger.info(f"卖出 {symbol} @ {current_price:.2f}")
                    emit_event(EventType.ORDER_FILLED, {
                        "symbol": symbol,
                        "action": "SELL",
                        "price": current_price,
                        "amount": 0
                    })
    
    def on_end(self, broker):
        """策略结束时的事件处理"""
        self.logger.info(f"策略 {self.name} 结束")
        emit_event(EventType.STRATEGY_END, {
            "strategy": self.name,
            "final_value": broker.get_total_value({})
        })


@timer
def demo_enhanced_backtest():
    """演示增强回测功能"""
    print("\n" + "=" * 50)
    print("🚀 增强回测演示")
    print("=" * 50)
    
    # 使用配置系统的参数
    print(f"使用配置: 初始资金 {qka.config.backtest.initial_cash:,}, 手续费 {qka.config.backtest.commission_rate}")
    
    # 获取数据
    data_obj = qka.data(qka.config.data.default_source, stocks=['000001', '000002'])
    
    # 运行回测
    result = qka.backtest(
        data=data_obj,
        strategy=EnhancedStrategy(),
        start_time='2023-06-01',
        end_time='2023-08-31'
    )
    
    # 输出结果
    print(f"\n📊 回测结果:")
    print(f"总收益率: {result['total_return']:.2%}")
    print(f"年化收益率: {result['annual_return']:.2%}")
    print(f"最大回撤: {result['max_drawdown']:.2%}")
    print(f"夏普比率: {result['sharpe_ratio']:.2f}")
    print(f"交易次数: {result['total_trades']}")


@retry(max_attempts=3, delay=1.0)
def demo_tools():
    """演示工具函数"""
    print("\n" + "=" * 50)
    print("🛠️ 工具函数演示")
    print("=" * 50)
    
    from qka.utils.tools import format_number, format_percentage, format_currency
    from qka.utils.tools import Timer, Cache
    
    # 格式化工具
    print(f"数字格式化: {format_number(1234567.89)}")
    print(f"百分比格式化: {format_percentage(0.1567)}")
    print(f"货币格式化: {format_currency(123456.78)}")
    
    # 计时器
    with Timer() as t:
        time.sleep(0.1)
        print(f"计时器测试: {t.elapsed():.3f}秒")
    
    # 缓存
    cache = Cache(max_size=100, ttl=60)
    cache.set('test_key', 'test_value')
    print(f"缓存测试: {cache.get('test_key')}")
    
    print("✅ 重试装饰器测试成功")


def main():
    """主演示函数"""
    print("🎉 QKA 增强功能演示")
    
    try:
        # 演示各个功能模块
        demo_config_system()
        demo_event_system()
        demo_logging_system()
        demo_tools()
        demo_enhanced_backtest()
        
        print("\n" + "=" * 50)
        print("✨ 所有功能演示完成")
        print("=" * 50)
        
        # 查看最终事件统计
        final_stats = qka.event_engine.get_statistics()
        print(f"\n📊 最终事件统计:")
        for event_type, count in final_stats['event_count'].items():
            print(f"  {event_type}: {count}次")
        
    except Exception as e:
        print(f"❌ 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 停止事件引擎
        stop_event_engine()
        print("\n🔚 事件引擎已关闭")


if __name__ == "__main__":
    main()
