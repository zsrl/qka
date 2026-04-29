# 核心概念

了解 QKA 的架构设计和核心抽象。

---

## 整体架构

```
qka/
├── core/               ← 核心模块
│   ├── data.py         # 数据获取与缓存
│   ├── backtest.py     # 回测引擎
│   ├── strategy.py     # 策略基类
│   ├── broker.py       # 虚拟经纪商（交易执行 + 费用计算）
│   └── report.py       # HTML 报告生成
├── brokers/            # QMT 实盘对接
├── mcp/                # MCP 服务
├── server/             # Web 服务
├── utils/              # 工具模块
└── cli.py              # 命令行
```

---

## 核心流程

```
Data ──> Strategy.on_bar(date, get) ──> Broker.buy/sell() ──> Backtest.run()
                                                                    │
                                                                    v
                                                              summary()
                                                              report()
```

**流程说明：**

1. **`Data`** 从 akshare 下载数据并缓存，返回多只股票的 DataFrame
2. **`Backtest`** 按日期遍历数据，每天调用策略的 `on_bar`
3. **`Strategy.on_bar(date, get)`** 用 `get('close')` 获取当日行情，决定买卖
4. **`Broker.buy/sell()`** 执行交易，自动扣费（佣金 + 印花税 + 滑点）
5. **`Backtest`** 记录每天的资金、持仓状态
6. 回测结束后，**`summary()`** 和 **`report()`** 输出结果

---

## 关键抽象

### `get(factor)` — 获取因子数据

这是 `on_bar` 中最重要的接口。它在**每个 bar** 被调用，返回**当前时间点**所有股票的某个因子值：

```python
def on_bar(self, date, get):
    close = get('close')       # pd.Series, index=股票代码
    ma5  = get('ma5')          # 自定义因子，同上格式
    # 返回值示例：
    # 000001.SZ    10.50
    # 600000.SH     8.32
    # 000002.SZ    15.68
```

!!! note "不是历史序列"
    `get('close')` 返回的是**当天所有股票的收盘价**，不是某只股票的历史价格。
    要算均线等需要历史的指标，需要在策略中用列表自己累积。

### `Broker` — 虚拟经纪商

管理资金、持仓和交易，自动处理：

| 费用 | 方向 | 默认费率 | 最低收费 |
|------|------|----------|----------|
| 佣金 | 双向 | 万2.5 | 5 元 |
| 印花税 | 卖出 | 万5 | 无 |
| 滑点 | 双向 | 0.1% | 无 |

可在 `Broker` 初始化时自定义：

```python
self.broker = Broker(
    initial_cash=1_000_000,
    commission_rate=0.0001,      # 万1
    stamp_duty_rate=0.0005,      # 万5（A股固定）
    slippage=0.0005,             # 0.05%
)
```

### `Backtest` 三件套

| 方法 | 功能 |
|------|------|
| `run(benchmark=None)` | 执行回测，可选基准对比 |
| `summary()` | 打印绩效指标，返回 dict |
| `report(title='', output_path=None)` | 生成 HTML 报告 |

---

## 数据模型

每只股票的数据存储为 `{symbol}_{field}` 格式的列：

| 列名 | 含义 |
|------|------|
| `000001.SZ_close` | 平安银行收盘价 |
| `000001.SZ_volume` | 平安银行成交量 |
| `600000.SH_close` | 浦发银行收盘价 |

自定义因子通过 `.map_partitions()` 挂载后，`get()` 同样可以获取。

---

## 设计原则

1. **开箱即用** — 三行代码跑回测，不折腾环境
2. **真实成本** — 佣金、印花税、滑点默认开启，回测结果贴近实盘
3. **结果可见** — `bt.report()` 生成自包含 HTML，手机 PC 都能看
4. **专注 A 股** — 费率、交易规则、基准对比都针对 A 股市场
