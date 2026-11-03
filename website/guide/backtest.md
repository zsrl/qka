# 回测引擎 (Backtest)

`qka.Backtest` 是 QKA 框架的调度枢纽，负责将数据层（`Data`）与业务策略层（`Strategy`）紧密串联，注入基础设施，按时序推进交易日并计算多维度的投资绩效指标。

---

## 构造与初始化

```python
from qka import Backtest

bt = Backtest(data, strategy)
```

- **`data`**：已配置好的 `qka.Data` 实例。
- **`strategy`**：用户自定义的 `qka.Strategy` 策略实例。

::: tip 惰性绑定
在实例化 `Backtest(data, strategy)` 时，仅建立对象间的引用关系，不会触发数据下载，也不会执行任何交易循环。所有计算均在显式调用 `run()` 后开始。
:::

---

## 启动回测 (`run`)

```python
bt.run(
    cash=100000.0,
    start_date='2023-01-01',
    end_date='2024-12-31',
    benchmark='000300.SH'
)
```

### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `cash` | `float` | `100000.0` | 初始资金（元） |
| `start_date` | `str` | `None` | 回测起始日期 `'YYYY-MM-DD'`。若为 `None` 则从数据最早有效日期开始 |
| `end_date` | `str` | `None` | 回测结束日期 `'YYYY-MM-DD'`。若为 `None` 则至数据最新日期截止 |
| `benchmark` | `str` | `None` | 基准指数代码（如 `'000300.SH'` 沪深300、`'000905.SH'` 中证500），用于对比超额收益及回归 Alpha/Beta |

> **分块滑动优化**：对于超过 500 个交易日的长期历史回测，`Backtest` 底层会自动启动分块迭代机制，保证内存平稳，极速运行。

---

## 13 项核心绩效指标 (`bt.metrics`)

回测结束后，`bt.metrics` 会自动计算并缓存 13 项专业量化绩效指标字典：

| 指标键名 | 类型 | 说明与数学意义 |
|----------|------|----------------|
| `initial_cash` | `float` | 账户初始本金 |
| `final_equity` | `float` | 期末账户总资产（现金 + 持仓终值） |
| `total_return_pct` | `float` | **总收益率**（%） |
| `annual_return_pct` | `float` | **年化复合收益率**（%） |
| `annual_volatility_pct` | `float` | **年化波动率**（%，按 252 交易日换算） |
| `sharpe_ratio` | `float` | **夏普比率**（年化，默认无风险利率 3%） |
| `max_drawdown_pct` | `float` | **最大回撤**（%，正数，如 `15.2` 表示回撤 15.2%） |
| `calmar_ratio` | `float` | **卡玛比率**（年化收益率 / 最大回撤） |
| `total_trades` | `int` | 发生的总交易笔数 |
| `win_rate_pct` | `float` | **胜率**（%），盈利交易笔数 / 总平仓笔数 |
| `profit_loss_ratio` | `float` | **盈亏比**（平均单笔盈利 / 平均单笔亏损） |
| `total_commission` | `float` | 累计扣除的总手续费与印花税支出 |
| `n_days` | `int` | 回测覆盖的实际交易日总天数 |

```python
# 快速读取绩效
m = bt.metrics
print(f"年化: {m['annual_return_pct']:.2f}% | 夏普: {m['sharpe_ratio']:.2f} | 最大回撤: {m['max_drawdown_pct']:.2f}%")
```

---

## 逐日资产快照 (`bt.results`)

`bt.results` 是一个以交易日为索引的 `pd.DataFrame`，记录每日收盘后的账户核心状态：

| 列名 | 类型 | 说明 |
|------|------|------|
| `cash` | `float` | 当日收盘可用现金余额 |
| `value` | `float` | 当日收盘全部持仓总市值 |
| `total` | `float` | 当日收盘账户总资产（`cash + value`） |
| `positions` | `dict` | 当日持仓快照（含各标的股数、均价、最新市价、浮动盈亏等） |

```python
# 查看净值走势前 5 天
print(bt.results[['cash', 'value', 'total']].head())
```

---

## 逐笔成交流水 (`bt.trade_history`)

`bt.trade_history` 以列表字典的形式记录每一笔订单的完整执行链路：

```python
[
    {
        'action': 'buy',
        'symbol': '000001.SZ',
        'price': 9.50,              # 下单前价格
        'exec_price': 9.5095,       # 加上滑点后的实际撮合成交价
        'size': 1000,               # 股数
        'amount': 9509.5,           # 成交金额
        'commission': 5.0,          # 佣金（最低 5 元生效）
        'total_cost': 9514.5,       # 账户实际扣减资金
        'timestamp': Timestamp('2024-01-05')
    },
    ...
]
```
