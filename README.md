# QKA — 快量化

<p align="center">
  <a href="https://qka.quantai.chat" target="_blank">
    <img src="https://img.shields.io/badge/文档站-qka.quantai.chat-blue?style=flat" alt="文档站">
  </a>
  <a href="https://pypi.org/project/qka/">
    <img src="https://img.shields.io/pypi/v/qka?color=blue" alt="PyPI">
  </a>
  <a href="https://github.com/zsrl/qka">
    <img src="https://img.shields.io/badge/python-3.10+-blue" alt="Python">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </a>
</p>

**快捷量化助手（Quick Quantitative Assistant）** — 简洁易用的 A 股量化交易框架。三行代码完成回测，从研究到实盘一路畅通。

---

## 三行代码跑回测

```python
import qka

bt = qka.Backtest(qka.Strategy()).run(benchmark='000300.SH')
bt.report('我的策略')   # 生成交互式 HTML 报告，浏览器自动打开
```

这就是全部。数据获取、回测执行、绩效计算、基准对比、图表可视化，一行搞定。

## 安装

```bash
# 推荐 — 用 uv
uv add qka

# 或
pip install qka
```

## 快速上手

### 1. 拿数据

```python
import qka

data = qka.Data(
    symbols=['000001.SZ', '600000.SH'],
    period='1d',
    adjust='qfq'
)
df = data.get()
```

### 2. 写策略

```python
class MyStrategy(qka.Strategy):
    def on_bar(self, date, get):
        close = get('close')
        # 价格低于10元买入1000股（注意前复权可能导致早期价格为负）
        if '000001.SZ' in close and 0 < close['000001.SZ'] < 10:
            self.broker.buy('000001.SZ', close['000001.SZ'], 1000)
```

### 3. 跑回测 + 看报告

```python
bt = qka.Backtest(data, MyStrategy())
bt.run(benchmark='000300.SH')          # 自动获取沪深300做基准对比
bt.report(title='我的策略')            # 一键生成HTML报告
```

生成的 HTML 报告包含：
- 📊 净值曲线 + 基准对比（交互式 Plotly 图表）
- 📉 回撤曲线
- 📅 月度收益率热力图
- 📋 交易明细（含手续费）
- 🏆 绩效指标：年化收益、夏普比率、最大回撤、胜率、盈亏比……

### 4. 调整成本参数

```python
bt = qka.Backtest(
    data, strategy,
    commission_rate=0.0003,      # 佣金万分之三
    stamp_duty_rate=0.001,       # 印花税千分之一
    slippage=0.001               # 滑点 0.1%
)
bt.run(benchmark='000300.SH')
```

> 💡 详细教程 👉 [qka.quantai.chat](https://qka.quantai.chat)

## 特性一览

| 特性 | 说明 |
|------|------|
| 🚀 **极简 API** | 统一的 `Data`/`Strategy`/`Backtest` 三件套，上手零门槛 |
| 📊 **A 股数据** | 基于 Akshare，覆盖全市场 A 股数据 |
| ⚡ **并发下载** | 多线程批量拉数据，几百只股票秒级完成 |
| 🔄 **高效回测** | 时间序列引擎，天然支持多股票横截面处理 |
| 📈 **HTML 报告** | 一键生成自包含的交互式回测报告，浏览器直接打开 |
| 📉 **基准对比** | 自动获取沪深300做基准，曲线叠加展示 |
| 💰 **成本模型** | 佣金/印花税/滑点全支持，贴近实盘 |
| 🔧 **模块化** | 核心、经纪商、MCP、Server 各模块可独立使用 |
| 📝 **文档完善** | [qka.quantai.chat](https://qka.quantai.chat) |

## 核心模块

### Data — 数据获取
多数据源、自动缓存、并发下载、统一格式。支持日线/分钟线，前复权/后复权。

### Strategy — 策略编写
事件驱动框架，在 `on_bar` 里写你的交易逻辑，`get()` 拿到当前截面数据做决策。

### Backtest — 回测引擎
时间序列驱动，支持多资产、成本模型、基准对比。`run()` 执行，`report()` 出报告，`summary()` 打印绩效指标。

### Brokers — 实盘交易（建设中）
集成 QMT 接口，客户端/服务器架构，支持远程交易。

## 文档站

完整文档、API 参考、最佳实践：

👉 **[qka.quantai.chat](https://qka.quantai.chat)**

## 许可证

[MIT](LICENSE)

## 致谢

- [Akshare](https://github.com/akfamily/akshare) — 免费 A 股数据源
- [Plotly](https://plotly.com/python/) — 交互式图表
- [FastAPI](https://fastapi.tiangolo.com/) — API 框架
- [xtquant](https://github.com/ShiMiaoYS/xtquant) — QMT Python 接口

---

> ⚠️ 量化交易存在风险，请充分了解风险后再使用本框架。作者不对任何投资损失负责。
