# 回测引擎

写好了策略，准备数据，怎么跑？这就是 `Backtest` 的事。

---

## 一句话

```python
from qka import Backtest

bt = Backtest(data, MyStrategy())
bt.run(benchmark='000300.SH')
bt.report()
```

三步：建好、跑、看结果。

---

## 参数说明

`Backtest` 就两个参数，没什么好记的：

```python
bt = Backtest(
    data,                          # Data 实例，里面装了股票数据
    MyStrategy(cash=100_000),      # 策略实例（可以传 cash 等参数）
)
```

---

## 跑回测

```python
bt.run(benchmark='000300.SH')   # 带沪深 300 对比
```

`run` 做的事：

1. 把数据按时间排序
2. 一天一天调你的 `on_bar(date)`
3. 记录每天的资产变化
4. 下载基准数据（如果传了 benchmark）

几百只股票跑 5 年？QKA 默认是分批算的，不会一次把所有数据塞到内存里，不用担心内存爆炸。

---

## 看结果

### `summary()` — 终端概览

```python
bt.summary()
```

输出：

```
QKA 回测报告 — MyStrategy
────────────────────────────────────────
初始资金:        ¥100,000.00
最终资产:        ¥178,233.45
总收益率:        +78.23%
年化收益率:      +11.34%
最大回撤:        -32.15%
夏普比率:        0.68
交易次数:        47
胜率:            61.70%
────────────────────────────────────────
```

### `report()` — HTML 报告

```python
bt.report(title='我的策略', output_path='./my_report.html')
```

浏览器自动打开。包含：

- 绩效指标卡片
- 净值曲线（带基准对比）
- 月度收益热力图
- 交易明细列表
- 全部在一个 HTML 文件里，手机上也能看

不传 `output_path` 的话，默认存到 `./reports/` 目录。

---

## 加基准

A 股最常用的是沪深 300：

```python
bt.run(benchmark='000300.SH')
```

加了之后，summary 和 report 里会多出超额收益、超额夏普这些指标。

---

## 小提示

**报告文件是用 Plotly 生成的，纯前端渲染。** 不用开服务器，双击 HTML 文件就能看。

**不要太在意单次回测的胜率。** 交易次数少了胜率 100% 也是蒙的，交易次数多了胜率低也可能是好策略。
