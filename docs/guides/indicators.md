# 指标

策略中经常需要均线、RSI、MACD 等技术指标。QKA 在数据加载时一次性预计算完毕，策略中直接读取。

---

## 基本用法

```python
data = Data(
    symbols=['000001.SZ'],
    indicators={
        'sma_20': ('sma', 20),
        'rsi_14': ('rsi', 14),
    }
)
```

策略中直接调用：

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

## 指定计算字段

默认以收盘价（close）计算。如需对其他字段计算：

```python
indicators={
    'sma_high_10': ('sma', 'high', 10),    # 对最高价计算均线
}
```

## 自定义指标

通过函数实现任意自定义计算逻辑：

```python
def add_ma5(df):
    """每只股票单独计算 5 日均线"""
    df['ma5'] = df['close'].rolling(5).mean()
    return df

data = Data(symbols=['000001.SZ'], indicators=add_ma5)
```

函数接收每只股票的 DataFrame，返回添加新列后的 DataFrame。可与内置指标混用：

```python
indicators={
    'sma_20': ('sma', 20),
    'ma5': add_ma5,
}
```

## 预计算与动态计算对比

| 方式 | 计算次数 | 策略中的用法 |
|------|---------|-------------|
| 预计算 | 加载时计算 1 次 | `self.get('sma_20')` |
| 动态计算 | 每根 bar 计算 1 次 | 每 bar 手动调用 rolling |

股票数量越多、回测周期越长，预计算的性能优势越明显。
