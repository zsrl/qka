# qka.Strategy

策略抽象基类。所有量化交易策略都必须继承此类。

```python
from qka import Strategy
```

---

## 策略定义规范

```python
class MyStrategy(Strategy):
    def __init__(self):
        super().__init__()
        # 在此绑定自定义超参数
        self.lookback = 20

    def on_bar(self, date):
        # 逐日推进的核心交易决策
        ...
```

- **`__init__`**：子类必须调用 `super().__init__()`，无参数。
- **`on_bar(self, date)`**：抽象方法，必须实现。参数 `date` 为当前交易日的 `pd.Timestamp`。

---

## 运行时注入属性

在 `Backtest.run()` 启动后，引擎会自动将以下实例注入到策略对象中：

| 属性 | 类型 | 说明 |
|------|------|------|
| `self.broker` | `qka.core.broker.Broker` | 虚拟券商，用于执行买卖下单和查询资金/持仓 |
| `self.sizing` | `qka.core.sizing.SizingAccessor` | 仓位管理计算器，提供多种按手取整的算仓方法 |
| `self._data` | `qka.core.accessor.DataAccessor` | 内部数据访问器，供 `self.get()` 与 `self.history()` 切片 |

---

## 成员方法

### `get(factor: str) -> pd.Series`

获取**当前交易日**所有标的的指定因子横截面数据。

- **`factor`** (`str`)：因子或字段名称，如 `'close'`、`'volume'`、`'sma_20'`。
- **返回值**：`pd.Series`，以股票代码为索引，当前因子值为数据值。

```python
close_prices = self.get('close')
print(close_prices['000001.SZ'])
```

---

### `history(factor: str, window: int = 20) -> pd.DataFrame`

获取截止至**当前交易日**的前 `window` 个交易日历史滑动窗口。

- **`factor`** (`str`)：因子名称。
- **`window`** (`int`, 默认 `20`)：回看窗口期天数。
- **返回值**：`pd.DataFrame`，行索引为日期升序排列，列索引为标的代码。

```python
hist_close = self.history('close', window=30)
# 计算过去 30 日最高价
max_30 = hist_close.max()
```
