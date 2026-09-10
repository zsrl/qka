## Backtest

回测引擎，串联 Data 和 Strategy。在执行时注入 broker/sizing/data。

### 构造

```python
from qka import Backtest

bt = Backtest(data, strategy)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `data` | `Data` | 数据对象 |
| `strategy` | `Strategy` | 策略对象 |

构造时不执行任何操作，只绑定引用。

### run()

`run(cash=100000.0, start_date=None, end_date=None, benchmark=None, warmup=0)`

执行回测。注入 broker/sizing/data 后遍历每个交易日，调用 `strategy.on_bar(date)`。

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `cash` | `100000.0` | 初始资金 |
| `start_date` | `None` | 回测起始日期 `'YYYY-MM-DD'` |
| `end_date` | `None` | 回测截止日期 |
| `benchmark` | `None` | 基准指数代码，baostock 格式如 `'sh.000300'` |
| `warmup` | `0` | 指标预热天数。自动多读 `warmup` 天历史计算指标，使策略第 1 个 bar 起指标即有效（无需手写 warmup guard）。on_bar 调用次数不变；显式传入（>0）时覆盖 Data 的 warmup 设定 |

> 500 bar 以上自动分块迭代，避免一次性加载全量数据。

```python
bt.run(cash=200000, start_date='2024-01-01')
```

执行后可通过 `bt.results` 和 `bt.trade_history` 获取结果，详见下方。

### bt.metrics

`dict`，绩效指标，`run()` 结束时计算并缓存。

| 字段 | 类型 | 说明 |
|------|------|------|
| `initial_cash` | `float` | 初始资金 |
| `final_equity` | `float` | 最终资产 |
| `total_return_pct` | `float` | 总收益率（%） |
| `annual_return_pct` | `float` | 年化收益率（%） |
| `annual_volatility_pct` | `float` | 年化波动率（%） |
| `sharpe_ratio` | `float` | 夏普比率（无风险利率 3%） |
| `max_drawdown_pct` | `float` | 最大回撤（%） |
| `calmar_ratio` | `float` | Calmar 比率 |
| `total_trades` | `int` | 交易总次数 |
| `win_rate_pct` | `float` | 胜率（%） |
| `profit_loss_ratio` | `float` | 盈亏比 |
| `total_commission` | `float` | 总手续费 |
| `n_days` | `int` | 回测天数 |

```python
bt.run()
print(bt.metrics['total_return_pct'])   # 15.3
print(bt.metrics['sharpe_ratio'])        # 1.25
```

### bt.results

`pd.DataFrame`，索引为日期。每行是当日收盘后的快照。

| 列 | 类型 | 说明 |
|------|------|------|
| `cash` | `float` | 可用现金 |
| `value` | `float` | 持仓总市值 |
| `total` | `float` | 总资产（cash + value） |
| `positions` | `dict` | 各持仓明细，`{symbol: {size, avg_price, current_price, market_value, profit_pct}}` |
| `trades` | `list[dict]` | 截止当日的全部交易记录 |

```python
bt.results.index        # DatetimeIndex
bt.results['total']     # 每日总资产序列
bt.results['cash']      # 每日现金序列
bt.results.iloc[-1]     # 最终状态
```

### bt.trade_history

`list[dict]`，逐笔交易明细，按成交顺序排列。

买入时含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | `str` | `'buy'` |
| `symbol` | `str` | 股票代码 |
| `price` | `float` | 下单价格（成交前） |
| `exec_price` | `float` | 实际成交价（滑点后） |
| `size` | `int` | 成交股数 |
| `amount` | `float` | 成交金额（exec_price × size） |
| `commission` | `float` | 佣金 |
| `total_cost` | `float` | 总支出（amount + commission） |
| `timestamp` | | 交易日 |

卖出时含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `action` | `str` | `'sell'` |
| `symbol` | `str` | 股票代码 |
| `price` | `float` | 下单价格 |
| `exec_price` | `float` | 实际成交价（滑点后） |
| `size` | `int` | 成交股数 |
| `amount` | `float` | 成交金额 |
| `commission` | `float` | 佣金 |
| `stamp_duty` | `float` | 印花税 |
| `net_proceeds` | `float` | 净收入（amount - commission - stamp_duty） |
| `timestamp` | | 交易日 |

### 完整示例

```python
from qka import Data, Strategy, Backtest

data = Data(
    symbols=['sz.000001'],
    indicators={
        'sma_5':  ('ta.trend.sma_indicator', 'close', 5),
        'sma_20': ('ta.trend.sma_indicator', 'close', 20),
    },
)

class MaCross(Strategy):
    def __init__(self):
        super().__init__()
        self.pct = 0.2

    def on_bar(self, date):
        close = self.get('close')
        fast = self.get('sma_5')
        slow = self.get('sma_20')
        for sym in close.index:
            price = float(close[sym])
            if fast[sym] > slow[sym]:
                size = self.sizing.percent(self.pct, price)
                if size > 0:
                    self.broker.buy(sym, price, size)
            else:
                pos = self.broker.positions.get(sym, {}).get('size', 0)
                if pos > 0:
                    self.broker.sell(sym, price, pos)

bt = Backtest(data, MaCross())
bt.run(cash=200000, start_date='2024-01-01')
print(bt.metrics['total_return_pct'])
```
