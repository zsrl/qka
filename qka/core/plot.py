import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Any
import numpy as np

def plot(result: Dict[str, Any], title: str = "回测结果"):
    """
    绘制回测结果图表
    
    Args:
        result: backtest()函数返回的结果字典
        title: 图表标题
    
    Examples:
        import qka
        
        result = qka.backtest(data, strategy)
        qka.plot(result)
    """
    
    if 'daily_values' not in result or not result['daily_values']:
        print("错误：回测结果中没有日收益数据")
        return
    
    # 提取数据
    daily_data = result['daily_values']
    dates = [record['date'] for record in daily_data]
    values = [record['total_value'] for record in daily_data]
    
    # 计算累计收益率和其他指标
    initial_value = result['initial_capital']
    returns = [(v - initial_value) / initial_value * 100 for v in values]
    
    # 计算每日收益率
    daily_returns = []
    for i in range(1, len(values)):
        daily_return = (values[i] - values[i-1]) / values[i-1] * 100
        daily_returns.append(daily_return)
    
    # 计算回撤
    peak_values = pd.Series(values).expanding().max()
    drawdowns = [(v - peak) / peak * 100 for v, peak in zip(values, peak_values)]
    
    # 定义颜色函数
    def get_color_style(value):
        """根据值的正负返回颜色样式"""
        if value < 0:
            return "color: red;"
        else:
            return "color: green;"
    
    # 创建子图
    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=(
            '累计收益率曲线', '回撤分析',
            '资产价值变化', '每日收益率分布',
            '滚动夏普比率', '月度收益'
        ),
        specs=[
            [{"colspan": 2}, None],
            [{"secondary_y": False}, {"type": "histogram"}],
            [{"secondary_y": False}, {"secondary_y": False}]
        ],
        vertical_spacing=0.12,
        horizontal_spacing=0.1
    )
    
    # 1. 累计收益率曲线 (主图)
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=returns,
            mode='lines',
            name='累计收益率',
            line=dict(color='#2E86AB', width=3),
            hovertemplate='日期: %{x}<br>收益率: %{y:.2f}%<extra></extra>'
        ),
        row=1, col=1
    )
    
    # 添加零轴线
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5, row=1, col=1)
    
    # 2. 回撤分析
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=drawdowns,
            mode='lines',
            name='回撤',
            line=dict(color='#A23B72', width=2),
            fill='tonexty',
            fillcolor='rgba(162, 59, 114, 0.2)',
            hovertemplate='日期: %{x}<br>回撤: %{y:.2f}%<extra></extra>'
        ),
        row=2, col=1
    )
    
    # 3. 资产价值变化
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=values,
            mode='lines',
            name='总资产',
            line=dict(color='#F18F01', width=2),
            hovertemplate='日期: %{x}<br>资产: ¥%{y:,.0f}<extra></extra>'
        ),
        row=2, col=2
    )
    
    # 4. 每日收益率分布
    if daily_returns:
        fig.add_trace(
            go.Histogram(
                x=daily_returns,
                name='每日收益率',
                nbinsx=30,
                marker_color='#C73E1D',
                opacity=0.7,
                hovertemplate='收益率: %{x:.2f}%<br>频次: %{y}<extra></extra>'
            ),
            row=3, col=1
        )
    
    # 5. 滚动夏普比率 (30日)
    if len(daily_returns) > 30:
        rolling_sharpe = []
        for i in range(30, len(daily_returns)):
            window_returns = daily_returns[i-30:i]
            if len(window_returns) > 0:
                mean_return = np.mean(window_returns)
                std_return = np.std(window_returns)
                sharpe = (mean_return * 252) / (std_return * np.sqrt(252)) if std_return > 0 else 0
                rolling_sharpe.append(sharpe)
        
        if rolling_sharpe:
            fig.add_trace(
                go.Scatter(
                    x=dates[30:30+len(rolling_sharpe)],
                    y=rolling_sharpe,
                    mode='lines',
                    name='30日滚动夏普',
                    line=dict(color='#3F88C5', width=2),
                    hovertemplate='日期: %{x}<br>夏普比率: %{y:.2f}<extra></extra>'
                ),
                row=3, col=2
            )
    
    # 更新布局
    fig.update_layout(
        title=dict(
            text=f"{title}<br><sub>总收益: <span style='{get_color_style(result['total_return'])}'>{result['total_return']:.2%}</span> | 年化收益: <span style='{get_color_style(result['annual_return'])}'>{result['annual_return']:.2%}</span> | 夏普比率: <span style='{get_color_style(result['sharpe_ratio'])}'>{result['sharpe_ratio']:.2f}</span> | 最大回撤: <span style='{get_color_style(result['max_drawdown'])}'>{result['max_drawdown']:.2%}</span></sub>",
            x=0.5,
            font=dict(size=16)
        ),
        height=800,
        showlegend=True,
        template='plotly_white',
        margin=dict(t=120, b=60, l=60, r=60)
    )
    
    # 更新子图标题
    fig.update_xaxes(title_text="日期", row=1, col=1)
    fig.update_yaxes(title_text="累计收益率 (%)", row=1, col=1)
    
    fig.update_xaxes(title_text="日期", row=2, col=1)
    fig.update_yaxes(title_text="回撤 (%)", row=2, col=1)
    
    fig.update_xaxes(title_text="日期", row=2, col=2)
    fig.update_yaxes(title_text="资产价值 (¥)", row=2, col=2)
    
    fig.update_xaxes(title_text="每日收益率 (%)", row=3, col=1)
    fig.update_yaxes(title_text="频次", row=3, col=1)
    
    fig.update_xaxes(title_text="日期", row=3, col=2)
    fig.update_yaxes(title_text="夏普比率", row=3, col=2)
    
    # 显示图表
    fig.show()
    
    # 打印关键指标
    print(f"\n📊 回测结果摘要")
    print(f"{'='*50}")
    print(f"📈 收益指标:")
    print(f"   总收益率:     {result['total_return']:.2%}")
    print(f"   年化收益率:   {result['annual_return']:.2%}")
    print(f"   基准收益率:   {result.get('benchmark_return', 'N/A')}")
    print(f"")
    print(f"⚠️  风险指标:")
    print(f"   波动率:       {result['volatility']:.2%}")
    print(f"   夏普比率:     {result['sharpe_ratio']:.2f}")
    print(f"   最大回撤:     {result['max_drawdown']:.2%}")
    print(f"")
    print(f"📊 交易指标:")
    print(f"   胜率:         {result['win_rate']:.2%}")
    print(f"   总交易次数:   {result['total_trades']}")
    print(f"   交易成本:     ¥{result['total_commission']:,.2f}")
    print(f"   交易天数:     {result['trading_days']}")
    
    # 计算额外统计信息
    if daily_returns:
        print(f"")
        print(f"📋 统计信息:")
        print(f"   平均日收益:   {np.mean(daily_returns):.3f}%")
        print(f"   收益标准差:   {np.std(daily_returns):.3f}%")
        print(f"   最大单日收益: {max(daily_returns):.2f}%")
        print(f"   最大单日亏损: {min(daily_returns):.2f}%")
        
        # 计算胜负比
        positive_days = len([r for r in daily_returns if r > 0])
        total_days = len(daily_returns)
        if total_days > 0:
            print(f"   盈利天数占比: {positive_days/total_days:.2%}")
    
    print(f"{'='*50}")
