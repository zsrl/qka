# 虚拟券商 (Broker)

`qka.Broker` 是回测过程中的交易中枢，负责模拟真实 A 股券商的交易执行、资金结算、持仓维护与各项税费扣减。

---

## 运作机制与注入

在回测运行时，`Backtest` 会自动实例化 `Broker` 并注入到策略对象的 `self.broker` 属性中，策略开发者**无需手动创建**该对象。

```python
def on_bar(self, date):
    # 查询当前可用资金
    available_cash = self.broker.cash

    # 查询当前持仓字典
    positions = self.broker.positions
```

---

## A 股交易费率模型

为了真实反映实盘交易中的摩擦损耗，QKA 默认内置了高度贴合 A 股实际的费率模型：

| 费用项 | 默认费率 | 规则与扣费方式 |
|--------|----------|----------------|
| **佣金 (Commission)** | 万分之 2.5 (`0.00025`) | 双向收取（买入与卖出均扣除），**最低 5 元起**（`MIN_COMMISSION = 5.0`） |
| **印花税 (Stamp Duty)** | 万分之 5 (`0.0005`) | **单向收取（仅卖出时扣除）**，买入免税 |
| **滑点 (Slippage)** | 0.1% (`0.001`) | 买入时成交价上浮 `price * (1 + 0.001)`，卖出时成交价下浮 `price * (1 - 0.001)` |

---

## 核心交易接口

### 1. `buy(symbol, price, size) -> bool`

买入指定股票。

- **`symbol`**：标的代码（如 `'000001.SZ'`）。
- **`price`**：基准委托价格。
- **`size`**：买入股数，**必须为 100 的整数倍（一手）**。
- **返回值**：布尔值 `True`（买入成功）或 `False`（买入失败）。

```python
# 买入平安银行 200 股
success = self.broker.buy('000001.SZ', price=9.50, size=200)
if not success:
    print("买入失败，可能原因：资金不足、价格非法或股数不合法")
```

::: warning 自动防御机制
- **负价格防御**：若历史数据因前复权导致早期价格 $\le 0$，`buy()` 会自动拦截并返回 `False`，避免产生荒谬的负成本买入。
- **费用预留**：`buy()` 会精确计算 `实际成交价 × 股数 + 佣金`，若 `self.cash < total_cost` 则拒单并提示资金不足。
:::

---

### 2. `sell(symbol, price, size) -> bool`

卖出指定股票。

- **`symbol`**：标的代码。
- **`price`**：基准委托价格。
- **`size`**：卖出股数，**必须为 100 的整数倍**。
- **返回值**：布尔值 `True`（卖出成功）或 `False`（卖出失败）。

```python
# 平掉所有持仓
pos = self.broker.positions.get('000001.SZ', {}).get('size', 0)
if pos > 0:
    self.broker.sell('000001.SZ', price=10.20, size=pos)
```

- 扣除佣金（最低 5 元）与印花税（万 5）。
- 净回款 `net_proceeds = 成交额 - 佣金 - 印花税` 立即退回到 `self.broker.cash`。

---

## 持仓与状态查询

### `self.broker.positions`
当前所有标的的持仓字典：
```python
{
    '000001.SZ': {
        'size': 1000,        # 持仓股数
        'avg_price': 9.45    # 平均持仓成本价（已含买入滑点与摊销佣金）
    }
}
```

### `self.broker.trades`
逐日权益流水记录 `pd.DataFrame`：
- `cash`：每日收盘可用现金。
- `value`：持仓总市值。
- `total`：总权益（现金 + 持仓市值）。
- `positions`：每日持仓明细快照。
- `trades`：交易流水明细。
