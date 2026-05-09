# 交易

`Broker` 是你的虚拟券商。它管钱、管持仓、管交易费用。策略里的 `self.broker` 就是它的实例。

---

## 初始化

```python
self.broker = Broker(initial_cash=100_000)
```

默认费率（贴近 A 股实盘）：

| 费用 | 什么时候收 | 默认费率 | 最低收费 |
|------|-----------|----------|---------|
| 佣金 | 买卖都收 | 万 2.5 | 5 元 |
| 印花税 | 卖出收 | 万 5 | 无 |
| 滑点 | 买卖都收 | 0.1% | 无 |

自己调费率：

```python
self.broker = Broker(
    initial_cash=1_000_000,
    commission_rate=0.0001,      # 万 1
    slippage=0.0005,             # 0.05%
)
```

## 买卖

```python
self.broker.buy('000001.SZ', price, size)
self.broker.sell('000001.SZ', price, size)
```

买入时扣钱加持仓，卖出时加钱减持仓。费用自动算。

## 持仓和资金

```python
self.broker.cash           # 还剩多少钱（¥85,000）
self.broker.positions      # {'000001.SZ': {'size': 1000, 'cost_basis': 10.2}}
```

`positions` 里每只股票有股数（size）和平均买入成本（cost_basis）。

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

        # 没有持仓 → 买入
        if sym not in self.broker.positions:
            size = self.sizing.percent(0.1, price)
            if size > 0:
                self.broker.buy(sym, price, size)

        # 涨幅超过 20% → 卖出
        else:
            pos = self.broker.positions[sym]
            cost = pos['cost_basis']
            if price / cost - 1 > 0.2:
                self.broker.sell(sym, price, pos['size'])
```

## 特殊情况

| 情况 | Broker 怎么做 |
|------|-------------|
| 现金不够买 | 不买，记日志 |
| 持仓不够卖 | 不卖，记日志 |
| 价格 ≤ 0 | 不交易，记日志 |
| 卖出部分 | 减持仓数量 |
| 全部卖出 | 从 positions 移除该股票 |
