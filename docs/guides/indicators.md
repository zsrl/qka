# 指标

写策略的时候需要均线、RSI、MACD 这些技术指标。QKA 在数据加载时一次性算好，策略里直接拿。

---

## 一句话

```python
data = Data(
    symbols=['000001.SZ'],
    indicators={
        'sma_20': ('sma', 20),
        'rsi_14': ('rsi', 14),
    }
)
```

策略里直接用：

```python
def on_bar(self, date):
    sma = self.get('sma_20')
    rsi = self.get('rsi_14')
```

## 支持的指标

| 指标 | 写法 | 生成列 |
|------|------|--------|
| 简单均线 | `('sma', 20)` | `sma_20` |
| 指数均线 | `('ema', 14)` | `ema_14` |
| 加权均线 | `('wma', 30)` | `wma_30` |
| RSI | `('rsi', 14)` | `rsi_14` |
| ATR | `('atr', 14)` | `atr_14` |
| MACD | `('macd', 12, 26, 9)` | `macd`、`macd_signal`、`macd_histogram` |
| 布林带 | `('bbands', 20, 2)` | `bbands_upper`、`bbands_middle`、`bbands_lower` |

## 对指定字段算

```python
indicators={
    'sma_high_10': ('sma', 'high', 10),    # 对最高价算均线
}
```

## 自定义指标

写个函数，想怎么算都行：

```python
def add_ma5(df):
    df['ma5'] = df['close'].rolling(5).mean()
    return df

data = Data(symbols=['000001.SZ'], indicators=add_ma5)
```

函数接收每只股票的 DataFrame，返回加了新列的 DataFrame。和内置指标可以混着用：

```python
indicators={
    'sma_20': ('sma', 20),
    'ma5': add_ma5,
}
```

## 预计算 vs 动态计算

| 方式 | 算几次 | 策略里咋用 |
|------|--------|-----------|
| 预计算 | 加载时算 1 次 | `self.get('sma_20')` |
| 动态计算 | 每根 bar 算 1 次 | 每 bar 手动调 rolling |

股票越多、bar 越多，预计算优势越大。
