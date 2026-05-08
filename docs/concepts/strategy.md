# 策略开发

策略是回测的核心。写一个策略就是写一个类，继承 `Strategy`，实现 `on_bar` 方法。

---

## 策略长什么样

```python
from qka import Strategy, Broker

class MyStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.broker = Broker(initial_cash=100_000)

    def on_bar(self, date):
        close = self.get('close')
        if close is None or close.empty:
            return
        # 你的交易逻辑写在这
```

---

## 理解生命周期

回测是按"天"跑的。每一天，QKA 会：

1. 把当天的数据准备好
2. 调用你的 `on_bar(date)`，告诉你今天是哪一天
3. 等你的逻辑跑完，进入下一天

所以 `on_bar` 里做的事情是：**根据今天的数据，决定要不要交易**。

---

## 取数据：两种方法

### `self.get(factor)` — 今天的数据

返回今天所有股票某个字段的数值。

```python
close = self.get('close')
# 结果长这样：
# 000001.SZ    10.50
# 600000.SH     8.32
# dtype: float64

# 取某只股票
price = float(close['000001.SZ'])

# 遍历所有股票
for sym in close.index:
    price = float(close[sym])
    # 你的交易逻辑
```

### `self.history(factor, window)` — 过去 N 天的数据

返回过去 N 天的历史，行是日期，列是股票。

```python
hist = self.history('close', 20)
# 结果长这样：
#              000001.SZ  600000.SH
# 2024-01-02      10.2       8.12
# 2024-01-03      10.5       8.32
# ...              ...        ...

# 算某只股票过去 20 天的均值
avg = hist['000001.SZ'].mean()
```

### 能取哪些字段

`self.get()` 和 `self.history()` 能取的东西取决于你 `Data` 里有什么。

**基础字段（自动有的）：**
- `open` / `high` / `low` / `close` / `volume`

**指标字段（需要你在 Data 里声明）：**
- 在 `indicators` 里声明的，比如 `sma_20`、`rsi_14`
- 详见 [预计算指标](indicators.md)

```python
# 有了 indicators，就能取
rsi = self.get('rsi_14')
sma_hist = self.history('sma_20', 10)
```

---

## 交易：两种操作

```python
# 买入
self.broker.buy('000001.SZ', price, size)

# 卖出
self.broker.sell('000001.SZ', price, size)
```

- `symbol` — 股票代码
- `price` — 成交价
- `size` — 股数（QKA 自动帮你在买入时按 100 股取整）

---

## 仓位管理

写死 100 股太粗糙。`self.sizing` 帮你算该买多少：

```python
# 可用资金的 10%
size = self.sizing.percent(0.1, price)

# 每次固定 1 万块
size = self.sizing.fixed_amount(10000, price)

# 按波动率风险控制
atr = float(self.get('atr_14')[sym])
size = self.sizing.atr_risk(0.02, price, atr)
```

详见 [仓位管理](sizing.md)。

---

## 状态管理

策略需要记住一些事情，比如"已经买过了"、"入场价格是多少"。直接在 `__init__` 里定义变量就行：

```python
class MyStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.broker = Broker(initial_cash=100_000)
        self.bought = False            # 自己的状态
        self.entry_prices = {}          # 入场价记录

    def on_bar(self, date):
        # 可以用 self.bought、self.entry_prices 来记东西
        pass
```

回测框架每根 bar 调 `on_bar`，但你的自定义变量在整个回测过程中都有效。

---

## 多股票怎么处理

数据有多只股票时，`self.get('close')` 返回的是所有股票的横截面，遍历处理就行：

```python
def on_bar(self, date):
    close = self.get('close')
    if close is None or close.empty:
        return

    for sym in close.index:
        price = float(close[sym])
        if price <= 0:
            continue

        if sym not in self.broker.positions:
            size = self.sizing.percent(0.1, price)
            if size > 0:
                self.broker.buy(sym, price, size)
```

---

## 不要做的事

| 不要做 | 为什么 |
|--------|--------|
| `on_bar` 里下载数据 | 每根 bar 都下载，回测会慢到怀疑人生 |
| `on_bar` 里 print | 几千根 bar 会刷屏到崩溃，用 `logger.debug` |
| 访问回测引擎内部 | `Strategy` 只跟 `broker` 和 `sizing` 打交道，其他别碰 |
