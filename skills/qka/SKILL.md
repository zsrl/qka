---
name: qka
description: >
  QKA 框架使用技能。当用户需要基于 QKA 框架编写 A 股量化策略、运行回测、
  处理股票数据、生成报告时使用。涵盖 QKA 全部核心 API 的使用方法。
---

# QKA 框架技能

## 概述

QKA 是一个 A 股量化交易回测框架。核心流程：

```
Data(symbols) → Strategy(策略类) → Backtest(回测) → Report(报告)
                  ↑
          indicators(预计算指标)
```

**类名约束：** 自定义策略类必须命名为 `MyStrategy`，继承 `Strategy`

## 能力边界

**能做的策略类型：**
- 趋势跟踪（双均线、海龟突破、MACD）
- 均值回归（RSI、Bollinger Bands）
- 多因子选股（PE/ROE/动量/波动率打分选股，周期 rebalance）
- 等权/市值加权组合
- 定投（固定间隔买入固定金额）
- 大盘 MA 择时、股债轮动

**做不了的：**
- 分钟级/高频（无分钟数据）
- 期权、期货
- 机器学习选股（无特征工程管道）
- 实盘交易
- 事件驱动（无财报/公告订阅）
- 多周期策略（仅单周期）

## A 股交易规则

1. 买入股数必须是 100 的整数倍（一手）
2. 价格必须 > 0 且不是 NaN
3. 资金不足时不买入
4. `sizing.percent()` 和 `sizing.fixed()` 已自动按手取整

## 模块索引

| 模块 | 文件 | 用途 |
|---|---|---|
| **Data** | references/data.md | 数据获取、缓存、预计算指标 |
| **Strategy** | references/strategy.md | 策略编写、on_bar、get/history |
| **Broker** | references/broker.md | 交易模拟、费用计算 |
| **Sizing** | references/sizing.md | 仓位计算 |
| **Backtest** | references/backtest.md | 回测引擎、benchmark |
| **Report** | references/report.md | 回测报告生成 |

按需查阅对应文件，每个文件包含精确的 API 签名、用法示例和常见错误。
