# 经纪商与交易

`Broker` 是你的虚拟券商。它管钱、管持仓、管交易费用。你不直接操作它——策略里的 `self.broker` 就是它的实例。

---

## 初始化

```python
from qka import Broker

self.broker = Broker(initial_cash=100_000)
```

默认费率（贴近 A 股实盘）：

| 费用 | 什么时候收 | 默认费率 | 最低收费 |
|------|-----------|----------|---------|
| 佣金 | 买入和卖出都收 | 万 2.5 | 5 元 |
| 印花税 | 卖出才收 | 万 5 | 无 |
| 滑点 | 买入和卖出都收 | 0.1% | 无 |

想自己调：

```python
self.broker = Broker(
    initial_cash=1_000_000,
    commission_rate=0.0001,      # 万 1
    stamp_duty_rate=0.0005,      # 万 5（A 股固定）
    slippage=0.0005,             # 0.05%
)
```

---

## 交易

```python
# 买入
self.broker.buy('000001.SZ', price, size)

# 卖出
self.broker.sell('000001.SZ', price, size)
```

买入时：
1. 算要花多少钱：`price × size + 佣金`
2. 检查现金够不够，不够就不买
3. 扣钱，加持仓记录

卖出时：
1. 检查有没有持仓、够不够卖
2. 到账：`price × size - 佣金 - 印花税 - 滑点`
3. 加钱，减持仓

---

## 持仓和资金

```python
# 还剩多少钱
self.broker.cash         # 比如 85000.0

# 持仓
self.broker.positions    # {'000001.SZ': {'size': 1000, 'cost_basis': 10.2}}
```

`positions` 里每只股票有两条信息：
- `size` — 持仓股数
- `cost_basis` — 平均买入成本（用于算盈亏，不影响回测结果）

---

## 完整的买入卖出流程

```python
def on_bar(self, date):
    close = self.get('close')
    if close is None or close.empty:
        return

    for sym in close.index:
        price = float(close[sym])
        if price <= 0:
            continue

        # 买入条件：没有持仓
        if sym not in self.broker.positions:
            size = self.sizing.percent(0.1, price)
            if size > 0:
                self.broker.buy(sym, price, size)
                print(f"买入 {sym} {size} 股，价格 {price}")
        
        # 卖出条件：有持仓，涨幅超过 20%
        elif sym in self.broker.positions:
            pos = self.broker.positions[sym]
            cost = pos['cost_basis']
            if price / cost - 1 > 0.2:
                self.broker.sell(sym, price, pos['size'])
                print(f"卖出 {sym} {pos['size']} 股")
```

---

## 特殊情况怎么处理

| 情况 | Broker 怎么做 |
|------|-------------|
| 现金不够买 | 不买，资金不足的消息记日志 |
| 持仓不够卖 | 不卖，持仓不足的消息记日志 |
| 价格不合法（≤0） | 不交易，记日志 |
| 卖出部分持仓 | 只减数量，持仓还在 |
| 全部卖出 | 从 `positions` 里移除该股票 |
