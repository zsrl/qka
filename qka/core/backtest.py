""" QKA回测引擎模块

提供基于时间序列的回测功能，支持多股票横截面数据处理，
包含完整的交易记录、绩效分析和可视化功能。
"""

import logging
from pathlib import Path

import pandas as pd
import numpy as np
import dask.dataframe as dd
from typing import Optional, Union
from collections import defaultdict
from qka.core.broker import Broker
from qka.core.accessor import DataAccessor
from qka.core.sizing import SizingAccessor

logger = logging.getLogger(__name__)


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
        self.initial_cash = None  # 由 run() 设置
        self.metrics = None
        self._benchmark_data = None       # 基准收盘价序列（HTML 报告画曲线用）
        self._benchmark_returns = None    # 基准日收益（算 alpha/beta 用）
        # 报告里算夏普用的无风险利率（年化，小数）。默认 3%，与历史报告可比。
        # 要换口径就在 run() 之后直接改这个属性。因子那边用 Data(risk_free=...)
        # 可以逐窗口时变，回测是一整段区间的单一指标，这里保持一个可覆写的数。
        self.risk_free_rate = 0.03

    @property
    def trade_history(self):
        """逐笔交易明细（list[dict]）"""
        return self.strategy.broker.trade_history if hasattr(self.strategy, 'broker') else []

    @property
    def trades(self):
        """每日资金/市值/持仓快照（pd.DataFrame）"""
        return self.strategy.broker.trades if hasattr(self.strategy, 'broker') else pd.DataFrame()

    @staticmethod
    def _parse_row(row):
        """
        解析一行 iterrows 数据为 per-factor 字典。

        列名格式: {symbol}|{factor}
        例: '000001.SZ|close' → factor='close', symbol='000001.SZ'
            '000001.SZ|sma_5' → factor='sma_5', symbol='000001.SZ'

        Args:
            row: pd.Series，列名格式 {symbol}|{factor}

        Returns:
            dict: {factor: {symbol: value}}
        """
        by_factor = defaultdict(dict)
        for col, val in row.items():
            if not isinstance(col, str) or '|' not in col:
                continue
            *sym_parts, factor = col.rsplit('|', 1)
            symbol = '|'.join(sym_parts)
            by_factor[factor][symbol] = val
        return dict(by_factor)

    @staticmethod
    def _build_layout(columns):
        """列名 → {factor: [(symbol, 列号)]}，**整段回测只解析一次**。

        列名格式 `{symbol}|{factor}`，所有 bar 共用同一套列。原来每根 bar 都
        `rsplit` 一遍全部列名：451 只 × 8 字段 × 1646 天 = 594 万次字符串切分，
        纯属重复劳动（实测 `_parse_row` 累计 19 秒）。
        """
        layout: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for i, col in enumerate(columns):
            if not isinstance(col, str) or '|' not in col:
                continue
            sym, _, factor = col.rpartition('|')
            layout[factor].append((sym, i))
        return dict(layout)

    def _run_bars(self, dates, values, layout):
        """逐 bar 驱动：推数据 → 策略决策 → broker 撮合。

        values 是 (days × cols) 的 numpy 数组，按位置取值。比 `df.iterrows()`
        快一个量级 —— iterrows 每行都要构造一个 Series 并做 dtype 推断
        （实测这两项合计 20 秒以上）。
        """
        data_acc = self.strategy._data
        broker = self.strategy.broker
        push = data_acc.push
        on_bar = self.strategy.on_bar

        for i, date in enumerate(dates):
            row = values[i]
            for factor, entries in layout.items():
                push(date, factor, {sym: row[ci] for sym, ci in entries})
            broker.timestamp = date
            on_bar(date)
            broker.on_bar(date, data_acc.get)

    def run(self, cash: float = 100000.0,
            start_date: str = None, end_date: str = None,
            benchmark: Optional[str] = None,
            commission_rate: float = None,
            stamp_duty_rate: float = None,
            slippage: float = None):
        """
        执行回测

        遍历所有时间点，在每个时间点调用策略的on_bar方法进行交易决策，
        并记录交易后的状态。

        大规模回测（>500 bar）时自动使用分区迭代，分块加载数据到内存，
        避免一次性加载全量数据。

        Args:
            cash: 初始资金，默认 10 万元
            start_date: 回测起始日期 YYYY-MM-DD，None 表示数据最早日期
            end_date: 回测截止日期 YYYY-MM-DD，None 表示数据最晚日期
            benchmark: 基准代码，如 '000300.SH'（沪深300）。
                       如果提供，会下载基准数据用于对比。
            commission_rate: 佣金费率，None 表示用 Broker 默认（万 2.5，最低 5 元）
            stamp_duty_rate: 印花税率（仅卖出），None 表示用 Broker 默认（万 5）
            slippage: 滑点比率，None 表示用 Broker 默认（0.1%）

        Returns:
            None。回测结果保存在 self.results、self.metrics、self.trade_history 中。
        """
        # 注入基础设施
        self.initial_cash = cash
        broker_kwargs = {'initial_cash': cash}
        if commission_rate is not None:
            broker_kwargs['commission_rate'] = commission_rate
        if stamp_duty_rate is not None:
            broker_kwargs['stamp_duty_rate'] = stamp_duty_rate
        if slippage is not None:
            broker_kwargs['slippage'] = slippage
        self.strategy.broker = Broker(**broker_kwargs)
        self.strategy.sizing = SizingAccessor(self.strategy.broker)
        self.strategy._data = DataAccessor()

        # 获取数据
        raw = self.data.get(lazy=True, start_date=start_date, end_date=end_date)

        # 加载基准数据（同时算出日收益，供 metrics 里的 alpha/beta 使用）
        if benchmark:
            self._load_benchmark(benchmark, start_date, end_date)

        if isinstance(raw, dd.DataFrame):
            # ── dask 模式 ──
            ddf: dd.DataFrame = raw
            n_rows = len(ddf)

            # 分块是为了控制内存，**不是越小越好**：原来写死每块 500 行，
            # 451 只票 × 1646 天被切成 4 块，dask 反复建图、反复读 parquet 元数据
            # （实测 dask.tokenize 被调 50 万次、累计 10 秒）。按 ~200MB 预算反推行数。
            _cols = max(1, len(ddf.columns))
            chunk_size = max(500, int(200 * 1024 * 1024 / (_cols * 8)))

            if n_rows <= chunk_size:
                # 一次装得下：直接 compute。**不要**再走 `ddf.loc[首:尾].compute()` ——
                # 单块时那等于多套一层 dask 图，实测白白多花 25 秒。
                df = ddf.compute()
                self._run_bars(df.index, df.to_numpy(), self._build_layout(df.columns))
            else:
                index = ddf.index.compute()
                layout = None
                for start in range(0, n_rows, chunk_size):
                    end = min(start + chunk_size, n_rows)
                    date_start, date_end = index[start], index[end - 1]

                    chunk = ddf.loc[date_start:date_end].compute()
                    # 列布局整段只算一次：所有分块的列完全一致
                    if layout is None:
                        layout = self._build_layout(chunk.columns)
                    self._run_bars(chunk.index, chunk.to_numpy(), layout)
        else:
            # ── pandas 模式：向后兼容（测试 mock 数据等） ──
            df: pd.DataFrame = raw
            self._run_bars(df.index, df.to_numpy(), self._build_layout(df.columns))

        # 保存回测结果
        self.results = self.strategy.broker.trades
        self.metrics = self._compute_metrics()

    def _load_benchmark(self, benchmark_code: str, start_date=None, end_date=None):
        """加载基准指数，同时算出**日收益序列**（`self._benchmark_returns`）。

        🚨 两个坑（都在这次改掉）：

        1. 原来这里新建一个 `Data(symbols=[code])` 再 `get()` —— 走的是 Data 的默认
           source/adjust，跟回测本体可能根本不是同一个目录；本地没缓存时还会去联网。
           现在直接用回测本体已经定好的缓存目录（`self.data.target_dir`），同源同口径。

        2. 原来的数据只喂给 `generate_report()` 画一条对照曲线，`_compute_metrics()`
           一点没用上 —— 所以 `bt.run(benchmark='000300.SH')` 跑完，metrics 里
           **看不到 alpha / beta**。现在把日收益留一份，指标那边直接用。

        Args:
            benchmark_code: 基准代码，如 '000300.SH'
            start_date / end_date: 回测区间，基准只取这一段（对齐才有意义）
        """
        self._benchmark_data = None
        self._benchmark_returns = None

        # 基准文件的候选位置 —— 按顺序找，第一个存在的就用：
        #   ① `{datadir}/{source}/{period}/{adjust}/` —— 和回测本体同一个目录
        #      （qkadata 也把指数写进了 hfq，跟个股同步更新，最新）
        #   ② `{datadir}/{source}/{period}/index/` —— 指数集中的地方
        #      （桌面端/其他环境可能只同步这一个目录）
        candidates = []
        target = getattr(self.data, 'target_dir', None)
        if target:
            candidates.append(Path(target) / f"{benchmark_code}.parquet")
        datadir = getattr(self.data, 'datadir', None)
        if datadir:
            candidates.append(
                Path(datadir) / str(getattr(self.data, 'source', 'tickflow'))
                / str(getattr(self.data, 'period', '1d')) / 'index'
                / f"{benchmark_code}.parquet")

        path = next((p for p in candidates if p.exists()), None)
        if path is None:
            logger.warning('基准行情文件不存在，alpha/beta 算不了，找过：%s',
                           [str(p) for p in candidates])
            return

        try:
            df = pd.read_parquet(path)
            if 'date' not in df.columns:
                df = df.reset_index()          # 写入时把 date 存成了 index
            if 'close' not in df.columns:
                logger.warning(f'基准文件缺 close 列，跳过：{path}')
                return

            df['date'] = df['date'].astype(str).str[:10]
            if start_date is not None:
                df = df[df['date'] >= str(start_date)[:10]]
            if end_date is not None:
                df = df[df['date'] <= str(end_date)[:10]]
            if len(df) < 20:
                logger.warning(f'基准数据只有 {len(df)} 天，样本太短，跳过 alpha/beta')
                return

            df = df.drop_duplicates('date').set_index('date').sort_index()
            close = df['close'].astype(float)
            self._benchmark_data = close
            self._benchmark_returns = close.pct_change().dropna()
        except Exception as exc:               # 基准出问题不该让整个回测失败
            logger.warning(f'基准数据加载失败（不影响回测）：{exc}')

    def _compute_metrics(self) -> dict:
        """计算绩效指标。无数据时返回空 dict。"""
        if self.results is None or self.results.empty:
            return {}

        totals = self.results['total']
        if len(totals) < 2:
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
            return {}

        # 年化收益率
        annual_return = (final / initial) ** (1 / years) - 1 if years > 0 else 0

        # 年化波动率
        annual_vol = daily_returns.std() * np.sqrt(252)

        # 夏普比率（无风险利率默认 3%，可通过 self.risk_free_rate 覆写）
        risk_free_rate = self.risk_free_rate
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

        # 总手续费
        total_commission = self.strategy.broker.total_commission

        metrics = {
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

        metrics.update(self._benchmark_metrics(daily_returns))
        return metrics

    def _benchmark_metrics(self, daily_returns: pd.Series) -> dict:
        """相对基准的指标：基准收益 / alpha / beta / 信息比率。

        只在 `run(benchmark=...)` 且基准文件读到了才有；否则返回空 dict，
        metrics 里就不出现这些键（调用方按缺字段处理，别造假数据）。

        回归本身交给 `Analysis.alpha_beta` —— 口径只有一处，不在这里重写公式。
        """
        bench = getattr(self, '_benchmark_returns', None)
        if bench is None or len(bench) < 2:
            return {}

        rp = daily_returns.copy()
        rp.index = [str(i)[:10] for i in rp.index]
        rp = rp[rp.index.isin(bench.index)]
        if len(rp) < 20:                     # 样本太短，回归没有意义
            return {}

        from qka.core.analysis import Analysis

        x = bench.loc[rp.index].astype(float)
        y = rp.astype(float)

        ab = Analysis().alpha_beta(y.values, x.values, rf=self.risk_free_rate)
        out = {
            'benchmark_return_pct': float((1 + x).prod() - 1) * 100,
            'alpha_pct': float(ab.alpha) * 100,
            'beta': float(ab.beta),
            'benchmark_n_days': int(len(x)),
        }
        try:
            out['information_ratio'] = float(
                Analysis().information_ratio(y.values, x.values))
        except Exception:                     # 跟踪误差为 0 时会算不出来，不致命
            pass
        return out

    def report(self, title: str = "未命名策略", output_path: Optional[str] = None) -> str:
        """
        生成自包含的 HTML 回测报告

        包含绩效指标卡片、净值曲线、回撤曲线、月度收益率热力图、
        交易明细表和回撤分析。可直接在浏览器中打开。

        Args:
            title: 策略名称（显示在报告标题中）
            output_path: 输出 HTML 文件路径。
                         None 则自动保存在 reports/ 目录下

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
