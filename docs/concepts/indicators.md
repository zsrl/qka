# 预计算指标

写策略的时候经常要用到均线、RSI、MACD 这些技术指标。

QKA 的做法是：**在数据加载的时候一次性算好，策略里直接拿。**

---

## 一句话用法

```python
data = Data(
    symbols=['000001.SZ'],
    indicators={
        'sma_20': ('sma', 20),       # 20 日均线
        'rsi_14': ('rsi', 14),        # 14 日 RSI
    }
)
```

然后在策略里：

```python
def on_bar(self, date):
    sma = self.get('sma_20')      # 直接用
    rsi = self.get('rsi_14')      # 直接用
```

不用在每个 `on_bar` 里算，数据加载时就算完了。

---

## 支持的指标

| 指标名 | 写法示例 | 生成了哪些列 |
|--------|---------|-------------|
| 简单均线 | `('sma', 20)` | `sma_20` |
| 指数均线 | `('ema', 14)` | `ema_14` |
| 加权均线 | `('wma', 30)` | `wma_30` |
| RSI | `('rsi', 14)` | `rsi_14` |
| ATR | `('atr', 14)` | `atr_14` |
| MACD | `('macd', 12, 26, 9)` | `macd`、`macd_signal`、`macd_histogram` |
| 布林带 | `('bbands', 20, 2)` | `bbands_upper`、`bbands_middle`、`bbands_lower` |

---

## 高阶用法

### 对指定字段算指标

默认都用收盘价（close）算。想用别的字段也行：

```python
indicators={
    'sma_high_10': ('sma', 'high', 10),    # 对最高价算均线
    'atr_14': ('atr', 14),                  # ATR 默认用 high/low/close
}
```

### 自定义指标

写个函数，想怎么算都行：

```python
def add_ma5(df):
    """每只股票单独算 5 日均线"""
    df['ma5'] = df['close'].rolling(5).mean()
    return df

data = Data(symbols=['000001.SZ'], indicators=add_ma5)
```

函数接收每只股票单独的 DataFrame，返回加了新列的 DataFrame。列名就是你在策略里用的名字。

### 混着写

自定义函数和内置指标可以混用：

```python
indicators={
    'sma_20': ('sma', 20),
    'rsi_14': ('rsi', 14),
    'ma5': add_ma5,           # 这里传函数引用也行
}
```

---

## 指标多了影响性能吗

**预计算是一次性的。** 数据加载时算完，策略里是直接读。跟策略里每根 bar 现算相比：

| 方式 | 算多少次 | 策略里咋用 |
|------|---------|-----------|
| 预计算（推荐） | 加载时算 1 次 | `self.get('sma_20')` |
| 动态计算 | 每根 bar 算 1 次 | 每 bar 手动调 rolling |

股票越多、bar 越多，预计算的优势越大。跑几百只股票 5 年数据，动态算一遍 RSI 的开销能差几百倍。
