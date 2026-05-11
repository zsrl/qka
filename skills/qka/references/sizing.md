# Sizing 模块

仓位计算工具。在策略中通过 `self.sizing` 访问。

## 方法

### self.sizing.percent(ratio, price) -> int

按可用资金的百分比计算买入股数，自动向下取整到 100 的倍数。

```python
# 用 10%（10000 元）资金买入
price = float(self.get('close')['000001.SZ'])
size = self.sizing.percent(0.1, price)
self.broker.buy('000001.SZ', price, size)
```

- `ratio`: 资金比例，如 `0.1` = 10%, `0.5` = 50%
- `price`: 当前价格
- 返回：股数（int），已按手取整
- 如果计算出的股数 < 100，返回 0

### self.sizing.fixed_shares(n) -> int

买入固定股数。

```python
size = self.sizing.fixed_shares(1000)     # 买入 1000 股
self.broker.buy('000001.SZ', price, size)
```

### self.sizing.fixed_amount(amount, price) -> int

买入固定金额。

```python
size = self.sizing.fixed_amount(5000, price)  # 投入 5000 元
self.broker.buy('000001.SZ', price, size)
```

## 注意事项

```python
# ✅ 正确：先算仓位再买入
price = float(self.get('close')['000001.SZ'])
size = self.sizing.percent(0.1, price)
if size >= 100:
    self.broker.buy(sym, price, size)

# ❌ 错误：不校验 size 直接买
self.broker.buy(sym, price, self.sizing.percent(0.1, price))
# 如果 percent 返回 0，buy 会报错
```
