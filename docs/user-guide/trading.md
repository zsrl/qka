# 实盘交易

QKA 提供完整的实盘交易功能，支持通过 QMT 接口进行 A 股实盘交易。

## 交易架构

QKA 的实盘交易采用客户端-服务器架构：

```
策略代码 → QMTClient → QMTServer → QMT交易接口 → 券商系统
```

## 准备工作

### 1. 安装 QMT

确保已安装 QMT 并正确配置：
- 下载并安装 QMT
- 获取有效的账户 ID
- 配置交易权限

### 2. 启动交易服务器

```python
from qka.brokers.server import QMTServer

# 创建交易服务器
server = QMTServer(
    account_id="YOUR_ACCOUNT_ID",      # 你的账户ID
    mini_qmt_path="YOUR_QMT_PATH",     # QMT安装路径
    host="0.0.0.0",                    # 服务器地址
    port=8000                          # 服务器端口
)

# 启动服务器
server.start()  # 会打印token供客户端使用
```

### 3. 使用交易客户端

```python
from qka.brokers.client import QMTClient

# 创建交易客户端
client = QMTClient(
    base_url="http://localhost:8000",  # 服务器地址
    token="服务器打印的token"           # 访问令牌
)
```

## 交易操作

### 查询账户信息

```python
# 查询股票资产
assets = client.api("query_stock_asset")
print(assets)

# 查询资金信息
capital = client.api("query_account_status")
print(capital)

# 查询持仓
positions = client.api("query_stock_positions")
print(positions)
```

### 下单交易

```python
from xtquant import xtconstant

# 买入股票
result = client.api(
    "order_stock",
    stock_code='600000.SH',           # 股票代码
    order_type=xtconstant.STOCK_BUY,  # 买入
    order_volume=1000,                # 数量
    price_type=xtconstant.FIX_PRICE,  # 限价单
    price=10.5                        # 价格
)

# 卖出股票
result = client.api(
    "order_stock", 
    stock_code='600000.SH',
    order_type=xtconstant.STOCK_SELL,  # 卖出
    order_volume=500,
    price_type=xtconstant.FIX_PRICE,
    price=11.0
)
```

### 订单管理

```python
# 查询委托
orders = client.api("query_stock_orders")
print(orders)

# 查询成交
trades = client.api("query_stock_trades") 
print(trades)

# 撤单
cancel_result = client.api(
    "cancel_order_stock",
    order_id="订单ID"
)
```

## 策略实盘化

### 回测转实盘

将回测策略转换为实盘策略：

```python
class RealTimeStrategy:
    def __init__(self, client):
        self.client = client
        self.positions = {}
    
    def run(self):
        """运行实盘策略"""
        while True:
            # 获取实时数据
            data = self.get_realtime_data()
            
            # 执行策略逻辑
            signals = self.generate_signals(data)
            
            # 执行交易
            self.execute_trades(signals)
            
            # 等待下一轮
            time.sleep(60)  # 每分钟执行一次
    
    def get_realtime_data(self):
        """获取实时数据"""
        # 可以通过其他数据源获取实时数据
        pass
    
    def generate_signals(self, data):
        """生成交易信号"""
        # 策略逻辑
        pass
    
    def execute_trades(self, signals):
        """执行交易"""
        for symbol, signal in signals.items():
            if signal == 'buy':
                self.buy(symbol)
            elif signal == 'sell':
                self.sell(symbol)
    
    def buy(self, symbol):
        """买入操作"""
        # 获取当前价格
        # 计算买入数量
        # 执行买入
        pass
    
    def sell(self, symbol):
        """卖出操作"""
        # 执行卖出
        pass
```

## 风险控制

### 仓位管理

```python
class RiskManagedTrader:
    def __init__(self, client, max_position_ratio=0.1):
        self.client = client
        self.max_position_ratio = max_position_ratio
    
    def calculate_position_size(self, symbol, price):
        """计算合理的买入数量"""
        # 查询总资产
        assets = self.client.api("query_stock_asset")
        total_assets = assets['总资产']
        
        # 单股票仓位限制
        max_position_value = total_assets * self.max_position_ratio
        max_shares = int(max_position_value / price)
        
        return max_shares
```

### 交易频率控制

```python
import time

class RateLimitedTrader:
    def __init__(self, client, max_trades_per_minute=5):
        self.client = client
        self.max_trades_per_minute = max_trades_per_minute
        self.trade_times = []
    
    def can_trade(self):
        """检查是否可以交易"""
        current_time = time.time()
        # 移除1分钟前的交易记录
        self.trade_times = [t for t in self.trade_times 
                           if current_time - t < 60]
        
        return len(self.trade_times) < self.max_trades_per_minute
    
    def record_trade(self):
        """记录交易时间"""
        self.trade_times.append(time.time())
```

## 监控和日志

### 交易监控

```python
class TradingMonitor:
    def __init__(self, client):
        self.client = client
    
    def monitor_positions(self):
        """监控持仓"""
        positions = self.client.api("query_stock_positions")
        for position in positions:
            print(f"持仓: {position['证券代码']} {position['当前数量']}股")
    
    def monitor_orders(self):
        """监控委托"""
        orders = self.client.api("query_stock_orders")
        for order in orders:
            print(f"委托: {order['证券代码']} {order['委托状态']}")
```

### 错误处理

```python
try:
    result = client.api("order_stock", ...)
    if not result.get('success'):
        print(f"交易失败: {result.get('detail')}")
except Exception as e:
    print(f"API调用失败: {e}")
    # 重试逻辑或报警
```

## 最佳实践

1. **小资金测试**: 先用小资金测试策略
2. **风险控制**: 设置严格的仓位和止损限制
3. **监控报警**: 设置交易异常报警
4. **日志记录**: 详细记录所有交易操作
5. **备份策略**: 准备手动干预方案

## 注意事项

1. **交易时间**: 只在交易时间段内运行策略
2. **网络稳定性**: 确保网络连接稳定
3. **系统维护**: 定期检查系统状态
4. **合规性**: 遵守相关交易规则

## 相关链接

- [API参考 - 交易模块](../api/brokers.md)
- [快速开始 - 第一个策略](../getting-started/first-strategy.md)
- [用户指南 - 回测分析](backtest.md)