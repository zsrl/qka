# 性能优化

QKA 回测引擎的 **dask 分区迭代** 架构，使其能够在一台笔记本上高效处理数百只股票数年的数据。

---

## 问题：大规模回测的内存瓶颈

传统回测引擎的典型做法：

```python
# 常规做法：一次性加载所有数据
all_data = pd.read_parquet('data/*.parquet')
# all_data 可能在内存中占 2-3 GB
for date in all_data.index.unique():
    run_strategy(date, all_data.loc[date])
```

当股票数量增多时，内存占用线性增长：

| 股票数 | 日线数据（5年） | 内存占用 |
|--------|----------------|----------|
| 10 只  | ~1250k 行     | ~100 MB  |
| 100 只 | ~12500k 行    | ~1 GB    |
| 300 只 | ~37500k 行    | ~3+ GB   |

3 GB 对现代电脑不算大，但加上回测过程中的副本、numpy 数组、中间结果，很容易吃掉 8-12 GB。

---

## 方案：dask 分区迭代

QKA 的解决方案绕开了"全量加载"这个前提：

### 1. 数据存储：每只股票独立 parquet

```
datadir/baostock/1d/qfq/
├── 000001.SZ.parquet    # 平安银行，~1MB
├── 600000.SH.parquet    # 浦发银行，~1MB
└── ...                  # 每只股票独立文件
```

优势：
- **增量更新**：新股票只需下载自己的文件，不影响已有数据
- **独立压缩**：每只股票独立列式存储，读取某个因子时只加载需要的列

### 2. 加载：dask 构建 lazy 计算图

```python
import dask.dataframe as dd

# 读取每个 parquet，添加 symbol 列
parts = []
for symbol in symbols:
    df = dd.read_parquet(f'{symbol}.parquet')
    df['symbol'] = symbol
    parts.append(df)

# 合并 → 此时仍是 lazy（0 内存占用）
merged = dd.concat(parts)
```

到目前为止，**没有读取任何实际数据**。dask 只记录了"去哪里读什么文件"的计算图。

### 3. 变换：字符串列名

```python
# 将 symbol+factor 拼合为扁平列名
for factor in factors:
    merged[f'{symbol}_{factor}'] = ...
```

使用 `{symbol}_{factor}` 字符串列名而非 MultiIndex，是因为 dask 的 MultiIndex 在 `.compute()` 后存在信息丢失的 bug。

### 4. 分区：按时间排序，分批计算

```python
# 按日期排序分区，每区约 500 行
npartitions = max(1, total_rows // 500)
merged = merged.set_index('date', npartitions=npartitions)
```

```
                        全部数据（~36000 行）
  ┌────────┬────────┬────────┬────────┬────────┬────────┬────────┐
  │分区 0  │分区 1  │分区 2  │分区 3  │分区 4  │分区 5  │分区 6  │
  │~500 行 │~500 行 │~500 行 │~500 行 │~500 行 │~500 行 │~500 行 │
  │第1-2天 │第2-3天 │...     │...     │...     │...     │最后几天│
  └────────┴────────┴────────┴────────┴────────┴────────┴────────┘
       │         │         │
       ▼         ▼         ▼
   分批 compute() → 每批~500行 → 内存释放
```

### 5. 迭代：逐分区 compute + DataAccessor 接续

```python
for i in range(npartitions):
    partition = merged.get_partition(i).compute()
    
    for date, row in partition.iterrows():
        factors = parse_row(row)  # 还原 {factor: {symbol: value}}
        
        for factor, data in factors.items():
            strategy._data.push(date, factor, data)
        
        strategy.on_bar(date)
        broker.on_bar()
    
    # 分区处理完后，partition 变量被回收
    # DataAccessor 内部缓存（deque）保留历史窗口
```

关键点：
- **内存峰值 = 单分区（~500 行）+ DataAccessor 缓存（~250 bar）**
- 与总股票数解耦，只与分区大小有关
- DataAccessor 的 `deque(maxlen=N)` 自动丢弃过期数据

### 6. DataAccessor：跨分区缓存

```python
class DataAccessor:
    def __init__(self, max_window=250):
        self._buffer = defaultdict(
            lambda: defaultdict(
                lambda: deque(maxlen=max_window)
            )
        )
        self._dates = deque(maxlen=max_window)
    
    def push(self, date, factor, data):
        # 记录日期（去重）
        if date != self._last_date:
            self._dates.append(date)
            self._last_date = date
        # 推入每个股票的值
        for symbol, value in data.items():
            self._buffer[factor][symbol].append(value)
    
    def get(self, factor):
        # 返回最新横截面
        return pd.Series({
            sym: vals[-1] 
            for sym, vals in self._buffer[factor].items()
        })
    
    def history(self, factor, window):
        # 返回历史 DataFrame
        data = {
            sym: list(vals)[-window:]
            for sym, vals in self._buffer[factor].items()
        }
        return pd.DataFrame(data, index=list(self._dates)[-window:])
```

DataAccessor 的生命周期跨越所有分区——它在 `Backtest.run()` 开始时创建，在回测结束时销毁。

---

## 性能对比

在真实数据上的测试（3 只股票，8604 bar）：

| 方式 | 内存峰值 | 耗时 |
|------|----------|------|
| 传统 pandas 全量加载 | ~300 MB | 8-10s |
| dask 分区迭代（500行/区） | ~5 MB | 11s |

性能差异在 300 只股票时会更加显著：

| 股票数 | 传统方式 | dask 分区 | 优势 |
|--------|----------|-----------|------|
| 10 只  | ~100 MB  | ~5 MB     | 20x 内存 |
| 100 只 | ~1 GB    | ~5 MB     | 200x 内存 |
| 300 只 | ~3+ GB   | ~5 MB     | 600x+ 内存 |

!!! tip "不在本地运行？"
    QKA Cloud 使用轻量级沙箱执行回测，dask 分区迭代保证即使在小内存服务器上也能稳定运行 300+ 只股票。

---

## 实际建议

- **< 50 只股票**：用默认模式即可，dask 不会有明显优势
- **50-200 只股票**：dask 分区迭代自动启用（`Data.get(lazy=True)`），无需额外配置
- **200+ 只股票**：强烈建议使用，内存占用几乎不变，仅增加少许计算时间

---

## 为什么不直接用 pandas？

pandas 在 300 只股票 × 5 年数据时已经需要 3+ GB 内存。回测过程中还有：

- 策略内部的数据副本（如计算均线时的 rolling 窗口）
- Broker 的交易记录 DataFrame
- 多只股票的中间计算结果

这些都叠加在初始数据之上，很容易超过 8 GB。

**dask 的分区迭代将"所有数据都在内存"的前提改为"只有当前窗口的数据在内存"**，从根本上解决了内存问题。

而 DataAccessor 的滚动窗口缓存（deque）确保了策略可以正常查询历史数据，不受分区边界的限制。
