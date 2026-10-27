---
layout: home

hero:
  name: "QKA — 快量化"
  text: "Quant Kit for A-shares"
  tagline: "简洁易用的 A 股量化回测框架，集成多源行情、指标预计算、虚拟撮合与交互式报告"
  image:
    src: /logo.svg
    alt: QKA Logo
  actions:
    - theme: brand
      text: 快速上手
      link: /guide/quick-start
    - theme: alt
      text: 核心功能
      link: /guide/intro
    - theme: alt
      text: API 参考
      link: /api/
    - theme: alt
      text: 🤖 AI Agent 技能
      link: /guide/agent-skill

features:
  - icon: ⚡
    title: 极简优雅的 API
    details: 面向对象的直观设计，几行代码搞定数据加载、指标计算、策略买卖与绩效评估，告别繁重框架样板代码。
  - icon: 🔄
    title: 多源行情与智能缓存
    details: 内置 tickflow（含 ETF / 可转债）、baostock（含估值指标）、tdx（通达信客户端）三源自由切换，自动落盘秒级读取。
  - icon: 📐
    title: 全量技术指标与因子
    details: 深度整合 ta 库百余种趋势、动量、波动率指标，支持内置 Jensen α/β、夏普比率及自定义 Lambda 因子预计算。
  - icon: 🧪
    title: 模拟标的 (Simulate)
    details: 现场合成单边上涨、单边下跌、均值回归或随机震荡走势，无需等待真实行情即可验证策略交易逻辑的正确性。
  - icon: 💼
    title: 拟真 A 股撮合与仓位
    details: 严格遵守 100 股整手、佣金/印花税/滑点扣除；内置资金比例、固定金额、固定股数与 ATR 风险 4 种仓位算法。
  - icon: 📊
    title: 交互式 HTML 回测大屏
    details: 一键输出自包含的 Plotly 交互报告，包含净值走势、基准对比、动态回撤区、月度收益热力图与逐笔交易流水。
  - icon: 🛡️
    title: 因子预热与防未来函数
    details: 独创 warmup 暖机机制，让回测第 1 根 bar 即拥有有效因子；严密隔离当前横截面与历史窗口，规避未来函数。
  - icon: 🤖
    title: AI Agent 智能体支持
    details: 原生适配 Claude Code、Cursor、Windsurf，通过 npx skills add 注入标准 API，大模型零误差编写合规量化代码。
---

<div class="vp-doc" style="margin-top: 3.5rem;">

<div style="text-align: center; margin-bottom: 2.5rem;">
  <h2 style="font-size: 2rem; font-weight: 800; border-top: none; margin-bottom: 0.5rem;">⚡ 30 秒极速体验</h2>
  <p style="color: var(--vp-c-text-2); font-size: 1.05rem; max-width: 720px; margin: 0 auto;">
    从数据加载、指标预计算到策略买卖与绩效评估，完整策略代码一目了然。
  </p>
</div>

::: code-group

```python [双均线策略 (MaCross.py)]
from qka import Data, Strategy, Backtest

# 1. 声明行情数据与指标预计算
data = Data(
    symbols=['000001.SZ'],
    factors={
        'sma_5':  ('ta.trend.sma_indicator', 'close', 5),
        'sma_20': ('ta.trend.sma_indicator', 'close', 20),
    },
)

# 2. 编写交易策略
class MaCross(Strategy):
    def __init__(self):
        super().__init__()
        self.pct = 0.2  # 每次调仓动用 20% 资金

    def on_bar(self, date):
        close = self.get('close')
        fast = self.get('sma_5')
        slow = self.get('sma_20')

        for sym in close.index:
            price = float(close[sym])
            if price <= 0:
                continue
            # 金叉买入
            if fast[sym] > slow[sym]:
                size = self.sizing.percent(self.pct, price)
                if size > 0:
                    self.broker.buy(sym, price, size)
            # 死叉平仓
            else:
                pos = self.broker.positions.get(sym, {}).get('size', 0)
                if pos > 0:
                    self.broker.sell(sym, price, pos)

# 3. 运行回测与评估
strategy = MaCross()
bt = Backtest(data, strategy)
bt.run(cash=200000, start_date='2024-01-01', benchmark='000300.SH')

print(f"总收益率: {bt.metrics['total_return_pct']:.2%}")
print(f"夏普比率: {bt.metrics['sharpe_ratio']:.2f}")
print(f"最大回撤: {bt.metrics['max_drawdown_pct']:.2%}")
```

```bash [安装与启动]
# 1. 安装 QKA 库
pip install qka

# 2. 为 Claude Code / Cursor 安装 AI 技能
npx skills add zsrl/qka

# 3. 在 Python 脚本或 Jupyter Notebook 中直接运行
python MaCross.py
```

:::

<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; margin-top: 2.5rem;">
  <div style="padding: 1.5rem; border-radius: 8px; background-color: var(--vp-c-bg-soft); border: 1px solid var(--vp-c-divider);">
    <h3 style="font-size: 1.15rem; margin-top: 0; color: var(--vp-c-brand-1);">📦 多源覆盖 & 自动落盘</h3>
    <p style="color: var(--vp-c-text-2); font-size: 0.92rem; line-height: 1.6;">
      支持 tickflow（股票/ETF/转债）、baostock（市盈率/市净率/换手率）及通达信本机行情，按复权隔离自动缓存，无缝极速读取。
    </p>
  </div>

  <div style="padding: 1.5rem; border-radius: 8px; background-color: var(--vp-c-bg-soft); border: 1px solid var(--vp-c-divider);">
    <h3 style="font-size: 1.15rem; margin-top: 0; color: var(--vp-c-brand-1);">🎯 拟真撮合 & 严格规则</h3>
    <p style="color: var(--vp-c-text-2); font-size: 0.92rem; line-height: 1.6;">
      全自动规整 A 股 100 股整手，内置千分之一滑点、万 2.5 佣金（5元起）与万 5 印花税，真实呈现交易损耗。
    </p>
  </div>

  <div style="padding: 1.5rem; border-radius: 8px; background-color: var(--vp-c-bg-soft); border: 1px solid var(--vp-c-divider);">
    <h3 style="font-size: 1.15rem; margin-top: 0; color: var(--vp-c-brand-1);">🤖 AI Agent 原生驱动</h3>
    <p style="color: var(--vp-c-text-2); font-size: 0.92rem; line-height: 1.6;">
      针对大语言模型编码特性深度优化，自带标准化 SKILL 规范，让 AI 助手能够精准理解 API 约束并编写高水准策略。
    </p>
  </div>
</div>

</div>
