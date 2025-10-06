"""
QKA回测引擎模块

提供基于时间序列的回测功能，支持多股票横截面数据处理，包含完整的交易记录和可视化功能。
"""

import plotly.graph_objects as go

class Backtest:
    """
    QKA回测引擎类
    
    提供基于时间序列的回测功能，支持多股票横截面数据处理。
    
    Attributes:
        data (Data): 数据对象实例
        strategy (Strategy): 策略对象实例
    """
    
    def __init__(self, data, strategy):
        """
        初始化回测引擎
        
        Args:
            data (Data): Data类的实例，包含股票数据
            strategy (Strategy): 策略对象，必须包含on_bar方法
        """
        self.data = data
        self.strategy = strategy
    
    def run(self):
        """
        执行回测
        
        遍历所有时间点，在每个时间点调用策略的on_bar方法进行交易决策，
        并记录交易后的状态。
        """
        # 获取所有股票数据（dask DataFrame）
        df = self.data.get()

        for date, row in df.iterrows():
            def get(factor):
                """
                获取指定因子的数据
                
                Args:
                    factor (str): 因子名称，如 'close', 'volume' 等
                    
                Returns:
                    pd.Series: 该因子在所有股票上的值
                """
                s = row[row.index.str.endswith(factor)]
                s.index = s.index.str.replace(f'_{factor}$', '', regex=True)
                return s
            
            # 先调用策略的on_bar（可能包含交易操作）
            self.strategy.on_bar(date, get)
            
            # 再调用broker的on_bar记录状态（包含交易后的状态）
            self.strategy.broker.on_bar(date, get)
    
    def plot(self, title="回测收益曲线"):
        """
        绘制回测收益曲线图
        
        Args:
            title (str): 图表标题，默认为"回测收益曲线"
            
        Returns:
            plotly.graph_objects.Figure: 交互式图表对象，如果无数据则返回None
        """
        
        # 获取交易数据
        trades_df = self.strategy.broker.trades
        
        # 检查是否有数据
        if trades_df.empty or 'total' not in trades_df.columns:
            print("错误：没有可用的回测数据或缺少total列")
            return None
        
        # 提取总资产数据
        total_assets = trades_df['total']
        
        # 创建交互式图表
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=total_assets.index,
            y=total_assets.values,
            mode='lines',
            name='总资产',
            line=dict(color='#2E86AB', width=3),
            hovertemplate='日期: %{x}<br>总资产: ¥%{y:,.2f}<extra></extra>'
        ))
        
        # 更新布局
        fig.update_layout(
            title=dict(
                text=title,
                x=0.5,
                font=dict(size=16)
            ),
            xaxis_title="日期",
            yaxis_title="总资产 (¥)",
            height=600,
            showlegend=True,
            template='plotly_white',
            hovermode='x unified'
        )
        
        # 添加网格线
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGrey')
        
        # 显示图表
        fig.show()
        
        return fig