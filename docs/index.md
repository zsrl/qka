# QKA - 快捷量化助手

欢迎使用 QKA（Quick Quantitative Assistant）文档！

## 简介

QKA 是一个简洁易用、功能完整的A股量化交易框架，支持数据获取、策略回测、实盘交易等全流程量化交易功能。

## 主要特性

- 🚀 **简洁易用**: 统一的API设计，降低量化交易门槛
- 📊 **数据丰富**: 支持Akshare数据源，提供多周期、多因子数据
- 🔄 **高效回测**: 基于时间序列的回测引擎，支持多股票横截面处理
- 💰 **实盘交易**: 集成QMT交易接口，支持实盘交易
- 📈 **可视化**: 内置Plotly图表，提供交互式回测结果展示
- 🔧 **模块化**: 高度模块化设计，易于扩展和维护

## 快速开始

### 安装

```bash
pip install qka
```

### 基本用法

```python
import qka

# 数据获取
data = qka.Data(symbols=['000001.SZ', '600000.SH'], period='1d')
df = data.get()

# 策略开发
class MyStrategy(qka.Strategy):
    def on_bar(self, date, get):
        close_prices = get('close')
        # 你的策略逻辑

# 回测分析
strategy = MyStrategy()
backtest = qka.Backtest(data, strategy)
backtest.run()
backtest.plot()
```

## 文档结构

- **快速开始**: 安装和基础使用指南
- **用户指南**: 详细的功能使用说明
- **API参考**: 完整的API文档
- **示例教程**: 实用的代码示例

## 获取帮助

- 查看 [GitHub Issues](https://github.com/zsrl/qka/issues) 获取技术支持
- 阅读 [用户指南](user-guide/data.md) 了解详细用法
- 参考 [API文档](api/core/data.md) 查看完整接口说明

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](https://github.com/zsrl/qka/blob/main/LICENSE) 文件了解详情。

---

**注意**: 量化交易存在风险，请在充分了解风险的情况下使用本框架。