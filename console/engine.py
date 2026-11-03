"""
QKA 控制台核心执行引擎 (Engine)
提供数据拉取、指标计算、策略预置模板、回测调度与模拟标的生成服务。
"""

import os
import sys
import math
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# 尝试导入 qka 核心模块
HAS_QKA = False
try:
    import pandas as pd
    import numpy as np
    from qka import Data, Simulate, Strategy, Backtest, Analysis
    HAS_QKA = True
except Exception as e:
    HAS_QKA = False


# 预置经典量化策略库
PRESET_STRATEGIES = {
    "ma_cross": {
        "id": "ma_cross",
        "name": "双均线动量择时策略",
        "description": "经典趋势跟踪策略。5日快线金叉20日慢线买入，死叉卖出平仓，支持按可用资金比例建仓。",
        "symbols": ["000001.SZ"],
        "benchmark": "000300.SH",
        "cash": 200000.0,
        "factors": {
            "sma_5": "('ta.trend.sma_indicator', 'close', 5)",
            "sma_20": "('ta.trend.sma_indicator', 'close', 20)"
        },
        "warmup": 20,
        "code": '''from qka import Strategy

class MaCross(Strategy):
    def __init__(self):
        super().__init__()
        self.pct = 0.25  # 每次调仓动用 25% 资金

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
'''
    },
    "bollinger_atr": {
        "id": "bollinger_atr",
        "name": "布林带突破 + ATR 风险平价",
        "description": "通道突破策略。突破布林带上轨开仓，使用海龟 ATR 风险平价控制仓位，跌破中轨移动止损。",
        "symbols": ["510300.SH"],
        "benchmark": "000300.SH",
        "cash": 300000.0,
        "factors": {
            "boll_h": "('ta.volatility.bollinger_hband', 'close', 20, 2.0)",
            "boll_m": "('ta.volatility.bollinger_mavg', 'close', 20)",
            "atr_14": "('ta.volatility.average_true_range', 'high', 'low', 'close', 14)"
        },
        "warmup": 20,
        "code": '''from qka import Strategy

class BollingerAtrStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.risk_ratio = 0.015  # 单笔最大风险暴露 1.5%

    def on_bar(self, date):
        close = self.get('close')
        upper = self.get('boll_h')
        mid = self.get('boll_m')
        atr = self.get('atr_14')

        for sym in close.index:
            price = float(close[sym])
            if price <= 0:
                continue

            pos = self.broker.positions.get(sym, {}).get('size', 0)

            # 突破上轨买入
            if price > upper[sym] and pos == 0:
                atr_val = float(atr[sym])
                if atr_val > 0:
                    size = self.sizing.atr_risk(self.risk_ratio, price, atr_val, multiplier=2.0)
                    if size > 0:
                        self.broker.buy(sym, price, size)
            # 跌破中轨止损或止盈
            elif price < mid[sym] and pos > 0:
                self.broker.sell(sym, price, pos)
'''
    },
    "momentum_rotation": {
        "id": "momentum_rotation",
        "name": "多标的横截面动量轮动",
        "description": "横截面动量排序策略。在候选股票池中按过去20日累计收益率排序，全仓轮动持有动量最强标的。",
        "symbols": ["000001.SZ", "600000.SH", "600519.SH", "510300.SH"],
        "benchmark": "000300.SH",
        "cash": 500000.0,
        "factors": {
            "sma_20": "('ta.trend.sma_indicator', 'close', 20)"
        },
        "warmup": 25,
        "code": '''from qka import Strategy

class MomentumRotation(Strategy):
    def __init__(self):
        super().__init__()
        self.lookback = 20
        self.top_k = 2  # 持仓最强的 2 只

    def on_bar(self, date):
        close = self.get('close')
        hist_returns = self.history('returns', window=self.lookback)

        if hist_returns.empty:
            return

        # 1. 计算过去 20 天动量并排序
        cum_ret = (1 + hist_returns).prod() - 1
        sorted_symbols = cum_ret.sort_values(ascending=False).index.tolist()
        targets = sorted_symbols[:self.top_k]

        # 2. 检查持仓：不在候选集里的先卖出
        for sym, pos in list(self.broker.positions.items()):
            if sym not in targets and pos['size'] > 0:
                price = float(close[sym])
                if price > 0:
                    self.broker.sell(sym, price, pos['size'])

        # 3. 买入新入围的标的
        if targets:
            target_pct = 1.0 / len(targets)
            for sym in targets:
                if sym not in self.broker.positions or self.broker.positions[sym]['size'] == 0:
                    price = float(close[sym])
                    if price > 0:
                        size = self.sizing.percent(target_pct, price)
                        if size > 0:
                            self.broker.buy(sym, price, size)
'''
    },
    "rsi_reversion": {
        "id": "rsi_reversion",
        "name": "RSI 超买超卖均值回归",
        "description": "经典摆动反转策略。RSI 低于 30 超卖区间分批建仓，RSI 超过 70 超买区间果断减仓离场。",
        "symbols": ["159915.SZ"],
        "benchmark": "399006.SZ",
        "cash": 200000.0,
        "factors": {
            "rsi_14": "('ta.momentum.rsi', 'close', 14)"
        },
        "warmup": 15,
        "code": '''from qka import Strategy

class RsiReversion(Strategy):
    def __init__(self):
        super().__init__()
        self.oversold = 30.0
        self.overbought = 70.0

    def on_bar(self, date):
        close = self.get('close')
        rsi = self.get('rsi_14')

        for sym in close.index:
            price = float(close[sym])
            if price <= 0:
                continue

            val = float(rsi[sym])
            pos = self.broker.positions.get(sym, {}).get('size', 0)

            # 超卖买入
            if val < self.oversold and pos == 0:
                size = self.sizing.percent(0.3, price)
                if size > 0:
                    self.broker.buy(sym, price, size)
            # 超买清仓
            elif val > self.overbought and pos > 0:
                self.broker.sell(sym, price, pos)
'''
    }
}


def get_system_info() -> Dict[str, Any]:
    """获取系统运行环境、依赖状态与缓存指标"""
    user_home = Path.home()
    qka_cache_dir = user_home / ".qka"
    if not qka_cache_dir.exists():
        qka_cache_dir = Path("./datadir").resolve()

    cache_size_bytes = 0
    cache_files_count = 0
    if qka_cache_dir.exists():
        for f in qka_cache_dir.rglob("*"):
            if f.is_file():
                cache_files_count += 1
                try:
                    cache_size_bytes += f.stat().st_size
                except Exception:
                    pass

    return {
        "python_version": sys.version.split()[0],
        "qka_version": "0.1.0",
        "has_qka_core": HAS_QKA,
        "os_platform": sys.platform,
        "cache_dir": str(qka_cache_dir),
        "cache_files_count": cache_files_count,
        "cache_size_mb": round(cache_size_bytes / (1024 * 1024), 2),
        "supported_sources": [
            {"id": "tickflow", "name": "Tickflow (默认免密 / 全量ETF & 转债)", "default": True},
            {"id": "baostock", "name": "Baostock (含财务估值/换手率)", "default": False},
            {"id": "tdx", "name": "通达信本地源 (Windows TQ客户端)", "default": False}
        ],
        "supported_adjust": [
            {"id": "qfq", "name": "前复权 (qfq, 回测推荐)", "default": True},
            {"id": "hfq", "name": "后复权 (hfq)", "default": False},
            {"id": "bfq", "name": "不复权 (bfq)", "default": False}
        ]
    }


def generate_simulation_data(
    symbol: str = "SIM.A",
    drift: float = 0.0005,
    reversion: float = 0.05,
    vol: float = 0.015,
    start_price: float = 100.0,
    days: int = 250,
    start_date: str = "2024-01-01"
) -> Dict[str, Any]:
    """生成带有漂移与均值回复特性的模拟行情数据"""
    dates = []
    kline = []  # [open, close, low, high]
    volumes = []
    prices = []

    dt = datetime.strptime(start_date, "%Y-%m-%d")
    current_log_price = math.log(start_price)
    anchor_log_price = current_log_price

    random.seed(42)

    for i in range(days):
        # 跳过周末
        while dt.weekday() >= 5:
            dt += timedelta(days=1)

        dates.append(dt.strftime("%Y-%m-%d"))

        # Ornstein-Uhlenbeck 模拟增量
        eps = random.gauss(0, 1)
        r_t = drift + reversion * (anchor_log_price - current_log_price) + vol * eps
        prev_price = math.exp(current_log_price)
        current_log_price += r_t
        curr_price = math.exp(current_log_price)

        # 构造高开低收
        o = prev_price * (1 + random.gauss(0, vol * 0.3))
        c = curr_price
        high_val = max(o, c) * (1 + abs(random.gauss(0, vol * 0.5)))
        low_val = min(o, c) * (1 - abs(random.gauss(0, vol * 0.5)))
        v = int(random.uniform(50000, 250000) * (1 + abs(r_t) * 10))

        prices.append(round(c, 2))
        kline.append([round(o, 2), round(c, 2), round(low_val, 2), round(high_val, 2)])
        volumes.append(v)

        dt += timedelta(days=1)

    # 简单计算 SMA5 和 SMA20
    sma5 = []
    sma20 = []
    for idx in range(len(prices)):
        if idx >= 4:
            sma5.append(round(sum(prices[idx-4:idx+1]) / 5, 2))
        else:
            sma5.append(None)
        if idx >= 19:
            sma20.append(round(sum(prices[idx-19:idx+1]) / 20, 2))
        else:
            sma20.append(None)

    return {
        "symbol": symbol,
        "dates": dates,
        "kline": kline,
        "volumes": volumes,
        "sma5": sma5,
        "sma20": sma20,
        "params": {
            "drift": drift,
            "reversion": reversion,
            "vol": vol,
            "days": days
        }
    }


def fetch_market_data(
    symbol: str = "000001.SZ",
    source: str = "tickflow",
    adjust: str = "qfq",
    start_date: str = "2023-01-01",
    end_date: str = "2024-12-31"
) -> Dict[str, Any]:
    """获取标的真实或仿真行情数据并格式化为 K 线"""
    if HAS_QKA:
        try:
            data = Data(
                symbols=[symbol],
                source=source,
                adjust=adjust,
                factors={
                    'sma_5': ('ta.trend.sma_indicator', 'close', 5),
                    'sma_20': ('ta.trend.sma_indicator', 'close', 20),
                    'rsi_14': ('ta.momentum.rsi', 'close', 14),
                },
                warmup=20
            )
            df = data.get(start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                dates = [d.strftime("%Y-%m-%d") for d in df.index]
                kline = []
                volumes = []
                sma5 = []
                sma20 = []
                rsi14 = []

                c_col = f"{symbol}|close"
                o_col = f"{symbol}|open"
                l_col = f"{symbol}|low"
                h_col = f"{symbol}|high"
                v_col = f"{symbol}|volume"
                s5_col = f"{symbol}|sma_5"
                s20_col = f"{symbol}|sma_20"
                r_col = f"{symbol}|rsi_14"

                for _, row in df.iterrows():
                    o = round(float(row.get(o_col, 0)), 2)
                    c = round(float(row.get(c_col, 0)), 2)
                    l = round(float(row.get(l_col, 0)), 2)
                    h = round(float(row.get(h_col, 0)), 2)
                    v = int(row.get(v_col, 0))
                    kline.append([o, c, l, h])
                    volumes.append(v)
                    sma5.append(round(float(row[s5_col]), 2) if s5_col in row and not pd.isna(row[s5_col]) else None)
                    sma20.append(round(float(row[s20_col]), 2) if s20_col in row and not pd.isna(row[s20_col]) else None)
                    rsi14.append(round(float(row[r_col]), 2) if r_col in row and not pd.isna(row[r_col]) else None)

                return {
                    "symbol": symbol,
                    "source": source,
                    "adjust": adjust,
                    "dates": dates,
                    "kline": kline,
                    "volumes": volumes,
                    "sma5": sma5,
                    "sma20": sma20,
                    "rsi14": rsi14,
                    "total_bars": len(dates)
                }
        except Exception as e:
            # 数据获取异常时回退到模拟数据
            pass

    # 无环境或回退模拟数据
    sim = generate_simulation_data(
        symbol=symbol,
        drift=0.0003,
        reversion=0.03,
        vol=0.014,
        start_price=12.5,
        days=260,
        start_date=start_date
    )
    sim["source"] = f"{source} (演示模式)"
    sim["adjust"] = adjust
    sim["total_bars"] = len(sim["dates"])
    return sim


def execute_backtest(
    strategy_code: str,
    symbols: List[str],
    cash: float = 200000.0,
    start_date: str = "2023-01-01",
    end_date: str = "2024-12-31",
    benchmark: str = "000300.SH",
    warmup: int = 20,
    factors_dict: Optional[Dict] = None
) -> Dict[str, Any]:
    """运行策略回测并提取完整的净值曲线、回撤曲线和绩效度量"""
    if HAS_QKA:
        try:
            # 1. 动态编译执行用户策略代码
            strategy_namespace = {}
            exec(strategy_code, strategy_namespace)

            # 寻找继承自 Strategy 的策略类
            target_cls = None
            for name, obj in strategy_namespace.items():
                if isinstance(obj, type) and issubclass(obj, Strategy) and obj is not Strategy:
                    target_cls = obj
                    break

            if target_cls is None:
                raise ValueError("未在提交的代码中找到继承自 qka.Strategy 的策略类！")

            # 2. 构造 Data
            factors = {
                'sma_5': ('ta.trend.sma_indicator', 'close', 5),
                'sma_20': ('ta.trend.sma_indicator', 'close', 20),
            }
            if factors_dict:
                for k, v in factors_dict.items():
                    if isinstance(v, str) and v.startswith("("):
                        factors[k] = eval(v)
                    else:
                        factors[k] = v

            data = Data(
                symbols=symbols,
                benchmark=benchmark,
                factors=factors,
                warmup=warmup
            )

            # 3. 运行 Backtest
            strat_instance = target_cls()
            bt = Backtest(data, strat_instance)
            bt.run(cash=cash, start_date=start_date, end_date=end_date, benchmark=benchmark)

            # 4. 提取结果
            dates = [d.strftime("%Y-%m-%d") for d in bt.results.index]
            total_equity = [round(float(v), 2) for v in bt.results['total']]
            cash_series = [round(float(c), 2) for c in bt.results['cash']]
            pos_series = [round(float(p), 2) for p in bt.results['value']]

            # 计算基准曲线
            bench_curve = []
            if f"benchmark|returns" in data.get().columns:
                bench_ret = data.get()['benchmark|returns'].loc[bt.results.index].fillna(0)
                cum_bench = (1 + bench_ret).cumprod() * cash
                bench_curve = [round(float(b), 2) for b in cum_bench]
            else:
                # 简单基准模拟
                bench_curve = [round(cash * (1 + 0.0001 * i), 2) for i in range(len(dates))]

            # 计算回撤曲线
            peak = total_equity[0]
            drawdown = []
            for eq in total_equity:
                if eq > peak:
                    peak = eq
                dd = (eq - peak) / peak if peak > 0 else 0
                drawdown.append(round(dd * 100, 2))

            # 生成报告
            report_path = bt.report(title=f"QKA 策略回测报告 ({', '.join(symbols)})")

            return {
                "success": True,
                "metrics": bt.metrics,
                "dates": dates,
                "equity": total_equity,
                "cash": cash_series,
                "positions_value": pos_series,
                "benchmark_equity": bench_curve,
                "drawdown": drawdown,
                "trade_history": bt.trade_history[-100:],  # 最多返回最近 100 笔
                "total_trades": len(bt.trade_history),
                "report_file": report_path
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    # 演示仿真回测（环境缺失时保证 UI 功能完整可体验）
    dates = []
    equity = []
    benchmark_equity = []
    drawdown = []
    trade_history = []

    dt = datetime.strptime(start_date, "%Y-%m-%d")
    curr_cash = cash
    curr_equity = cash
    bench_eq = cash
    peak = cash

    random.seed(int(cash) % 1000)

    for i in range(240):
        while dt.weekday() >= 5:
            dt += timedelta(days=1)
        d_str = dt.strftime("%Y-%m-%d")
        dates.append(d_str)

        # 模拟策略收益与基准波动
        daily_strat = random.gauss(0.0008, 0.012)
        daily_bench = random.gauss(0.0002, 0.011)

        curr_equity *= (1 + daily_strat)
        bench_eq *= (1 + daily_bench)

        if curr_equity > peak:
            peak = curr_equity
        dd = (curr_equity - peak) / peak * 100

        equity.append(round(curr_equity, 2))
        benchmark_equity.append(round(bench_eq, 2))
        drawdown.append(round(dd, 2))

        # 偶发生成买卖
        if random.random() < 0.12 and i > 5:
            action = "buy" if random.random() > 0.4 else "sell"
            sym = symbols[0] if symbols else "000001.SZ"
            price = round(random.uniform(9.0, 15.0), 2)
            trade_history.append({
                "action": action,
                "symbol": sym,
                "price": price,
                "exec_price": round(price * 1.001, 2) if action == "buy" else round(price * 0.999, 2),
                "size": random.randint(1, 10) * 100,
                "amount": round(price * 300, 2),
                "commission": 5.0,
                "timestamp": d_str
            })

        dt += timedelta(days=1)

    total_ret = (curr_equity / cash - 1) * 100
    ann_ret = ((curr_equity / cash) ** (252 / len(dates)) - 1) * 100

    return {
        "success": True,
        "is_mock": True,
        "metrics": {
            "initial_cash": cash,
            "final_equity": round(curr_equity, 2),
            "total_return_pct": round(total_ret, 2),
            "annual_return_pct": round(ann_ret, 2),
            "annual_volatility_pct": 18.25,
            "sharpe_ratio": round(ann_ret / 18.25, 2),
            "max_drawdown_pct": round(abs(min(drawdown)), 2),
            "calmar_ratio": round(ann_ret / (abs(min(drawdown)) + 1e-4), 2),
            "win_rate_pct": 58.33,
            "profit_loss_ratio": 1.75,
            "total_trades": len(trade_history),
            "total_commission": round(len(trade_history) * 6.5, 2),
            "n_days": len(dates)
        },
        "dates": dates,
        "equity": equity,
        "cash": [round(cash * 0.3, 2)] * len(dates),
        "positions_value": [round(eq * 0.7, 2) for eq in equity],
        "benchmark_equity": benchmark_equity,
        "drawdown": drawdown,
        "trade_history": trade_history,
        "total_trades": len(trade_history),
        "report_file": ""
    }
