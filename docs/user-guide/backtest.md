# 回测分析

QKA 提供了完整的回测引擎和分析工具，帮助您验证和优化交易策略。

## 基本回测

### 创建回测引擎

```python
from qka.core.backtest import BacktestEngine, Strategy
from qka.core.data import get_stock_data

# 创建策略
class SimpleStrategy(Strategy):
    def on_data(self, data):
        # 简单买入持有策略
        if not self.get_position('000001.SZ'):
            self.buy('000001.SZ', 100)

# 创建回测引擎
engine = BacktestEngine(
    initial_cash=1000000,
    start_date='2023-01-01',
    end_date='2023-12-31',
    commission_rate=0.0003
)

# 添加数据
data = get_stock_data('000001.SZ', start='2023-01-01', end='2023-12-31')
engine.add_data(data)

# 运行回测
strategy = SimpleStrategy()
result = engine.run(strategy)
```

### 回测配置

```python
# 详细配置回测参数
engine = BacktestEngine(
    initial_cash=1000000,      # 初始资金
    start_date='2023-01-01',   # 开始日期
    end_date='2023-12-31',     # 结束日期
    commission_rate=0.0003,    # 手续费率
    slippage_rate=0.001,       # 滑点率
    min_commission=5,          # 最小手续费
    benchmark='000001.SH',     # 基准指数
    frequency='daily',         # 数据频率
    price_type='close'         # 价格类型
)
```

## 回测结果分析

### 基本性能指标

```python
# 获取基本指标
print(f"总收益率: {result.total_return:.2%}")
print(f"年化收益率: {result.annual_return:.2%}")
print(f"夏普比率: {result.sharpe_ratio:.2f}")
print(f"最大回撤: {result.max_drawdown:.2%}")
print(f"胜率: {result.win_rate:.2%}")
print(f"盈亏比: {result.profit_loss_ratio:.2f}")

# 详细统计信息
stats = result.get_stats()
print(stats)
```

### 详细分析报告

```python
from qka.core.backtest import BacktestAnalyzer

analyzer = BacktestAnalyzer()

# 生成详细分析报告
report = analyzer.analyze(result)

# 输出报告
print("=" * 50)
print("策略表现分析报告")
print("=" * 50)
print(f"策略名称: {report.strategy_name}")
print(f"回测期间: {report.start_date} - {report.end_date}")
print(f"交易次数: {report.trade_count}")
print(f"平均持仓天数: {report.avg_holding_days:.1f}")
```

### 风险指标

```python
# 风险分析
risk_metrics = analyzer.calculate_risk_metrics(result)

print("\n风险指标:")
print(f"波动率: {risk_metrics.volatility:.2%}")
print(f"下行风险: {risk_metrics.downside_risk:.2%}")
print(f"VaR (95%): {risk_metrics.var_95:.2%}")
print(f"条件VaR: {risk_metrics.cvar:.2%}")
print(f"卡尔马比率: {risk_metrics.calmar_ratio:.2f}")
print(f"索提诺比率: {risk_metrics.sortino_ratio:.2f}")
```

## 可视化分析

### 收益曲线图

```python
from qka.core.plot import plot_returns, plot_drawdown

# 绘制收益曲线
plot_returns(
    result.returns,
    benchmark_returns=result.benchmark_returns,
    title="策略收益曲线"
)

# 绘制回撤图
plot_drawdown(result.returns, title="策略回撤分析")
```

### 交易分析图

```python
# 绘制交易点位图
plot_trades(
    result.price_data,
    result.trades,
    title="交易点位分析"
)

# 绘制仓位变化图
plot_positions(
    result.positions,
    title="仓位变化分析"
)
```

### 滚动指标图

```python
# 绘制滚动夏普比率
plot_rolling_sharpe(
    result.returns,
    window=252,  # 一年滚动窗口
    title="滚动夏普比率"
)

# 绘制滚动相关性
plot_rolling_correlation(
    result.returns,
    result.benchmark_returns,
    window=60,
    title="与基准的滚动相关性"
)
```

## 多策略对比

### 策略对比分析

```python
from qka.core.backtest import StrategyComparison

# 运行多个策略
strategies = [
    ('MA策略', MovingAverageStrategy(20, 50)),
    ('布林带策略', BollingerBandStrategy()),
    ('买入持有', BuyAndHoldStrategy())
]

results = []
for name, strategy in strategies:
    result = engine.run(strategy)
    result.strategy_name = name
    results.append(result)

# 对比分析
comparison = StrategyComparison(results)
comparison_report = comparison.generate_report()

print(comparison_report)
```

### 对比可视化

```python
# 绘制策略对比图
comparison.plot_comparison()

# 绘制风险收益散点图
comparison.plot_risk_return_scatter()

# 绘制滚动收益对比
comparison.plot_rolling_returns()
```

## 高级分析功能

### 因子归因分析

```python
from qka.core.backtest import FactorAttribution

# 因子归因分析
attribution = FactorAttribution()

# 添加因子数据
attribution.add_factor('market', market_returns)
attribution.add_factor('size', size_factor)
attribution.add_factor('value', value_factor)

# 执行归因分析
attribution_result = attribution.analyze(result.returns)

print(f"市场因子贡献: {attribution_result.market_contribution:.2%}")
print(f"规模因子贡献: {attribution_result.size_contribution:.2%}")
print(f"价值因子贡献: {attribution_result.value_contribution:.2%}")
print(f"选股能力: {attribution_result.alpha:.2%}")
```

### 压力测试

```python
from qka.core.backtest import StressTest

stress_test = StressTest()

# 市场崩盘场景
crash_scenario = stress_test.create_market_crash_scenario(
    crash_magnitude=-0.3,
    recovery_days=60
)

# 执行压力测试
stress_result = stress_test.run(strategy, crash_scenario)

print(f"压力测试最大损失: {stress_result.max_loss:.2%}")
print(f"恢复时间: {stress_result.recovery_days} 天")
```

### 蒙特卡洛模拟

```python
from qka.core.backtest import MonteCarloSimulation

# 蒙特卡洛模拟
mc_simulation = MonteCarloSimulation(
    strategy=strategy,
    num_simulations=1000,
    confidence_level=0.95
)

mc_result = mc_simulation.run()

print(f"预期收益率: {mc_result.expected_return:.2%}")
print(f"收益率置信区间: [{mc_result.lower_bound:.2%}, {mc_result.upper_bound:.2%}]")
print(f"破产概率: {mc_result.ruin_probability:.2%}")
```

## 组合优化

### 马科维茨优化

```python
from qka.core.backtest import PortfolioOptimizer

optimizer = PortfolioOptimizer()

# 添加资产
assets = ['000001.SZ', '000002.SZ', '600000.SH']
returns_data = get_returns_data(assets)

# 计算有效前沿
efficient_frontier = optimizer.calculate_efficient_frontier(returns_data)

# 获取最优组合
optimal_weights = optimizer.optimize(
    objective='max_sharpe',  # 最大化夏普比率
    constraints={'max_weight': 0.4}  # 单个资产最大权重40%
)

print(f"最优权重: {optimal_weights}")
```

### 风险平价组合

```python
# 风险平价组合
risk_parity_weights = optimizer.risk_parity_optimization(returns_data)
print(f"风险平价权重: {risk_parity_weights}")

# 最小方差组合
min_var_weights = optimizer.minimum_variance_optimization(returns_data)
print(f"最小方差权重: {min_var_weights}")
```

## 回测报告生成

### HTML报告

```python
from qka.core.backtest import ReportGenerator

generator = ReportGenerator()

# 生成HTML报告
html_report = generator.generate_html_report(
    result,
    include_charts=True,
    include_trades=True,
    output_path='backtest_report.html'
)

print("报告已生成: backtest_report.html")
```

### PDF报告

```python
# 生成PDF报告
pdf_report = generator.generate_pdf_report(
    result,
    template='professional',
    output_path='backtest_report.pdf'
)
```

### 自定义报告模板

```python
# 使用自定义模板
custom_report = generator.generate_report(
    result,
    template_path='custom_template.html',
    output_format='html'
)
```

## 实时监控

### 策略监控

```python
from qka.core.backtest import StrategyMonitor

monitor = StrategyMonitor()

# 添加监控指标
monitor.add_metric('drawdown', threshold=0.1)
monitor.add_metric('sharpe_ratio', threshold=1.0)
monitor.add_metric('win_rate', threshold=0.5)

# 启动监控
monitor.start_monitoring(strategy)
```

### 告警系统

```python
# 设置告警
monitor.add_alert(
    metric='max_drawdown',
    condition='greater_than',
    threshold=0.15,
    action='email',
    recipients=['trader@example.com']
)
```

## 最佳实践

1. **充分的历史数据**：使用足够长的历史数据进行回测
2. **样本外测试**：保留部分数据用于样本外验证
3. **交易成本考虑**：包含真实的手续费和滑点
4. **数据质量检查**：确保数据的准确性和完整性
5. **过拟合防范**：避免过度优化参数
6. **多时期验证**：在不同市场环境下测试策略
7. **风险评估**：关注风险调整后的收益

## 常见问题

### 数据对齐问题

```python
# 确保数据对齐
engine.set_data_alignment(method='forward_fill')
```

### 生存偏差

```python
# 使用时点股票池
engine.use_point_in_time_universe(True)
```

### 未来信息泄露

```python
# 设置信息延迟
engine.set_information_delay(days=1)
```

## API 参考

回测分析的详细API参考请查看 [Backtest API文档](../api/core/backtest.md)。

### 主要模块功能

- 回测引擎核心逻辑
- 性能指标计算
- 结果分析和报告
- 风险评估工具

更多详细信息和示例请参考API文档页面。
