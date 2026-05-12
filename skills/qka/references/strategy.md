<!-- AUTO: API 签名 -->

### Strategy

### `Strategy(**cash** `float` = 100000.0)`

    初始化策略

### `Strategy.get(**factor** `str`) → `pd.Series，index=股票代码，values=最新值``

    获取当前 bar 的横截面数据。 替代旧的 on_bar(date, get) 中的 get 参数。 仅当 on_bar 通过 self._data 注入数据后才能使用。

### `Strategy.history(**factor** `str`, **window** `int` = 20) → `pd.DataFrame，行=日期，列=股票代码``

    获取因子的历史窗口数据。

### `Strategy.on_bar(**date**)`

    每个 bar 的处理逻辑，必须由子类实现。 使用 self.get(factor) / self.history(factor, window) 获取数据。 --- 用法 --- class MyStrategy(Strategy): def on_bar(self, date): # 横截面数据（当前 bar 所有股票） close = self.get('close') # 历史序列（过去 N...

### DataAccessor

### `DataAccessor(**max_window** `int` = 250)`
### `DataAccessor.push(**date**, **factor** `str`, **data** `dict`)`

    推入一个因子在某天的横截面数据。

### `DataAccessor.get(**factor** `str`) → `pd.Series``

    获取当前 bar 的横截面数据。

### `DataAccessor.history(**factor** `str`, **window** `int` = 20) → `pd.DataFrame``

    获取因子的历史窗口数据。

### `DataAccessor.clear()`

    清空所有缓存（分区切换时使用）

<!-- /AUTO -->

# Strategy 模块

策略编写核心。

## 策略类结构

```python
from qka import Strategy

class MyStrategy(Strategy):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 初始化自定义状态（可选）
        # 不写 __init__ 也行，用父类默认值

    def on_bar(self, date):
        """每个交易日回调一次"""
        # date: pd.Timestamp
        # self.get() / self.history() 获取数据
        # self.broker 交易
        # self.sizing 计算仓位
        pass
```

**规则：**
- 类名必须是 `MyStrategy`
- `__init__` 必须用 `**kwargs` 透传，不能固定参数
- ❌ 禁止写 `on_bar(self, date, get)`——没有 `get` 参数

## self.get(factor) -> pd.Series

当前 bar 所有股票的横截面数据。

```python
close = self.get('close')           # 所有股票的收盘价
volume = self.get('volume')         # 成交量
high = self.get('high')             # 最高价

for sym in close.index:             # 遍历股票
    price = float(close[sym])
    if price > 0:
        ...
```

- `factor`: 因子名，如 `'close'`, `'open'`, `'high'`, `'low'`, `'volume'`
- 也可以取预计算指标：`self.get('sma_5')`, `self.get('rsi_14')`
- 返回 `pd.Series`, index=股票代码
- 如果某股票当前值缺失，会从 Series 中排除

```python
# ✅ 正确用法
close = self.get('close')
for sym in close.index:
    ...

# ❌ 错误用法
self.get('close', count=20)  # 没有 count 参数
get('close')                  # get 不是全局函数
```

## self.history(factor, window) -> pd.DataFrame

因子的历史窗口数据。

```python
hist = self.history('close', 20)        # 过去 20 天收盘价
ma5 = hist.iloc[-5:].mean()             # 最近 5 天均值，Series(index=股票代码)
today_close = hist.iloc[-1]             # 今天收盘价
yesterday_close = hist.iloc[-2]         # 昨天收盘价
series = hist[sym].dropna()             # 某只股票的历史序列
```

- 返回 `pd.DataFrame`, 行=日期（倒序）, 列=股票代码
- 如果 `history` 的数据不够 `window` 天，前几行会有 NaN
- **用 `.dropna()` 清理后再计算**
- `hist.iloc[-N:]` 取最近 N 天

## self.broker

交易接口。详见 broker.md。

```python
self.broker.buy('000001.SZ', price, 100)    # 买入 100 股
self.broker.sell('000001.SZ', price, 100)   # 卖出 100 股
```

## self.sizing

仓位计算。详见 sizing.md。

```python
# 10% 资金买入，自动按手取整
size = self.sizing.percent(0.1, price)
self.broker.buy(sym, price, size)
```
