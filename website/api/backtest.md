# qka.Backtest

回测引擎核心调度器，串联 `Data` 与 `Strategy` 并驱动事件流。

```python
from qka import Backtest
```

---

## 构造函数

```python
Backtest(data: Data, strategy: Strategy)
```

- **`data`**：已配置好的 `qka.Data` 实例。
- **`strategy`**：用户自定义的 `qka.Strategy` 实例。

---

## 执行方法

### `run(cash=100000.0, start_date=None, end_date=None, benchmark=None)`

运行完整回测。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `cash` | `float` | `100000.0` | 初始资金（元） |
| `start_date` | `str` | `None` | 回测起始日期 `'YYYY-MM-DD'` |
| `end_date` | `str` | `None` | 回测结束日期 `'YYYY-MM-DD'` |
| `benchmark` | `str` | `None` | 基准指数代码，如 `'000300.SH'` |

```python
bt.run(cash=200000, start_date='2023-01-01', benchmark='000300.SH')
```

---

### `report(title: str = "未命名策略", output_path: str | None = None) -> str`

生成自包含的 HTML 可视化回测报告。

- **`title`** (`str`): 策略名称（展示在报告标题中）。
- **`output_path`** (`str | None`): 输出的 HTML 文件路径。若为 `None` 则默认保存在 `reports/` 目录下。
- **返回值** (`str`): 生成的 HTML 文件绝对路径。

```python
html_path = bt.report(title="双均线策略回测", output_path="reports/ma_report.html")
```

---

## 核心属性

### `metrics` (`dict`)
绩效度量指标字典，包含 13 项指标：
- `initial_cash` (`float`): 初始本金
- `final_equity` (`float`): 最终总资产
- `total_return_pct` (`float`): 总收益率（%）
- `annual_return_pct` (`float`): 年化收益率（%）
- `annual_volatility_pct` (`float`): 年化波动率（%）
- `sharpe_ratio` (`float`): 夏普比率（年化）
- `max_drawdown_pct` (`float`): 最大回撤（%）
- `calmar_ratio` (`float`): 卡玛比率
- `total_trades` (`int`): 总交易笔数
- `win_rate_pct` (`float`): 胜率（%）
- `profit_loss_ratio` (`float`): 盈亏比
- `total_commission` (`float`): 总手续费支出
- `n_days` (`int`): 回测实际交易天数

### `results` (`pd.DataFrame`)
每日收盘资产流水快照：
- `cash`: 可用现金
- `value`: 持仓市值
- `total`: 总权益
- `positions`: 当日持仓字典快照

### `trade_history` (`list[dict]`)
逐笔交易流水明细列表。
