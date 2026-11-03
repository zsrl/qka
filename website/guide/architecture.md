# 架构设计

QKA 采用了 **声明式向量计算 + 事件驱动轻量回测** 的混合架构。既保留了向量化因子计算在处理大规模数据时的极速优势，又兼具事件驱动模型在模拟真实撮合、滑点扣费和动态仓位控制时的拟真度。

---

## 总体架构全景

```mermaid
flowchart TD
    subgraph 数据层["1. 数据层 (Data Layer)"]
        D1["行情源适配器<br/>(tickflow / baostock / tdx)"]
        D2["本地 Parquet 缓存<br/>(按复权口径自动落盘)"]
        D3["向量化因子预计算<br/>(ta 库指标 / 内置指标 / Lambda)"]
        D4["因子预热引擎 (warmup)"]
        D1 --> D2 --> D3 --> D4
    end

    subgraph 引擎层["2. 引擎调度层 (Backtest Engine)"]
        B1["Backtest 调度器"]
        B2["分块滑动迭代器 (500 bar chunking)"]
        B3["日线时序推进器 (date-by-date)"]
        B1 --> B2 --> B3
    end

    subgraph 基础设施["3. 基础设施注入 (Runtime Injection)"]
        I1["虚拟券商 (Broker)"]
        I2["仓位计算器 (Sizing)"]
        I3["数据访问切片 (DataAccessor)"]
    end

    subgraph 策略层["4. 策略决策层 (Strategy Layer)"]
        S1["on_bar(date)"]
        S2["横截面: self.get()"]
        S3["历史切片: self.history()"]
        S4["买卖决策与调仓"]
        S1 --> S2 & S3 --> S4
    end

    subgraph 撮合与核算["5. 拟真撮合核算 (Matching & Accounting)"]
        M1["A股整手约束 (100股整除)"]
        M2["费率结算 (佣金/印花税/滑点)"]
        M3["持仓与资金表 (Cash & Positions)"]
    end

    subgraph 分析与大屏["6. 绩效评估与报告 (Analysis & Report)"]
        R1["13 项核心绩效指标 (bt.metrics)"]
        R2["逐笔成交记录 (bt.trade_history)"]
        R3["交互式 HTML 诊断报告 (Plotly)"]
    end

    数据层 --> 引擎层
    引擎层 -.-> 基础设施
    基础设施 --> 策略层
    策略层 --> 撮合与核算
    撮合与核算 --> 引擎层
    引擎层 --> 分析与大屏
```

---

## 核心设计要点

### 1. 宽表组织与跨标的横截面
`Data.get()` 返回的是标准的长宽结构 `pd.DataFrame`：
- **行索引（Index）**：为交易日 `pd.Timestamp`。
- **列索引（Columns）**：采用 `{symbol}|{factor}` 的统一复合命名规则（例如 `000001.SZ|close`、`600000.SH|sma_20`）。
- **内置常驻列**：除开高低收成交额外，`Data` 始终自动计算 `{symbol}|returns`（日收益率），无需手动重复声明。

在策略执行阶段，`self.get('factor_name')` 会在 $O(1)$ 复杂度下切片出当天的横截面 `pd.Series`，以股票代码为索引，极大简化了多标的、全市场策略的编写。

### 2. 运行时无缝注入模式
与 Backtrader 等框架需要用户手动构造复杂的上下文环境不同，在 QKA 中，用户只需实现纯粹的策略逻辑：
```python
class MyStrategy(Strategy):
    def on_bar(self, date):
        # broker, sizing, _data 均由 Backtest 在执行时动态注入
        ...
```
这种设计将策略的**业务逻辑**与回测引擎的**运行状态**彻底解耦，便于针对策略进行单元测试，也利于大模型无差错生成代码。

### 3. 分块迭代与内存优化
当回测区间跨度极大（大于 500 个交易日）时，`Backtest` 内部会自动按 500 bar 的窗口进行分块滑动推进，避免一次性在内存中维护超大规模的临时对象，保证长期回测的稳定流畅。

### 4. 严格防范未来函数设计
- 策略在 `date` 当天通过 `self.get()` 只能获取截止到当天的因子值。
- 通过 `self.history(factor, N)` 只能获取 `[date - N + 1, date]` 区间内的历史滑动窗口。
- 绝无任何途径从 `Strategy` 内部提前探测未来数据，从架构根源上杜绝了量化研究中最致命的「未来函数陷阱」。
