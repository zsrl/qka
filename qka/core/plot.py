import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Any

def plot_backtest(result: Dict[str, Any], title: str = "回测结果"):
    """
    绘制回测结果图表
    
    Args:
        result: backtest()函数返回的结果字典
        title: 图表标题
    
    Examples:
        from qka.core.plot import plot_backtest
        
        result = backtest(data, strategy)
        plot_backtest(result)
    """
    
    if 'daily_values' not in result or not result['daily_values']:
        print("错误：回测结果中没有日收益数据")
        return
    
    # 提取数据
    daily_data = result['daily_values']
    dates = [record['date'] for record in daily_data]
    values = [record['total_value'] for record in daily_data]
    
    # 计算累计收益率
    initial_value = result['initial_capital']
    returns = [(v - initial_value) / initial_value * 100 for v in values]
    
    # 定义颜色函数
    def get_color_style(value):
        """根据值的正负返回颜色样式"""
        if value < 0:
            return "color: green;"
        else:
            return "color: red;"
    
    # 创建图表
    fig = go.Figure()
    
    # 累计收益率曲线
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=returns,
            mode='lines',
            name='累计收益率',
            line=dict(color='#1f77b4', width=2),
            hovertemplate='日期: %{x}<br>收益率: %{y:.2f}%<extra></extra>'
        )
    )
    
    # 添加零轴线
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    
    # 更新布局
    fig.update_layout(
        title=dict(
            text=f"{title}<br><sub>总收益: <span style='{get_color_style(result['total_return'])}'>{result['total_return']:.2%}</span> | 年化收益: <span style='{get_color_style(result['annual_return'])}'>{result['annual_return']:.2%}</span> | 夏普比率: <span style='{get_color_style(result['sharpe_ratio'])}'>{result['sharpe_ratio']:.2f}</span> | 最大回撤: <span style='{get_color_style(result['max_drawdown'])}'>{result['max_drawdown']:.2%}</span></sub>",
            x=0.5,
            font=dict(size=20)
        ),
        height=500,
        showlegend=False,
        template='plotly_white',
        margin=dict(t=100, b=50, l=50, r=50),
        xaxis_title="日期",
        yaxis_title="累计收益率 (%)"
    )
    
    # 显示图表
    fig.show()
    
    # 打印关键指标
    print(f"\n📊 回测结果摘要")
    print(f"{'='*40}")
    print(f"总收益率:     {result['total_return']:.2%}")
    print(f"年化收益率:   {result['annual_return']:.2%}")
    print(f"波动率:       {result['volatility']:.2%}")
    print(f"夏普比率:     {result['sharpe_ratio']:.2f}")
    print(f"最大回撤:     {result['max_drawdown']:.2%}")
    print(f"胜率:         {result['win_rate']:.2%}")
    print(f"总交易次数:   {result['total_trades']}")
    print(f"交易成本:     ¥{result['total_commission']:,.2f}")
    print(f"交易天数:     {result['trading_days']}")
    print(f"{'='*40}")
