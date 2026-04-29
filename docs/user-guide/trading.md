# 实盘交易

!!! warning "开发中"
    实盘交易模块（`qka/brokers/`）目前仍在开发中，以下内容为计划中的接口设计，
    尚未完全可用。

---

## 架构

QKA 的实盘交易基于 **QMT（迅投极速交易）** 实现：

```
策略 → 回测引擎 (模拟交易)    ← 开发/验证阶段
策略 → QMT 客户端 → QMT 终端  ← 实盘阶段
```

## 计划中的接口

### QMT 客户端

```python
from qka.brokers.client import QMTClient

client = QMTClient(
    account_id='你的资金账号',
    qmt_path='C:/QMT/bin'  # QMT 安装路径
)
```

### 交易操作

```python
# 买入
client.buy('000001.SZ', price=10.5, size=1000)

# 卖出
client.sell('000001.SZ', price=11.0, size=500)

# 查询持仓
positions = client.positions()

# 查询委托
orders = client.orders()
```

---

## 相关资源

- [QMT 官方文档](http://dict.thinktrader.net/)
- `qka/brokers/` 模块源码
