# 交易

`Broker` 是虚拟券商，负责资金管理、持仓记录和交易费用计算。策略中通过 `self.broker` 访问。

---

## 初始化

```python
self.broker = Broker(initial_cash=100_000)
```

默认费率（贴近 A 股实盘）：

| 费用 | 收取方向 | 默认费率 | 最低收费 |
|------|---------|----------|---------|
| 佣金 | 买卖双向 | 万 2.5 | 5 元 |
| 印花税 | 卖出 | 万 5 | 无 |
| 滑点 | 买卖双向 | 0.1% | 无 |

自定义费率：

```python
self.broker = Broker(
    initial_cash=1_000_000,
    commission_rate=0.0001,      # 万 1
    slippage=0.0005,             # 0.05%
)
```

## 买卖操作

```python
self.broker.buy('000001.SZ', price, size)
self.broker.sell('000001.SZ', price, size)
```

买入时扣除资金并增加持仓，卖出时释放资金并减少持仓。交易费用自动计算。

## 持仓与资金

```python
self.broker.cash           # 当前可用资金（¥85,000）
self.broker.positions      # {'000001.SZ': {'size': 1000, 'avg_price': 10.2}}
```

`positions` 中每只股票包含：
- `size` — 持仓股数
- `avg_price` — 平均买入成本

## 完整的买卖流程

```python
def on_bar(self, date):
    close = self.get('close')
    if close is None or close.empty:
        return

    for sym in close.index:
        price = float(close[sym])
        if price <= 0:
            continue

        # 无持仓则买入
        if sym not in self.broker.positions:
            size = self.sizing.percent(0.1, price)
            if size > 0:
                self.broker.buy(sym, price, size)

        # 涨幅超过 20% 则卖出
        else:
            pos = self.broker.positions[sym]
            cost = pos['avg_price']
            if price / cost - 1 > 0.2:
                self.broker.sell(sym, price, pos['size'])
```

## 特殊情况处理

| 情况 | Broker 行为 |
|------|------------|
| 现金不足 | 不执行买入，记录日志 |
| 持仓不足 | 不执行卖出，记录日志 |
| 价格 ≤ 0 | 不交易，记录日志 |
| 部分卖出 | 减少对应持仓数量 |
| 全部卖出 | 从 positions 中移除该股票 |
