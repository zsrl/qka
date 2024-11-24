# qka (快量化)

快捷量化助手（Quick Quantitative Assistant）是一个简洁易用，可实操A股的量化交易框架。

## 安装

```bash
pip install qka
```

```python
datas = qka.data(
  stock_list=[], 
  period='tick', 
  indicators=[
    'MA',
    'BOLL'
  ]
)


def strategy(bar, bars, borker):
  pass

res = qka.backtest(datas, start_time='', end_time='', strategy=strategy)

borker = qka.broker(type='qmt', config={})

qka.trade(datas, start_time='', strategy=strategy, borker=borker)

```