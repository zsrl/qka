""" QKA回测引擎模块

提供基于时间序列的回测功能，支持多股票横截面数据处理，
包含完整的交易记录、绩效分析和可视化功能。
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from typing import Optional
from pathlib import Path


class Backtest:
    """
    QKA回测引擎类

    提供基于时间序列的回测功能，支持多股票横截面数据处理，
    以及绩效指标计算和可视化。

    Attributes:
        data (Data): 数据对象实例
        strategy (Strategy): 策略对象实例
        results (pd.DataFrame): 回测结果数据
        initial_cash (float): 初始资金
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
        self.results = None
        self.initial_cash = strategy.broker.cash
        self._benchmark_data = None

    def run(self, benchmark: Optional[str] = None):
        """
        执行回测

        遍历所有时间点，在每个时间点调用策略的on_bar方法进行交易决策，
        并记录交易后的状态。

        Args:
            benchmark (str, optional): 基准代码，如 '000300.SH'（沪深300）。
                                       如果提供，会下载基准数据用于对比。
        """
        # 获取所有股票数据（dask DataFrame）
        df = self.data.get()

        # 加载基准数据
        if benchmark:
            self._load_benchmark(benchmark)

        for date, row in df.iterrows():
            def get(factor):
                """
                获取指定因子的数据

                Args:
                    factor (str): 因子名称，如 'close', 'volume' 等

                Returns:
                    pd.Series: 该因子的所有股票数据，index为股票代码
                """
                s = row[row.index.str.endswith(factor)]
                s.index = s.index.str.replace(f'_{factor}$', '', regex=True)
                return s

            # 调用策略的on_bar方法
            self.strategy.on_bar(date, get)

            # 记录Bar结束后的状态
            self.strategy.broker.on_bar(date, get)

        # 保存回测结果
        self.results = self.strategy.broker.trades

    def _load_benchmark(self, benchmark_code: str):
        """
        加载基准指数数据

        Args:
            benchmark_code: 基准代码，如 '000300.SH'
        """
        try:
            import akshare as ak
            clean_code = benchmark_code.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
            bm_df = ak.stock_zh_index_daily(symbol=f"sh{clean_code}")
            if bm_df is not None and not bm_df.empty:
                bm_df['date'] = pd.to_datetime(bm_df['date'])
                bm_df = bm_df.set_index('date')
                bm_df = bm_df.sort_index()
                self._benchmark_data = bm_df['close']
                print(f"基准数据加载成功: {benchmark_code}，{len(bm_df)} 个交易日")
        except Exception as e:
            print(f"基准数据加载失败: {e}")

    def summary(self) -> dict:
        """
        计算并打印回测绩效指标

        返回包含以下指标的字典：
        - 总收益率、年化收益率、年化波动率
        - 夏普比率、最大回撤、Calmar比率
        - 胜率、盈亏比、交易次数
        - 最终资产、总手续费

        Returns:
            dict: 绩效指标字典
        """
        if self.results is None or self.results.empty:
            print("请先运行回测 (backtest.run())")
            return {}

        totals = self.results['total']
        if len(totals) < 2:
            print("回测数据不足（至少需要2个交易周期）")
            return {}

        # 基本数据
        initial = self.initial_cash
        final = totals.iloc[-1]
        total_return = (final / initial - 1) * 100

        # 交易天数 / 年化
        n_days = len(totals)
        years = n_days / 252  # A股年均约252个交易日

        # 日收益率序列
        daily_returns = totals.pct_change().dropna()
        if len(daily_returns) == 0:
            print("没有足够的收益率数据")
            return {}

        # 年化收益率
        annual_return = (final / initial) ** (1 / years) - 1 if years > 0 else 0

        # 年化波动率
        annual_vol = daily_returns.std() * np.sqrt(252)

        # 夏普比率（无风险利率假设 3%）
        risk_free_rate = 0.03
        sharpe = (annual_return - risk_free_rate) / annual_vol if annual_vol > 0 else 0

        # 最大回撤
        cumulative = (1 + daily_returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min() * 100

        # Calmar 比率
        calmar = annual_return / abs(max_drawdown / 100) if max_drawdown != 0 else 0

        # 交易分析
        trades = self.strategy.broker.trade_history
        n_trades = len(trades)

        if n_trades > 0:
            # 统计每笔交易的盈亏
            trade_pnl = []
            buy_prices = {}
            for t in trades:
                if t['action'] == 'buy':
                    if t['symbol'] not in buy_prices:
                        buy_prices[t['symbol']] = []
                    buy_prices[t['symbol']].append((t['size'], t['exec_price'], t['total_cost']))
                elif t['action'] == 'sell':
                    symbol = t['symbol']
                    size = t['size']
                    net_proceeds = t['net_proceeds']
                    # 按先进先出匹配买入
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
                        pnl = net_proceeds - total_buy_cost
                        trade_pnl.append(pnl)

            win_trades = sum(1 for p in trade_pnl if p > 0)
            win_rate = (win_trades / len(trade_pnl) * 100) if trade_pnl else 0
            avg_win = np.mean([p for p in trade_pnl if p > 0]) if any(p > 0 for p in trade_pnl) else 0
            avg_loss = abs(np.mean([p for p in trade_pnl if p <= 0])) if any(p <= 0 for p in trade_pnl) else 0
            profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0
        else:
            win_rate = 0
            profit_loss_ratio = 0
            trade_pnl = []

        # 总手续费
        total_commission = self.strategy.broker.total_commission

        # 打印报告
        print("=" * 55)
        print("           回测绩效报告")
        print("=" * 55)
        print(f"  初始资金:        ¥{initial:>10,.2f}")
        print(f"  最终资产:        ¥{final:>10,.2f}")
        print(f"  总收益率:         {total_return:>+8.2f}%")
        print(f"  年化收益率:       {annual_return * 100:>+8.2f}%")
        print(f"  年化波动率:       {annual_vol * 100:>8.2f}%")
        print(f"  夏普比率:         {sharpe:>8.2f}")
        print(f"  最大回撤:         {max_drawdown:>8.2f}%")
        print(f"  Calmar比率:       {calmar:>8.2f}")
        print(f"  交易次数:         {n_trades:>8}")
        print(f"  胜率:             {win_rate:>8.2f}%")
        print(f"  盈亏比:           {profit_loss_ratio:>8.2f}")
        print(f"  总手续费:         ¥{total_commission:>10,.2f}")
        print(f"  回测天数:         {n_days:>8} 天")
        print("=" * 55)

        return {
            'initial_cash': initial,
            'final_equity': final,
            'total_return_pct': total_return,
            'annual_return_pct': annual_return * 100,
            'annual_volatility_pct': annual_vol * 100,
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_drawdown,
            'calmar_ratio': calmar,
            'total_trades': n_trades,
            'win_rate_pct': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
            'total_commission': total_commission,
            'n_days': n_days,
        }

    def plot(self, title="回测收益曲线"):
        """
        绘制回测收益曲线

        展示策略总资产变化曲线，如果设置了基准则叠加基准曲线。

        Args:
            title (str): 图表标题

        Returns:
            go.Figure: Plotly图表对象
        """
        if self.results is None or self.results.empty:
            print("请先运行回测 (backtest.run())")
            return None

        fig = go.Figure()

        # 策略收益曲线
        fig.add_trace(go.Scatter(
            x=self.results.index,
            y=self.results['total'],
            mode='lines',
            name='策略资产',
            line=dict(color='#2E86AB', width=3),
            hovertemplate='日期: %{x}<br>策略资产: ¥%{y:,.2f}<extra></extra>'
        ))

        # 基准曲线（如果有）
        if self._benchmark_data is not None:
            # 对齐基准到回测时间范围
            bm = self._benchmark_data.reindex(self.results.index, method='ffill')
            if not bm.empty:
                # 归一化基准到初始资金起点
                bm_normalized = bm / bm.iloc[0] * self.initial_cash
                fig.add_trace(go.Scatter(
                    x=bm_normalized.index,
                    y=bm_normalized.values,
                    mode='lines',
                    name='基准 (沪深300)',
                    line=dict(color='#E07A5F', width=2, dash='dash'),
                    hovertemplate='日期: %{x}<br>基准资产: ¥%{y:,.2f}<extra></extra>'
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

        # 自动保存 HTML 文件到 examples/charts/
        try:
            charts_dir = Path.cwd() / "examples" / "charts"
            charts_dir.mkdir(parents=True, exist_ok=True)
            safe_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()[:50]
            html_path = charts_dir / f"{safe_title}.html"
            fig.write_html(str(html_path))
            print(f"📊 图表已保存: {html_path}")
        except Exception as e:
            pass  # 保存失败不阻塞主流程

        return fig

    def report(self, title: str = "未命名策略", output_path: Optional[str] = None) -> str:
        """
        生成自包含的 HTML 回测报告

        包含绩效指标卡片、净值曲线、回撤曲线、月度收益率热力图、
        交易明细表和回撤分析。可直接在浏览器中打开。

        Args:
            title: 策略名称（显示在报告标题中）
            output_path: 输出 HTML 文件路径。
                         None 则自动保存在 examples/charts/ 下

        Returns:
            str: HTML 文件路径
        """
        from qka.core.report import generate_report

        if self.results is None or self.results.empty:
            print("错误：请先运行回测 (bt.run())")
            return ""

        bm = getattr(self, '_benchmark_data', None)
        return generate_report(
            results=self.results,
            broker=self.strategy.broker,
            initial_cash=self.initial_cash,
            benchmark_data=bm,
            strategy_name=title,
            output_path=output_path,
        )
