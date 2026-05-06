"""
QKA 回测报告生成器

生成自包含的 HTML 回测报告，包含：
- 绩效指标卡片
- 净值曲线 + 基准对比
- 回撤曲线
- 月度收益率热力图
- 交易明细表
- 回撤分析
"""

import json
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from plotly.utils import PlotlyJSONEncoder


def _calc_daily_returns(totals: pd.Series) -> pd.Series:
    """计算日收益率序列"""
    return totals.pct_change().dropna()


def _calc_drawdown_series(daily_returns: pd.Series) -> pd.Series:
    """计算回撤序列"""
    cumulative = (1 + daily_returns).cumprod()
    running_max = cumulative.cummax()
    return (cumulative - running_max) / running_max


def _find_drawdown_periods(daily_returns: pd.Series, top_n: int = 5) -> list:
    """
    找出前 N 大回撤区间

    Returns:
        list of dict: [{'start', 'end', 'depth', 'duration'}, ...]
    """
    dd = _calc_drawdown_series(daily_returns)

    periods = []
    in_drawdown = False
    start_idx = None
    min_val = None

    for i, val in enumerate(dd):
        if val < -0.0001 and not in_drawdown:
            in_drawdown = True
            start_idx = i
            min_val = val
        elif val < -0.0001 and in_drawdown:
            if val < min_val:
                min_val = val
        elif val >= -0.0001 and in_drawdown:
            periods.append({
                'start': daily_returns.index[start_idx],
                'end': daily_returns.index[i],
                'depth': min_val * 100,
                'duration': i - start_idx,
            })
            in_drawdown = False
            min_val = None

    # 未结束的回撤
    if in_drawdown:
        periods.append({
            'start': daily_returns.index[start_idx],
            'end': daily_returns.index[-1],
            'depth': min_val * 100,
            'duration': len(daily_returns) - start_idx,
        })

    periods.sort(key=lambda p: p['depth'])
    return periods[:top_n]


def _calc_monthly_returns(daily_returns: pd.Series) -> pd.DataFrame:
    """计算月度收益率矩阵（年×月）"""
    monthly = daily_returns.groupby([daily_returns.index.year, daily_returns.index.month]).apply(
        lambda x: (1 + x).prod() - 1
    )
    # 转成年×月的 DataFrame
    years = sorted(set(p[0] for p in monthly.index))
    out = pd.DataFrame(index=years, columns=range(1, 13), dtype=float)
    for (y, m), val in monthly.items():
        out.loc[y, m] = val * 100
    return out


def _make_equity_chart(results: pd.DataFrame, initial_cash: float,
                       benchmark_data: Optional[pd.Series] = None) -> str:
    """生成净值曲线图（含基准），返回 Plotly JSON"""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3],
    )

    # 净值曲线
    fig.add_trace(go.Scatter(
        x=results.index, y=results['total'],
        mode='lines', name='策略净值',
        line=dict(color='#2E86AB', width=2.5),
        hovertemplate='%{x}<br>策略: ¥%{y:,.2f}<extra></extra>',
    ), row=1, col=1)

    # 基准
    if benchmark_data is not None:
        bm = benchmark_data.reindex(results.index, method='ffill')
        if not bm.empty:
            bm_norm = bm / bm.iloc[0] * initial_cash
            fig.add_trace(go.Scatter(
                x=bm_norm.index, y=bm_norm.values,
                mode='lines', name='基准 (沪深300)',
                line=dict(color='#E07A5F', width=2, dash='dash'),
                hovertemplate='%{x}<br>基准: ¥%{y:,.2f}<extra></extra>',
            ), row=1, col=1)

    # 回撤曲线
    daily_ret = _calc_daily_returns(results['total'])
    dd = _calc_drawdown_series(daily_ret) * 100

    fig.add_trace(go.Scatter(
        x=dd.index, y=dd.values,
        mode='lines', name='回撤',
        fill='tozeroy',
        line=dict(color='#E74C3C', width=1),
        hovertemplate='%{x}<br>回撤: %{y:.2f}%<extra></extra>',
    ), row=2, col=1)

    fig.update_layout(
        title=dict(text='净值曲线与回撤', x=0.5, font=dict(size=16)),
        height=500, margin=dict(l=50, r=30, t=50, b=30),
        showlegend=True, template='plotly_white',
        hovermode='x unified',
    )
    fig.update_yaxes(title_text='总资产 (¥)', row=1, col=1)
    fig.update_yaxes(title_text='回撤 (%)', row=2, col=1, tickformat='.1f')
    fig.update_xaxes(title_text='日期', row=2, col=1)

    return json.dumps(fig.to_dict(), cls=PlotlyJSONEncoder)


def _make_monthly_heatmap(daily_returns: pd.Series) -> str:
    """生成月度收益率热力图，返回 Plotly JSON"""
    monthly = _calc_monthly_returns(daily_returns)
    if monthly.empty:
        return ''

    years = monthly.index.tolist()
    months = list(range(1, 13))
    month_labels = ['1月','2月','3月','4月','5月','6月',
                    '7月','8月','9月','10月','11月','12月']

    z = []
    for y in years:
        row = []
        for m in months:
            val = monthly.loc[y, m]
            row.append(val if not pd.isna(val) else None)
        z.append(row)

    # 颜色区间：-10% ~ +10%
    max_abs = max(abs(v) for row in z for v in row if v is not None) if any(
        v is not None for row in z for v in row) else 5
    zmax = max(max_abs, 5)

    fig = go.Figure(data=go.Heatmap(
        z=z, x=month_labels, y=[str(y) for y in years],
        colorscale=[[0, '#c0392b'], [0.5, '#ecf0f1'], [1, '#27ae60']],
        zmid=0, zmin=-zmax, zmax=zmax,
        text=[[f'{v:+.2f}%' if v is not None else '' for v in row] for row in z],
        texttemplate='%{text}',
        textfont=dict(size=11),
        hovertemplate='%{y} %{x}<br>%{text}<extra></extra>',
    ))

    fig.update_layout(
        title=dict(text='月度收益率', x=0.5, font=dict(size=14)),
        height=180 + len(years) * 30,
        margin=dict(l=50, r=30, t=40, b=20),
        xaxis=dict(side='bottom'),
        yaxis=dict(autorange='reversed'),
    )

    return json.dumps(fig.to_dict(), cls=PlotlyJSONEncoder)


def _build_html(metrics: dict, equity_chart_json: str,
                monthly_chart_json: str, trades_table_rows: str,
                drawdown_rows: str, strategy_name: str) -> str:
    """构建完整的 HTML 报告"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    # ---- 预计算条件渲染区块 ----
    monthly_chart_div = ''
    monthly_chart_js = ''
    if monthly_chart_json:
        monthly_chart_div = (
            '<div class="chart-box">\n'
            '    <div id="monthlyChart"></div>\n'
            '  </div>')
        monthly_chart_js = (
            '\nvar monthlyData = ' + monthly_chart_json + ';\n'
            "Plotly.newPlot('monthlyChart', monthlyData.data, monthlyData.layout, {responsive: true});")

    drawdown_section = ''
    if drawdown_rows:
        drawdown_section = (
            '<div class="chart-box">\n'
            '    <h2>\u56de\u64a4\u5206\u6790</h2>\n'
            '    <div class="table-wrap">\n'
            '      <table>\n'
            '        <thead><tr>\n'
            '          <th>#</th><th>\u5f00\u59cb</th><th>\u7ed3\u675f</th>\n'
            '          <th>\u56de\u64a4\u5e45\u5ea6</th><th>\u6301\u7eed\u5929\u6570</th>\n'
            '        </tr></thead>\n'
            '        <tbody>\n'
            + drawdown_rows +
            '\n        </tbody>\n'
            '      </table>\n'
            '    </div>\n'
            '  </div>')

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>QKA \u56de\u6d4b\u62a5\u544a - {strategy_name}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f0f2f5; color: #333;
}}
.container {{ max-width: 1100px; margin: 0 auto; padding: 20px; }}

/* ---- Header ---- */
.header {{
  background: linear-gradient(135deg, #2E86AB, #1a5276); color: white;
  padding: 28px 30px; border-radius: 12px; margin-bottom: 24px;
}}
.header h1 {{ font-size: 24px; margin-bottom: 6px; }}
.header p {{ opacity: 0.85; font-size: 14px; }}

/* ---- Cards ---- */
.cards {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}}
.card {{
  background: white; border-radius: 10px; padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}}
.card-label {{ font-size: 12px; color: #888; margin-bottom: 4px; }}
.card-value {{ font-size: 22px; font-weight: 700; }}
.card-value.positive {{ color: #27ae60; }}
.card-value.negative {{ color: #e74c3c; }}

/* ---- Chart boxes ---- */
.chart-box {{
  background: white; border-radius: 10px; padding: 16px; margin-bottom: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow: hidden;
}}
.chart-box h2 {{ font-size: 16px; margin-bottom: 12px; color: #555; }}

/* ---- Tables ---- */
.table-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{
  background: #2E86AB; color: white; padding: 10px 12px; text-align: left;
  font-weight: 500; white-space: nowrap;
}}
td {{ padding: 8px 12px; border-bottom: 1px solid #eee; white-space: nowrap; }}
tr:hover td {{ background: #f8f9fa; }}

/* ---- Tags ---- */
.tag-buy {{
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 11px; font-weight: 600; background: #e8f8f5; color: #27ae60;
}}
.tag-sell {{
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 11px; font-weight: 600; background: #fdedec; color: #e74c3c;
}}
.pnl-positive {{ color: #27ae60; font-weight: 600; }}
.pnl-negative {{ color: #e74c3c; font-weight: 600; }}
.footer {{ text-align: center; padding: 20px; color: #999; font-size: 12px; }}

/* =====================================================
   Tablet landscape & small desktop (769px - 1024px)
   ===================================================== */
@media (max-width: 1024px) {{
  .container {{ padding: 16px; }}
  .cards {{ gap: 10px; }}
  .card-value {{ font-size: 20px; }}
  .header h1 {{ font-size: 22px; }}
}}

/* =====================================================
   Tablet portrait (481px - 768px)
   ===================================================== */
@media (max-width: 768px) {{
  .container {{ padding: 12px; }}
  .header {{ padding: 20px; }}
  .header h1 {{ font-size: 20px; }}
  .header p {{ font-size: 13px; }}
  .cards {{ grid-template-columns: repeat(2, 1fr); gap: 10px; }}
  .card {{ padding: 12px; }}
  .card-value {{ font-size: 18px; }}
  .chart-box {{ padding: 12px; }}
  table {{ font-size: 12px; }}
  th, td {{ padding: 8px 10px; }}
}}

/* =====================================================
   Phone (<=480px) — tables become stacked cards
   ===================================================== */
@media (max-width: 480px) {{
  .container {{ padding: 6px; }}
  .header {{ padding: 14px 12px; border-radius: 8px; margin-bottom: 14px; }}
  .header h1 {{ font-size: 16px; }}
  .header p {{ font-size: 11px; }}
  .cards {{ grid-template-columns: repeat(2, 1fr); gap: 6px; margin-bottom: 14px; }}
  .card {{ padding: 10px 8px; border-radius: 8px; }}
  .card-label {{ font-size: 9px; margin-bottom: 2px; }}
  .card-value {{ font-size: 14px; }}
  .chart-box {{ padding: 8px; border-radius: 8px; margin-bottom: 14px; }}
  .chart-box h2 {{ font-size: 13px; margin-bottom: 8px; }}
  .footer {{ font-size: 9px; padding: 10px; }}

  /* ---- Tables rightarrow stacked card layout ---- */
  .table-wrap table,
  .table-wrap thead,
  .table-wrap tbody,
  .table-wrap th,
  .table-wrap td,
  .table-wrap tr {{
    display: block;
  }}
  .table-wrap thead {{ display: none; }}
  .table-wrap tr {{
    margin-bottom: 8px;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 10px 12px;
    background: white;
  }}
  .table-wrap td {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 0;
    border-bottom: 1px solid #f0f0f0;
    white-space: normal;
    font-size: 13px;
  }}
  .table-wrap td:last-child {{ border-bottom: none; }}
  .table-wrap td::before {{
    content: attr(data-label);
    font-weight: 600;
    color: #888;
    font-size: 12px;
    flex-shrink: 0;
    margin-right: 12px;
  }}
  .table-wrap td:first-child {{ padding-top: 0; }}
  .table-wrap td:last-child {{ padding-bottom: 0; }}
  .table-wrap tr:hover td {{ background: transparent; }}
}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>QKA \u56de\u6d4b\u62a5\u544a</h1>
    <p>\u7b56\u7565: {strategy_name} &nbsp;|&nbsp; \u751f\u6210\u65f6\u95f4: {now}</p>
  </div>

  <div class="cards">
    <div class="card">
      <div class="card-label">\u603b\u6536\u76ca\u7387</div>
      <div class="card-value {'positive' if metrics['total_return_pct'] >= 0 else 'negative'}">
        {metrics['total_return_pct']:+.2f}%
      </div>
    </div>
    <div class="card">
      <div class="card-label">\u5e74\u5316\u6536\u76ca\u7387</div>
      <div class="card-value {'positive' if metrics['annual_return_pct'] >= 0 else 'negative'}">
        {metrics['annual_return_pct']:+.2f}%
      </div>
    </div>
    <div class="card">
      <div class="card-label">\u590f\u666e\u6bd4\u7387</div>
      <div class="card-value">{metrics['sharpe_ratio']:.2f}</div>
    </div>
    <div class="card">
      <div class="card-label">\u6700\u5927\u56de\u64a4</div>
      <div class="card-value negative">{metrics['max_drawdown_pct']:.2f}%</div>
    </div>
    <div class="card">
      <div class="card-label">\u80dc\u7387</div>
      <div class="card-value">{metrics['win_rate_pct']:.1f}%</div>
    </div>
    <div class="card">
      <div class="card-label">\u76c8\u4e8f\u6bd4</div>
      <div class="card-value">{metrics['profit_loss_ratio']:.2f}</div>
    </div>
    <div class="card">
      <div class="card-label">\u4ea4\u6613\u6b21\u6570</div>
      <div class="card-value">{metrics['total_trades']}</div>
    </div>
    <div class="card">
      <div class="card-label">\u603b\u624b\u7eed\u8d39</div>
      <div class="card-value">\u00a5{metrics['total_commission']:,.2f}</div>
    </div>
  </div>

  <div class="chart-box">
    <div id="equityChart"></div>
  </div>

  {monthly_chart_div}

  <div class="chart-box">
    <h2>\u4ea4\u6613\u660e\u7ec6</h2>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>\u65e5\u671f</th><th>\u65b9\u5411</th><th>\u4ee3\u7801</th><th>\u6570\u91cf</th>
          <th>\u6210\u4ea4\u4ef7</th><th>\u6210\u4ea4\u91d1\u989d</th><th>\u624b\u7eed\u8d39</th>
        </tr></thead>
        <tbody>
          {trades_table_rows}
        </tbody>
      </table>
    </div>
  </div>

  {drawdown_section}

  <div class="footer">
    \u7531 QKA (github.com/zsrl/qka) \u751f\u6210
  </div>
</div>

<script>
var equityData = {equity_chart_json};
Plotly.newPlot('equityChart', equityData.data, equityData.layout, {{responsive: true}});
{monthly_chart_js}
</script>
</body>
</html>"""


def _build_trades_table(trades: list) -> str:
    """生成交易明细 HTML 行（带 data-label 属性，用于移动端卡片化）"""
    rows = []
    for t in trades:
        action = t['action']
        tag = '<span class="tag-buy">买入</span>' if action == 'buy' else '<span class="tag-sell">卖出</span>'
        price = t.get('exec_price', t.get('price', 0))
        amount = t.get('amount', 0)
        comm = t.get('commission', 0)
        ts = t.get('timestamp', '')
        ts_str = str(ts.date()) if hasattr(ts, 'date') else str(ts)[:10]
        rows.append(f'''<tr>
          <td data-label="日期">{ts_str}</td>
          <td data-label="方向">{tag}</td>
          <td data-label="代码">{t['symbol']}</td>
          <td data-label="数量">{t['size']:,}</td>
          <td data-label="成交价">¥{price:.2f}</td>
          <td data-label="成交金额">¥{amount:,.2f}</td>
          <td data-label="手续费">¥{comm:.2f}</td>
        </tr>''')
    return '\n'.join(rows)


def _build_drawdown_table(dd_list: list) -> str:
    """生成回撤分析 HTML 行（带 data-label 属性，用于移动端卡片化）"""
    rows = []
    for i, d in enumerate(dd_list, 1):
        rows.append(f'''<tr>
          <td data-label="#">{i}</td>
          <td data-label="开始">{d['start'].date()}</td>
          <td data-label="结束">{d['end'].date()}</td>
          <td data-label="回撤幅度" class="pnl-negative">{d['depth']:.2f}%</td>
          <td data-label="持续天数">{d['duration']} 天</td>
        </tr>''')
    return '\n'.join(rows)


def generate_report(
    results: pd.DataFrame,
    broker,
    initial_cash: float,
    benchmark_data: Optional[pd.Series] = None,
    strategy_name: str = '未命名策略',
    output_path: Optional[str] = None,
) -> str:
    """
    生成 HTML 回测报告

    Args:
        results: trades DataFrame
        broker: Broker 实例
        initial_cash: 初始资金
        benchmark_data: 基准数据（可选）
        strategy_name: 策略名称
        output_path: 输出路径，None 则自动生成

    Returns:
        str: HTML 文件路径
    """
    if results is None or results.empty or 'total' not in results.columns:
        raise ValueError("无可用的回测数据")

    totals = results['total']
    if len(totals) < 2:
        raise ValueError("数据不足（至少需要 2 个交易日）")

    # ---- 计算绩效指标 ----
    initial = float(totals.iloc[0])
    final = float(totals.iloc[-1])
    total_return = (final / initial - 1) * 100

    n_days = len(totals)
    years = n_days / 252
    daily_returns = _calc_daily_returns(totals)

    annual_return = (final / initial) ** (1 / years) - 1 if years > 0 else 0
    annual_vol = float(daily_returns.std() * np.sqrt(252))
    risk_free = 0.03
    sharpe = (annual_return - risk_free) / annual_vol if annual_vol > 0 else 0

    dd_series = _calc_drawdown_series(daily_returns)
    max_dd = float(dd_series.min() * 100)
    calmar = annual_return / abs(max_dd / 100) if max_dd != 0 else 0

    # 交易统计
    trades = broker.trade_history
    n_trades = len(trades)
    win_rate = 0.0
    profit_loss_ratio = 0.0

    if n_trades > 0:
        trade_pnl = []
        buy_prices = {}
        for t in trades:
            if t['action'] == 'buy':
                buy_prices.setdefault(t['symbol'], [])
                buy_prices[t['symbol']].append((t['size'], t['exec_price'], t['total_cost']))
            elif t['action'] == 'sell':
                symbol = t['symbol']
                size = t['size']
                net_proceeds = t['net_proceeds']
                if symbol in buy_prices and buy_prices[symbol]:
                    total_buy_cost = 0
                    remaining = size
                    while remaining > 0 and buy_prices[symbol]:
                        b_size, b_price, b_cost = buy_prices[symbol][0]
                        if b_size <= remaining:
                            total_buy_cost += b_cost
                            remaining -= b_size
                            buy_prices[symbol].pop(0)
                        else:
                            ratio = remaining / b_size
                            total_buy_cost += b_cost * ratio
                            buy_prices[symbol][0] = (b_size - remaining, b_price, b_cost * (1 - ratio))
                            remaining = 0
                    trade_pnl.append(net_proceeds - total_buy_cost)

        if trade_pnl:
            wins = sum(1 for p in trade_pnl if p > 0)
            win_rate = wins / len(trade_pnl) * 100
            avg_win = float(np.mean([p for p in trade_pnl if p > 0])) if any(p > 0 for p in trade_pnl) else 0
            avg_loss = float(abs(np.mean([p for p in trade_pnl if p <= 0]))) if any(p <= 0 for p in trade_pnl) else 0
            profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

    metrics = {
        'initial_cash': initial,
        'final_equity': final,
        'total_return_pct': total_return,
        'annual_return_pct': annual_return * 100,
        'annual_volatility_pct': annual_vol * 100,
        'sharpe_ratio': sharpe,
        'max_drawdown_pct': max_dd,
        'calmar_ratio': calmar,
        'total_trades': n_trades,
        'win_rate_pct': win_rate,
        'profit_loss_ratio': profit_loss_ratio,
        'total_commission': broker.total_commission,
        'n_days': n_days,
    }

    # ---- 生成图表 ----
    equity_chart_json = _make_equity_chart(results, initial_cash, benchmark_data)
    monthly_chart_json = _make_monthly_heatmap(daily_returns)

    # ---- 生成表格 ----
    trades_table_rows = _build_trades_table(trades)

    dd_list = _find_drawdown_periods(daily_returns, top_n=5)
    drawdown_rows = _build_drawdown_table(dd_list)

    # ---- 组装 HTML ----
    html = _build_html(metrics, equity_chart_json, monthly_chart_json,
                       trades_table_rows, drawdown_rows, strategy_name)

    # ---- 保存 ----
    if output_path is None:
        reports_dir = Path.cwd() / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c for c in strategy_name if c.isalnum() or c in " _-").strip()[:40]
        output_path = str(reports_dir / f"回测报告_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"[OK] 回测报告已生成: {output_path}")
    return output_path
