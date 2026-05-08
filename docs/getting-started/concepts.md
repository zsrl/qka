# 核心概念

了解 QKA 的架构设计和核心抽象。

---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。

## 整体架构

```
qka/
├── core/               ← 核心模块
│   ├── data.py         # 数据获取与缓存
│   ├── backtest.py     # 回测引擎（含 dask 分区迭代）
│   ├── strategy.py     # 策略基类
│   ├── accessor.py     # 滚动窗口数据访问器（DataAccessor）
│   ├── broker.py       # 虚拟经纪商（交易执行 + 费用计算）
│   ├── sizing.py       # 仓位计算工具（SizingAccessor）
│   └── report.py       # HTML 报告生成
├── brokers/            # QMT 实盘对接
├── mcp/                # MCP 服务
├── server/             # Web 服务
├── utils/              # 工具模块
└── cli.py              # 命令行
```

---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。

## 核心流程

```
Data ──> Backtest.run() ──> dask 分区迭代 ──> Strategy.on_bar(date) ──> Broker.buy/sell()
                    │                                          │              ▲
                    v                                          ▼              │
               summary() / report()           SizingAccessor (self.sizing) ───┘
                                              DataAccessor (self.get / self.history)
```

**流程说明：**

1. **`Data`** 从 baostock 下载并缓存数据（每只股票独立 parquet）
2. **`Backtest`** 用 dask 合并为 lazy DataFrame，按时间分区分批计算
3. 每个分区 compute() 后，逐 bar 调用 `strategy.on_bar(date)`
4. **`Strategy.on_bar(date)`** 用 `self.get('close')` / `self.history('close', 20)` 获取数据
5. **`SizingAccessor`** 根据可用资金计算买入股数，传入 `self.broker.buy()`
6. **`Broker.buy/sell()`** 执行交易，自动扣费（佣金 + 印花税 + 滑点）
7. 回测结束后，**`summary()`** 和 **`report()`** 输出结果

---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。

## 核心抽象

### `DataAccessor` — 滚动窗口数据访问器

DataAccessor 是策略访问数据的中枢。它在回测过程中维护一个滚动窗口缓存，支持三种查询方式：

```
                        push(date, 'close', {symbol: value})
                                   │
                                   ▼
           ┌─────────────────────────────────────┐
           │      DataAccessor 内部缓存            │
           │                                      │
           │   close: {                            │
           │     '000001.SZ': deque(maxlen=750),   │
           │     '600000.SH': deque(maxlen=750),   │
           │     ...                               │
           │   }                                   │
           │   volume: { ... }                     │
           │   sma_20: { ... }      ← 预计算指标   │
           │   rsi_14: { ... }                     │
           └─────────────────────────────────────┘
              │        │              
              ▼        ▼              
        self.get()  self.history()
        (横截面)    (时间序列)
```

#### `self.get(factor)` — 横截面数据

#### `self.get(factor)` — 横截面数据

返回**当前 bar** 所有股票的某个因子值：

```python
close = self.get('close')
# pd.Series:
# 000001.SZ    10.50
# 600000.SH     8.32
# 000002.SZ    15.68
```

#### `self.history(factor, window)` — 历史序列

返回过去 N 个交易日的历史数据：

```python
hist = self.history('close', 20)
# pd.DataFrame，行=日期，列=股票代码：
#              000001.SZ  600000.SH  000002.SZ
# 2024-01-02      10.2       8.12      15.21
# 2024-01-03      10.5       8.32      15.68
# ...              ...        ...        ...
```

### 预计算指标/因子（Data 层面）

`Data` 的 `indicators` 参数统一处理**技术指标**和**自定义因子**，在数据加载时一次性预计算。
策略中直接通过 `self.get()` 和 `self.history()` 查询，无需每 bar 动态计算。

#### 格式 1：声明式字典（TA 指标 + 自定义 callable）

```python
data = Data(
    symbols=['000001.SZ', '600000.SH'],
    indicators={
        # TA 指标（tuple 写法）
        'sma_20': ('sma', 20),         # 20 日均线
        'ema_14': ('ema', 14),         # 14 日指数均线
        'rsi_14': ('rsi', 14),         # 14 日 RSI
        'macd': ('macd', 12, 26, 9),   # MACD（生成 3 列）
        'bbands': ('bbands', 20, 2),   # 布林带（生成 3 列）

        # 自定义因子（callable，可混搭）
        'ma5': lambda df: df['close'].rolling(5).mean(),
        'ratio': lambda df: df['close'] / df['open'],
    }
)
```

指标在数据加载时一次性预计算，每只股票会增加对应的列：

```
合并后列名格式：{symbol}_{指标名}
例如：000001.SZ_sma_20, 000001.SZ_macd, 000001.SZ_macd_signal
```

#### 格式 2：函数（替代旧版 `factor` 参数）

```python
def add_ma5(df):
    df['ma5'] = df['close'].rolling(5).mean()
    return df

data = Data(symbols=['000001.SZ'], indicators=add_ma5)
# 等价于旧版 Data(..., factor=add_ma5)
```

#### 在策略中使用

```python
def on_bar(self, date):
    # 直接取横截面（不用每 bar 现算）
    sma_20 = self.get('sma_20')
    price = self.get('close')
    
    # 历史数据同样支持
    macd_hist = self.history('macd', 10)
    bb_upper_hist = self.history('bbands_upper', 5)
```

#### 支持的指标

| 指标名 | 参数 | 生成列 | 备注 |
|---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。--|---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。|---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。--|---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。|
| `sma` | `(length)` | `sma_20` | 简单移动平均 |
| `ema` | `(length)` | `ema_14` | 指数移动平均 |
| `wma` | `(length)` | `wma_30` | 加权移动平均 |
| `rsi` | `(length)` | `rsi_14` | 相对强弱指数 |
| `macd` | `(fast, slow, signal)` | `macd`, `macd_signal`, `macd_histogram` | 指数平滑异同 |
| `bbands` | `(length, std)` | `bbands_upper`, `bbands_middle`, `bbands_lower` | 布林带 |
| `atr` | `(length)` | `atr_14` | 平均真实波幅 |

可指定自定义因子列：`('sma', 'high', 20)` 表示对 `high` 列计算 SMA。

#### 对比：预计算 vs 动态计算

| 方式 | 性能 | 策略代码简洁度 | 历史数据支持 |
|---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。|---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。|---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。|---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。-|
| **预计算（推荐）** | 一次算好，各 bar 复用 | `self.get('sma_20')` | ✅ `self.history('sma_20', 20)` |
| 动态计算（旧方式） | 每 bar 重复算 | `self.ta.sma('close', length=20)` | ❌ 需额外逻辑 |

---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。

### `Broker` — 虚拟经纪商

管理资金、持仓和交易，自动处理：

| 费用 | 方向 | 默认费率 | 最低收费 |
|---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。|---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。|---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。-|---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。-|
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

---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。

### `Backtest` 三件套

| 方法 | 功能 |
|---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。|---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。|
| `run(benchmark=None)` | 执行回测，可选基准对比 |
| `summary()` | 打印绩效指标，返回 dict |
| `report(title='', output_path=None)` | 生成自包含 HTML 报告 |

---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。

## 数据存储模型

每只股票的数据独立存储为 parquet 文件：

```
datadir/
└── baostock/
    └── 1d/
        └── qfq/
            ├── 000001.SZ.parquet
            ├── 600000.SH.parquet
            └── ...
```

回测时，dask 将所有 parquet 合并为 lazy DataFrame。列名格式为 `{symbol}_{factor}`：

| 列名 | 含义 |
|---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。|---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。|
| `000001.SZ_close` | 平安银行收盘价 |
| `000001.SZ_volume` | 平安银行成交量 |
| `600000.SH_close` | 浦发银行收盘价 |

---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。

## 性能原理

QKA 的回测引擎使用 **dask 分区迭代** 处理大规模数据：

- **每只股票独立存储** → 增量下载天然支持
- **dask 合并** → 仅保存计算图，不加载到内存
- **按时间分区** → 每个分区约 500 bar，逐批 compute()
- **DataAccessor 跨分区** → deque 缓存延续历史数据

这种设计让 QKA 可以高效处理数百只股票数年数据，同时保持单机运行。详见 [性能优化](../advanced/performance.md)。

---

### `SizingAccessor` — 仓位计算工具

`SizingAccessor` 挂载在 `strategy.sizing` 下，根据可用资金和价格计算买入股数。
所有结果自动按手（100股）向下取整，不足一手返回 0。

```
              ┌─────────────────────┐
              │  Broker             │
              │  ───────────        │
              │  cash: ¥100,000     │
              │  positions: {...}   │
              └────────┬────────────┘
                       │ reads cash
                       ▼
┌─────────────────────────────────┐
│        SizingAccessor           │
│                                 │
│  percent(0.1, ¥10) → 1000 股   │
│  atr_risk(0.02, ¥10, 0.5) → 2000 股
│  kelly(0.6, 2.0, ¥10) → 4000 股
└─────────────────────────────────┘
```

#### 使用场景示例

```python
def on_bar(self, date):
    price = float(self.get('close')['000001.SZ'])
    if price <= 0:
        return

    # 硬性风控：每笔亏损不超过总资金 2%
    atr = float(self.get('atr_14')['000001.SZ'])
    size = self.sizing.atr_risk(0.02, price, atr)
    if size > 0:
        self.broker.buy('000001.SZ', price, size)
```

#### 方法总览

| 方法 | 适用场景 | 公式 | 返回值 |
|------|---------|------|--------|
| `fixed_shares(n)` | 固定股数定投 | 直接取整 | `int` |
| `fixed_amount(amount, price)` | 每月固定金额投入 | `amount / price` | `int` |
| `percent(ratio, price)` | 按资金比例分配仓位 | `cash × ratio / price` | `int` |
| `atr_risk(risk_ratio, price, atr, multiplier=2)` | 基于波动率的动态仓位 | `cash × risk / (atr × mult)` | `int` |
| `kelly(win_rate, wl_ratio, price)` | 已知胜率赔率的最优下注 | 凯利公式 `(p×b-q)/b` | `int` |

#### 方法详解

**`percent(ratio, price)`** — 最常用。用可用现金的 `ratio` 比例买入：

```python
# 半仓买入 000001.SZ
size = self.sizing.percent(0.5, float(self.get('close')['000001.SZ']))
```

**`atr_risk(risk_ratio, price, atr, multiplier=2)`** — 波动率自适应仓位。
ATR 越大，单股风险越高，买入股数自动减少：

```python
# 每笔亏损 ≤ 2% 总资金，止损位 2 倍 ATR
atr = float(self.get('atr_14')['000001.SZ'])
size = self.sizing.atr_risk(0.02, price, atr)
# ATR=0.5 → size=2000；ATR=1.0 → size=1000（波动翻倍，仓位减半）
```

**`kelly(win_rate, win_loss_ratio, price)`** — 已知历史胜率和赔率时的最优仓位。
当 f* ≤ 0 时返回 0（不下注）：

```python
# 胜率 60%，平均盈利/亏损 = 2
size = self.sizing.kelly(0.6, 2.0, price)
# f* = (0.6*2 - 0.4)/2 = 0.4 → 40% 仓位
```

> **注意：** 所有方法基于 `broker.cash`（可用现金）计算，不含持仓市值。
> 如需基于总资产计算，先手动合并持仓市值。

## 设计原则

1. **开箱即用** — 三行代码跑回测，不折腾环境
2. **真实成本** — 佣金、印花税、滑点默认开启，回测结果贴近实盘
3. **结果可见** — `bt.report()` 生成自包含 HTML，手机 PC 都能看
4. **专注 A 股** — 费率、交易规则、基准对比都针对 A 股市场
