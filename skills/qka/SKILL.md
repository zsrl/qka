---
name: qka
description: 使用 QKA（快量化）框架生成 A 股量化回测策略、选股和技术指标代码。当需要基于 qka.Data、qka.Strategy、qka.Backtest、qka.Broker 等 API 编写量化代码时使用此技能。
---

# QKA 框架

简洁易用的 A 股量化回测框架，共六个公开类：

| 类 | 全限定名 | 作用 |
|-----|------|------|
| Data | `qka.Data` | 行情数据加载 + 指标预计算 |
| Strategy | `qka.Strategy` | 策略基类 — 实现 `on_bar` 做交易决策 |
| Broker | `qka.Broker` | 虚拟券商 — 执行买卖，管理资金和持仓 |
| SizingAccessor | `qka.SizingAccessor` | 仓位计算 — 四种仓位方法 |
| Backtest | `qka.Backtest` | 回测引擎 — 串联 Data 和 Strategy，注入基础设施 |
| Analysis | `qka.Analysis` | 分析模块 — 常用的分析方法 |

## 参考文档

详细 API 文档按模块拆分在 `references/` 目录下，按需查阅对应文件：

| 模块 | 文件 | 内容 |
|------|------|------|
| Data | `references/data.md` | 数据加载、指标预计算（ta 库全部指标 + qka 内置指标）、`get()` |
| Strategy | `references/strategy.md` | 策略基类、`on_bar`、`self.get()`、`self.history()` |
| Backtest | `references/backtest.md` | `run()`、`bt.metrics`、`bt.results`、`bt.trade_history` |
| Broker | `references/broker.md` | `buy()`、`sell()` |
| SizingAccessor | `references/sizing.md` | 四种仓位方法 |
| Analysis | `references/analysis.md` | `zigzag()`、`alpha_beta()`、`sharpe_ratio()`、`max_drawdown()`、`information_ratio()` |

## 使用指南

- 编写**回测策略**：读 `references/strategy.md` + `references/backtest.md`，必要时读 `references/data.md`
- 编写**选股 / 数据加载**：读 `references/data.md`
- 使用**买卖 / 仓位**：读 `references/broker.md` + `references/sizing.md`
- 使用**事后分析**：读 `references/analysis.md`
