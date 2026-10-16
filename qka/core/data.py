"""
QKA数据模块

提供统一的数据获取、缓存和管理功能，支持多数据源、多周期、多因子的数据获取。
"""

import contextlib
import hashlib
import inspect
import io
import json
import os
import textwrap
import threading
from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import baostock as bs
import dask.dataframe as dd
from typing import List, Optional, Callable, Union
from qka.utils.logger import logger
from qka.core import indicator
from qka.core.simulate import Simulate
from qka.core import tdx

# qka 内置指标裸名集合，用于 dispatch 识别（无需 qka. 前缀）
_QKA_BUILTIN_NAMES = frozenset({
    'alpha', 'beta', 'sharpe', 'max_drawdown',
    'information_ratio', 'rolling_zigzag',
})


def _is_qka_factor(ind_type):
    """判断指标类型是否为 qka 内置指标（支持 qka. 前缀或裸名）。"""
    return (isinstance(ind_type, str) and
            (ind_type.startswith('qka.') or ind_type in _QKA_BUILTIN_NAMES))


def _callable_source(fn):
    """取可调用对象的源码文本，用于算配方指纹；取不到返回 None（表示不缓存）。"""
    try:
        return textwrap.dedent(inspect.getsource(fn))
    except (OSError, TypeError):
        return None


# ── TickFlow 凭据（进程级，设一次即可）──────────────────────────
# 放在模块级而不是 `Data` 参数里：「用哪个凭据」是部署级配置，不该每构造一次
# Data 就传一遍。优先级：set_tickflow_api_key() > 环境变量 > 免费档。
_TICKFLOW_API_KEY: Optional[str] = None


def set_tickflow_api_key(api_key: Optional[str]) -> None:
    """设置 TickFlow API key（进程级，设一次即可）。

    设了之后所有 `Data(source='tickflow')` 都走完整服务
    （https://api.tickflow.org）；不设则走免费档
    （https://free-api.tickflow.org），与既有行为完全一致。

    优先级：本函数设的值 > 环境变量 ``TICKFLOW_API_KEY`` > 免费档。

    Args:
        api_key: 密钥；传 None 或空串表示清除，回到免费档。

    Examples:
        >>> from qka import Data, set_tickflow_api_key
        >>> set_tickflow_api_key('tk_xxx')
        >>> Data(symbols=['600519.SH']).get()      # 已走完整服务
    """
    global _TICKFLOW_API_KEY
    _TICKFLOW_API_KEY = api_key or None
    # 已经建好的客户端按旧 key 建的，作废掉 —— 否则「先建了免费档客户端、
    # 后设 key」这条时间线会静默继续走免费档，既看不出来又难查。
    Data._reset_tickflow_clients()


def get_tickflow_api_key() -> Optional[str]:
    """当前生效的 TickFlow key：函数设的优先，其次环境变量，都没有则 None。"""
    return _TICKFLOW_API_KEY or os.environ.get('TICKFLOW_API_KEY') or None


def _key_fingerprint(api_key: Optional[str]) -> str:
    """key 的短摘要，用作客户端缓存的键。

    不拿明文 key 当字典键 —— 免得它出现在内存转储或日志里。
    """
    if not api_key:
        return ''
    return hashlib.sha1(api_key.encode('utf-8')).hexdigest()[:12]


# 当日日线数据「可能已经生成」的时刻（本地时间）。一天以它为界切成前后两个时段：
# 17:00 之前，数据源手里最新的一根还是上一交易日，当天这根根本还没生成；
# 17:00 之后，当天的已经出完了，要补也就这一次。
DATA_READY_HOUR = 17


def _data_period(ts) -> tuple:
    """把时刻归入「数据时段」——（日期，是否已过当日数据生成时刻）。

    同一个时段内数据源不会多出任何东西，对同一只标的重复询问纯属白跑一趟。
    休市日、节假日尤其明显：日历上没有交易日，缓存永远「缺今天」，若不记时段
    就会每次请求都去问一遍，永远问不到结果。
    """
    return (ts.date(), ts.hour >= DATA_READY_HOUR)


class Data():
    """
    数据管理类
    
    负责股票数据的获取、缓存和管理，支持多数据源、并发下载和自定义因子计算。
    通过 `factors` 参数统一处理技术指标和自定义因子，在数据加载时一次性预计算。
    （`indicators` 是同义旧名，两者完全等价、可互换，保留向后兼容。）

    Attributes:
        symbols (List[str]): 股票代码列表，格式「代码.市场」，如 ['600519.SH', '000001.SZ']
            （也兼容 sh.600519 旧写法，两种写法等价）
        period (str): 数据周期，如 '1d'、'1m' 等
        adjust (str): 复权方式，如 'qfq'、'hfq'、'bfq'
        factors (dict | Callable): 预计算指标/因子（旧名 `indicators` 等价）
        source (str): 数据源，默认 'tickflow'（可选 'baostock'、'tdx'）
        pool_size (int): 并发下载线程数
        datadir (Path): 数据缓存目录
        target_dir (Path): 目标存储目录
        extra_fields (List[str]): 扩展字段（选股/估值用），如 ['peTTM', 'pbMRQ', 'turn']。
            仅 'baostock' 源提供（可选值见 BAOSTOCK_EXTRA_FIELDS）；'tickflow' 与
            'tdx' 源无扩展列，会忽略
    """
    
    # 支持的行情源
    SOURCES = ('tickflow', 'baostock', 'tdx')

    # 允许「增量缓存」的复权方式。前复权（qfq）**不在其中**。
    # 原因：前复权是「以最新价为锚」，今后的分红送股会往回改写整段历史 ——
    # 缓存若只往后补新棒，文件里就会拼出「前段旧口径 + 后段新口径」的缝，
    # 缝上凭空多出一根假 K 线（实测 000001.SZ 一次分红让整段等比缩 5.57%，
    # 拼接处算出 -4.84%，真实是 +0.91%）。故前复权一律整段重取覆盖，
    # 保证文件里永远只有一种口径。不复权 / 后复权的历史不会被改写，可以放心增量。
    INCREMENTAL_ADJUSTS = ('bfq', 'hfq')

    # baostock query_history_k_data_plus 完整支持的基础字段（除 date 索引外）
    BAOSTOCK_BASE_FIELDS = ["open", "high", "low", "close", "volume", "amount"]
    # 可通过 extra_fields 追加的扩展字段白名单（行情/估值/选股类）
    BAOSTOCK_EXTRA_FIELDS = [
        "preclose",    # 前收盘价
        "turn",        # 换手率(%)
        "tradestatus", # 交易状态(1=正常, 0=停牌)
        "pctChg",      # 涨跌幅(%)
        "isST",        # 是否 ST(1=是, 0=否)
        "peTTM",       # 市盈率(TTM)
        "pbMRQ",       # 市净率(MRQ)
        "psTTM",       # 市销率(TTM)
        "pcfNcfTTM",   # 市现率(TTM)
    ]
    # TickFlow 可提供的扩展字段：其历史日线固定返回 OHLCV + amount，
    # 无估值/换手率等扩展列（季报级 financials 不是每日序列，不接入）。
    TICKFLOW_EXTRA_FIELDS = []
    # 通达信源当前只接行情（OHLCV + amount），暂无扩展列
    TDX_EXTRA_FIELDS = []

    # parquet 元数据键：这只标的「已确认起点」——数据源在该日期之前没有更早的数据。
    # 没有它，请求起点只要早于缓存首日（往往只是撞上长假）就得白跑一趟网络去确认。
    VERIFIED_FROM_KEY = b'qka_verified_from'

    # ── 模拟数据源默认值 ──
    SIM_START = '2020-01-02'    # 模拟行情默认起点（调用方未给 start_date 时使用）
    SIM_START_PRICE = 20.0      # 起始价
    SIM_LIMIT = 0.10            # 单日涨跌幅截断（模拟涨跌停）
    SIM_FUND_PHI = 0.97         # 基本面扰动的持续性（半衰期 ≈ 23 个交易日）
    # 估值列参数：field -> (基准值, 对价格的对数弹性, 基本面自身对数波动(稳态 std))
    # 弹性 = 估值随价格等比变动的比例。弹性≈1 ⇒ 估值是价格的复刻（错）；
    # 弹性小甚至为负 ⇒ 盈利同步增长抵消了价格，估值走出自己的路（对）。
    # 目标量级参照真实缓存实测：corr(peTTM,close)≈-0.09 / pbMRQ≈+0.78 /
    # psTTM≈-0.59 / pcfNcfTTM≈-0.59。
    SIM_EXTRA_BASE = {
        'peTTM':     (15.0, +0.05, 0.130),
        'pbMRQ':     (1.8,  +0.40, 0.070),
        'psTTM':     (2.2,  -0.30, 0.120),
        'pcfNcfTTM': (12.0, -0.80, 0.300),
    }

    def __init__(
        self, 
        symbols: Optional[List[Union[str, Simulate]]] = None,
        benchmark: Optional[str] = None,
        period: str = '1d',
        adjust: str = 'qfq',
        source: str = 'tickflow',
        pool_size: int = 10,
        datadir: Optional[Path] = None,
        factors: Optional[dict] = None,
        indicators: Optional[dict] = None,
        extra_fields: Optional[List[str]] = None,
        warmup: int = 0,
        drop_head: int = 0,
        factor_cache: bool = False,
        fill_suspended: bool = False,
    ):
        """
        初始化数据对象

        Args:
            symbols: 标的列表，元素**可以是真实代码字符串，也可以是 Simulate 对象**。
                真实代码用「代码.市场」格式，如 ['600519.SH', '000001.SZ']（同样兼容
                sh.600519 旧写法）；Simulate 对象
                表示一只由 qka 现场生成的模拟标的，两者可以混排。写法完全同构，区别只在
                元素本身：

                ```python
                Data(symbols=[
                    '600900.SH',
                    Simulate('sim.a', drift=0.0, reversion=0.08, vol=0.018),
                ])
                ```

                模拟标的同样支持 `factors` / `extra_fields` / `warmup`，行为与真实源
                一致（列名同样是 {symbol}|{field}，扩展列同样是「不请求就不生成」）。
                模拟标的的行情区间由 get(start_date, end_date) 决定 —— 用 baostock 的
                交易日历把区间内的真实交易日取出来，一 日一根，与真实源同构。
            benchmark: 基准代码，如 '000300.SH'。基准数据以 benchmark| 前缀加入最终 DataFrame，
                       仅供辅助计算（β/α 等），不参与指标计算
            period: 数据周期，如 '1d'（日线）、'1m'（分钟）
            adjust: 复权方式，'qfq'（前复权）、'hfq'（后复权）、'bfq'（不复权）。
                注意缓存口径：前复权的历史会被今后的分红送股改写，故它**不做增量缓存**
                —— 需要问数据源时整段重取覆盖，保证缓存文件里只有一种口径；
                不复权 / 后复权的历史不会被改写，走增量缓存（只补缺口）。详见 INCREMENTAL_ADJUSTS
            source: 数据来源，默认 'tickflow'（可选 'baostock'、'tdx'）。各源返回结构一致，
                切换源不影响上层调用；差异见各源的扩展字段能力。'tdx' 走本机安装的
                「支持 TQ 策略」通达信客户端（仅 Windows，需客户端在运行），安装目录的定位
                方式见 `qka.set_tdx_root` / `qka.get_tdx_root_info`
            pool_size: 并发下载线程数
            datadir: 缓存目录路径
            factors: 预计算指标/因子（**推荐写法**）。支持两种写法（dict / callable；不传即不算）：

                **1. 字典（混搭 ta 函数和自定义因子）：**
                ```python
                {
                    'sma_5':  ('ta.trend.sma_indicator', 'close', 5),
                    'rsi_14': ('ta.momentum.rsi', 'close', 14),
                    'macd':   ('ta.trend.macd_diff', 'close', 26, 12, 9),
                    'atr_14': ('ta.volatility.average_true_range', 'high', 'low', 'close', 14),
                    'ma5':    lambda df: df['close'].rolling(5).mean(),
                }
                ```
                每个条目独立产一列，直接透传 ta 库全部指标。
                列名参数（'close'/'high' 等）放在 ta 路径之后、数值参数之前；
                多列函数（如 ATR）连续列出所有列名即可。

                **2. 函数（自定义因子）：**
                ```python
                factors=lambda df: df.assign(ma5=df['close'].rolling(5).mean())
                ```
                函数接收单只股票的 DataFrame，返回添加了额外列的 DataFrame。

            indicators: `factors` 的同义旧名，行为完全一致、保留向后兼容；两者同时传会报错。

            extra_fields: 扩展字段列表（选股/估值用，如 ['peTTM', 'pbMRQ', 'turn']），
                可选值见 BAOSTOCK_EXTRA_FIELDS —— 仅 'baostock' 源提供；
                'tickflow' 与 'tdx' 源无扩展列，传入的扩展字段会被静默忽略
                （不报错、不生成该列）。
                追加的列同样遵循 {symbol}|{field} 命名，如 '600519.SH|peTTM'。注意：
                首次下载后缓存字段固定，变更 extra_fields 会自动检测列缺失并重新下载对应股票。

            warmup: 因子预热天数（默认 0）。回测/取数时自动多读取 warmup 个交易日的历史数据
                用于计算因子，使第 1 个交易日即可拿到有效值，无需在策略里手写
                `if len(hist) < N: continue` 跳过前 N 根 bar。仅用于计算，不会增加 on_bar 调用次数。

            drop_head: 掐头根数（默认 0，即不掐）。取回数据的**每条序列**（含基准）
                的前 drop_head 根，`returns` 一律记空 —— 这些根只当"垫场"，不参与
                任何因子的滚动窗口。为什么需要：次新股的头一两根 K 线是「发行价跳到
                上市价」，那笔涨幅不是市场交易出来的（见过一天"涨 349%"的假数据），
                掐掉之后，窗口自动需要 drop_head 根额外的真实样本 —— 上市不足
                「窗口 + drop_head」根的票，因子整条留空，不会拿脏数据凑数。
                与 warmup 的分工：warmup 管「往前多取多少料」，drop_head 管
                「取回来的料开头多少根不许用」。两者互不替代，可同时使用。

            factor_cache: 是否把算出来的因子**纵向落盘**（默认 False，即不缓存）。
                开启后，因子按 `datadir/factors/{因子名}/{symbol}.parquet` 存，
                命中就直接读、只缺尾巴就只补尾巴；配方或数据口径变了则整条重算。
                详见 `skills/qka/references/data.md` 的「因子缓存」。
                只作用于默认（`lazy=False`）路径。

            fill_suspended: 是否把**停牌日按前收补齐**（默认 False）。
                各标的只在自己的交易日有 K 线，对齐到同一张宽表后停牌日就是空缺；
                滚动类因子（α/β/波动率……）默认要求窗口内一天都不能缺，**停过一天牌
                就会整条算不出来**。开启后：价格四列取前一交易日的值（当天收益率
                变成 0），`returns` 按补齐后的 close 重算；**上市前的空缺仍然留空**。
                只作用于默认（`lazy=False`）路径。

        """
        # ── 归一化 symbols：str = 真实标的，Simulate 对象 = 模拟标的，可混排 ──
        names, sim_specs = [], {}
        for item in (symbols or []):
            if isinstance(item, Simulate):
                name = item.symbol
                sim_specs[name] = item
            elif isinstance(item, str):
                name = item
            else:
                raise TypeError(
                    f"symbols 的元素必须是 str 或 Simulate，got {type(item)}: {item!r}"
                )
            if name in names:
                raise ValueError(f"symbols 中存在重复标的: {name}")
            names.append(name)

        self.symbols = names                                    # 全部标的（保持入参顺序）
        self._sim_specs = sim_specs                             # {代码: Simulate}
        self._real_symbols = [n for n in names if n not in sim_specs]
        self.benchmark = benchmark
        self.period = period
        self.adjust = adjust
        # 该复权方式是否允许增量缓存（前复权不允许，见 INCREMENTAL_ADJUSTS）
        self.incremental = adjust in self.INCREMENTAL_ADJUSTS
        if source not in self.SOURCES:
            raise ValueError(f"不支持的数据源: {source!r}。可选: {self.SOURCES}")
        self.source = source
        self.pool_size = pool_size
        self.warmup = warmup
        # 掐头根数：取回数据的每条序列开头 N 根，returns 记空（见 __init__ 文档）。
        # 必须在停牌补齐**之后**生效 —— 补齐会重算 returns，先掐会被洗回来。
        self.drop_head = int(drop_head)
        # 因子缓存：默认关。要用得显式开（见 _factors_with_cache）
        self.factor_cache = bool(factor_cache)
        # 停牌日按前收填充：默认关。见 _fill_suspended_prices
        self.fill_suspended = bool(fill_suspended)

        # 当前数据源实际支持的扩展字段（源能力不同，按源过滤）
        whitelist = self._extra_fields_whitelist(source)

        # extra_fields 校验 + 去重
        # 未知字段（拼写错误）报错；当前源提供不了的字段静默忽略
        # （如 tickflow 无估值列，调用方仍传 peTTM 时不报错、只是不生成该列）
        self.extra_fields = []              # 当前源实际会下载的扩展字段
        self._requested_extra_fields = []   # 调用方原始请求（不按源过滤，模拟标的按此生成）
        for f in (extra_fields or []):
            if f not in self.BAOSTOCK_EXTRA_FIELDS:
                raise ValueError(
                    f"extra_fields 含不支持的字段: {f}。"
                    f"可选: {self.BAOSTOCK_EXTRA_FIELDS}"
                )
            if f not in self._requested_extra_fields:
                self._requested_extra_fields.append(f)
            if f not in whitelist:
                continue
            if f not in self.extra_fields:
                self.extra_fields.append(f)

        # 统一处理 factors / indicators 参数（同一个东西的两个名字，等价）
        if factors is not None and indicators is not None:
            raise TypeError(
                "factors 与 indicators 是同一个参数的新旧两个名字，"
                "等价且只能传一个，请只传 factors"
            )
        specs = factors if factors is not None else indicators
        if callable(specs):
            # 函数形式 → 保存为 callable
            self._factors = specs
        elif isinstance(specs, dict):
            # 字典形式
            self._factors = specs
        elif specs is None:
            self._factors = {}
        else:
            raise TypeError(
                f"factors 必须是 dict、callable 或 None，got {type(specs)}"
            )

        # 初始化缓存目录
        if datadir is None:
            # 默认使用当前工作目录下的 datadir
            self.datadir = Path.cwd() / "datadir"
        else:
            self.datadir = Path(datadir)
        
        # 只有真实标的才需要缓存目录；纯模拟标的（_real_symbols 为空）不落盘
        if self._real_symbols:
            self.datadir.mkdir(parents=True, exist_ok=True)

        self.target_dir = self.datadir / self.source / self.period / (self.adjust or "bfq")
        if self._real_symbols:
            self.target_dir.mkdir(parents=True, exist_ok=True)

    def _trading_index(self, start_date: str, end_date: str) -> pd.DatetimeIndex:
        """
        取 [start_date, end_date] 内的真实交易日，作为模拟行情的日期轴。

        数据来自 baostock 的交易日历接口 query_trade_dates，故调用方需已登录。

        Args:
            start_date / end_date: 'YYYY-MM-DD'

        Returns:
            pd.DatetimeIndex，名称 'date'（与真实缓存 parquet 的索引名一致）

        Raises:
            RuntimeError: baostock 查询失败，或区间内一个交易日都没有
        """
        rs = bs.query_trade_dates(start_date=start_date, end_date=end_date)
        if rs.error_code != '0':
            raise RuntimeError(
                f"获取交易日历失败（{start_date} ~ {end_date}）: "
                f"[{rs.error_code}] {rs.error_msg}"
            )
        dates = []
        while rs.next():
            calendar_date, is_trading_day = rs.get_row_data()
            if is_trading_day == '1':
                dates.append(calendar_date)
        if not dates:
            raise RuntimeError(
                f"区间内没有交易日: {start_date} ~ {end_date}，请检查日期范围"
            )
        idx = pd.DatetimeIndex(pd.to_datetime(dates), name='date')
        return idx

    def _generate_symbol(self, symbol: str, idx: pd.DatetimeIndex) -> pd.DataFrame:
        """
        生成一只模拟标的的行情数据（纯内存，不走缓存、不下载）。

        对数价格按「带趋势的均值回复」演化：
            r_t = drift + reversion * (logAnchor - logP_{t-1}) + vol * eps_t
        eps_t ~ N(0, 1)。drift=0 且 reversion=0 时退化为纯随机游走。

        Args:
            symbol: Simulate 标的的代码
            idx: 日期轴（真实交易日，取自 _trading_index）

        Returns:
            pd.DataFrame，索引即 idx，含 6 个基础列，
            并按 self.extra_fields 追加扩展列 —— 与真实数据源行为一致（不给就不生成）。
        """
        spec = self._sim_specs[symbol]
        drift, reversion, vol = spec.drift, spec.reversion, spec.vol

        bars = len(idx)
        rng = np.random.default_rng()   # 每次新建 ⇒ 每次调用都是新行情

        # 1. 对数价格路径（锚点固定在起点价上，保证「震荡」真是围着起点来回）
        log_p = np.empty(bars)
        log_p[0] = np.log(self.SIM_START_PRICE)
        anchor = log_p[0]
        eps = rng.standard_normal(bars)
        for t in range(1, bars):
            log_p[t] = log_p[t - 1] + drift + reversion * (anchor - log_p[t - 1]) + vol * eps[t]
        close = np.exp(log_p)

        # 2. 涨跌停截断（相对前收），避免造出真实市场不会有的单日暴涨
        step_ret = np.clip(np.diff(close) / close[:-1], -self.SIM_LIMIT, self.SIM_LIMIT)
        close = np.concatenate([[close[0]], close[0] * np.cumprod(1.0 + step_ret)])

        # 3. OHLC：保证 high >= max(open, close)、low <= min(open, close)
        preclose = np.concatenate([[close[0]], close[:-1]])
        open_ = preclose * (1.0 + rng.normal(0.0, 0.002, bars))
        high = np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0.0, 0.003, bars)))
        low = np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0.0, 0.003, bars)))

        volume = rng.integers(1_000_000, 5_000_000, bars).astype(float)
        df = pd.DataFrame({
            'open': open_, 'high': high, 'low': low, 'close': close,
            'volume': volume, 'amount': volume * close,
        }, index=idx)

        # 4. 扩展列：只生成请求的字段（与真实源「不给就没有」一致）
        # 用「调用方原始请求」而非 self.extra_fields —— 模拟数据由 qka 现场生成，
        # 不依赖任何外部源，故不受数据源的扩展字段能力限制
        log_ratio = np.log(close / close[0])
        for field in self._requested_extra_fields:
            if field == 'preclose':
                df[field] = preclose
            elif field == 'pctChg':
                df[field] = (close / preclose - 1.0) * 100.0
            elif field == 'tradestatus':
                df[field] = 1
            elif field == 'isST':
                df[field] = 0
            elif field == 'turn':
                df[field] = np.abs(rng.normal(2.0, 0.6, bars))
            elif field in self.SIM_EXTRA_BASE:
                base, elasticity, idio_std = self.SIM_EXTRA_BASE[field]
                # 估值 = 基准值 × 价格弹性项 × 基本面自身波动项
                df[field] = base * np.exp(
                    elasticity * log_ratio
                    + self._sim_fundamental_walk(rng, bars, idio_std)
                )
        return df

    def _sim_fundamental_walk(self, rng, bars: int, idio_std: float) -> np.ndarray:
        """
        生成一条「基本面」对数扰动序列（OU 均值回复过程）。

        为什么需要它：真实世界里 PE = 市值 / 净利润，净利润是**独立于价格**演化
        的慢变量，所以真实估值与股价并不同步（实测长江电力 corr(peTTM, close)
        ≈ -0.09）。若估值列直接写成价格的等比缩放，该相关系数会逼近 +1，
        「低 PE 买入」这类策略在模拟数据上会被等价测成「价格策略」，语义失真。

        模型：z_t = phi * z_{t-1} + sigma * eps_t
        取 sigma = idio_std * sqrt(1 - phi^2) ⇒ 稳态标准差恰为 idio_std，
        故入参语义就是「估值对数偏离的量级」，可直接与真实数据对照。

        Args:
            rng: numpy Generator
            bars: 生成长度
            idio_std: 基本面自身的稳态对数波动

        Returns:
            np.ndarray，形状 (bars,)，z[0] = 0（对齐基准值起点）
        """
        phi = self.SIM_FUND_PHI
        sigma = idio_std * np.sqrt(1.0 - phi * phi)
        z = np.empty(bars)
        z[0] = 0.0
        eps = rng.standard_normal(bars)
        for t in range(1, bars):
            z[t] = phi * z[t - 1] + sigma * eps[t]
        return z

    def _checked_recently(self, path: Path) -> bool:
        """本时段是否已经问过数据源（以缓存文件的修改时间当记号）。

        缓存文件每次被写都会刷新修改时间：首次下载、补到新数据是写出来的；
        问了但数据源没给新数据时也会主动刷新一次（见 _download 末尾）。
        两种情形都意味着「本时段已经核对过，数据源不会再给新东西」。
        """
        if not path.exists():
            return False
        mtime = pd.Timestamp.fromtimestamp(path.stat().st_mtime)
        return _data_period(mtime) == _data_period(pd.Timestamp.now())

    def _mark_checked(self, path: Path) -> None:
        """留下「本时段已问过」的记号"""
        if path.exists():
            os.utime(path, None)

    def _read_verified_from(self, path: Path):
        """读「已确认起点」；没有记录（老缓存）返回 None"""
        try:
            meta = pq.read_schema(path).metadata or {}
        except Exception:
            return None
        raw = meta.get(self.VERIFIED_FROM_KEY)
        if not raw:
            return None
        try:
            return pd.Timestamp(raw.decode())
        except Exception:
            return None

    def _write_verified_from(self, path: Path, table: pa.Table, verified_from) -> None:
        """把「已确认起点」写进 parquet 元数据后落盘（数据本身原样保留）"""
        meta = dict(table.schema.metadata or {})
        meta[self.VERIFIED_FROM_KEY] = verified_from.strftime('%Y-%m-%d').encode()
        pq.write_table(table.replace_schema_metadata(meta), path)

    def _cache_missing_extra_fields(self, path: Path) -> bool:
        """检查已有 parquet 缓存是否缺少 extra_fields 指定的列。"""
        if not self.extra_fields or not path.exists():
            return False
        try:
            cols = set(pq.read_schema(path).names)
        except Exception:
            return True
        return any(f not in cols for f in self.extra_fields)

    def _extra_fields_whitelist(self, source: str) -> List[str]:
        """该数据源实际支持的扩展字段（源能力不同，按源过滤）。"""
        if source == 'baostock':
            return self.BAOSTOCK_EXTRA_FIELDS
        if source == 'tdx':
            return self.TDX_EXTRA_FIELDS
        return self.TICKFLOW_EXTRA_FIELDS

    def _merged_extra_fields(self, path: Path) -> List[str]:
        """
        计算本次下载实际请求的扩展字段：当前 extra_fields 与缓存已有扩展列的并集。

        保证同一 datadir 下不同 extra_fields 配置共享缓存时，列只增不减、
        不互相覆盖（第一次只有 peTTM，第二次再加 pbMRQ 时 peTTM 仍保留）。
        """
        merged = list(self.extra_fields)
        if not path.exists():
            return merged
        try:
            existing = set(pq.read_schema(path).names)
        except Exception:
            return merged
        whitelist = self._extra_fields_whitelist(self.source)
        for f in whitelist:
            if f in existing and f not in merged:
                merged.append(f)
        return merged

    def _download(
        self, symbol: str,
        download_start: str = None,
        download_end: str = None,
    ) -> Path:
        """
        按需下载单个股票数据。

        首次下载只拉请求范围（非全量）。已存在时检查缓存覆盖范围，
        只补下载缺失的部分（前面缺失补前面，后面缺失补后面），合并去重写回。
        若缓存缺少 extra_fields 指定的列（如从无扩展字段升级到有），则全量重新下载。

        例外：不允许增量缓存的复权方式（前复权，见 INCREMENTAL_ADJUSTS）不走增量，
        一旦需要问数据源就整段重取覆盖，详见 _rewrite_full。

        每次问完数据源都会留下痕迹：补到新数据就写文件（修改时间自然刷新），
        没补到就刷新修改时间 + 记下「已确认起点」。这两样让重复的请求不必再问网络，
        详见 _needs_download。

        Args:
            symbol: 股票代码
            download_start: 下载起始日期，格式 YYYY-MM-DD。None 表示拉全量（1990-01-01）
            download_end: 下载截止日期，格式 YYYY-MM-DD。None 表示到今天

        Returns:
            Path: 数据文件路径

        Raises:
            RuntimeError: 数据源返回空数据（首次下载时）
        """
        path = self.target_dir / f"{symbol}.parquet"
        default_start = '1990-01-01'
        default_end = pd.Timestamp.now().strftime("%Y-%m-%d")

        # 实际请求的扩展字段 = 当前配置 ∪ 缓存已有扩展列（列只增不减，不互相覆盖）
        merged_extra = self._merged_extra_fields(path)

        # ── 不通增量的复权方式（前复权）：整段重取、整段覆盖 ──
        # 前复权的历史会被今后的分红送股改写，只补新棒就会拼出「前段旧口径 + 后段新口径」
        # 的缝（见 INCREMENTAL_ADJUSTS），故一旦需要问数据源就整段重新要一遍、整体替换。
        if path.exists() and not self.incremental:
            return self._rewrite_full(
                path, symbol, download_start, download_end, merged_extra
            )

        # ── 首次下载：只拉请求范围（缓存缺失 extra_fields 列时也全量重下）──
        if not path.exists() or self._cache_missing_extra_fields(path):
            df = self._fetch(
                symbol,
                start_date=download_start or default_start,
                end_date=download_end or default_end,
                extra_fields=merged_extra,
            )
            if len(df) == 0:
                raise RuntimeError(f"{symbol}: 数据源（{self.source}）返回空数据")
            table = pa.Table.from_pandas(df)
            # 这次就是从这个起点问的，一并记下「已确认起点」
            self._write_verified_from(
                path, table, pd.Timestamp(download_start or default_start)
            )
            return path

        # ── 增量更新：检查缓存覆盖，补缺失范围 ──
        existing = pd.read_parquet(path)
        if not isinstance(existing.index, pd.DatetimeIndex):
            return path

        cache_min = existing.index.min()
        cache_max = existing.index.max()
        pieces = [existing]
        changed = False

        # 往前补（并记下「这个起点已确认没有更早的数据」，免得下次为同一个缺口白问）
        old_verified = self._read_verified_from(path)
        verified_from = old_verified
        req_start = pd.Timestamp(download_start) if download_start else None
        if req_start is not None and (old_verified is None or req_start < old_verified):
            if req_start < cache_min:
                end_before = (cache_min - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
                df_before = self._fetch(
                    symbol, start_date=download_start, end_date=end_before,
                    extra_fields=merged_extra,
                )
                if len(df_before) > 0:
                    pieces.insert(0, df_before)
                    changed = True
            verified_from = req_start

        # 往后补
        # 口径与 _needs_download 保持一致：按「日」比较。若用带时刻的 now()，
        # 缓存末日恰为今天时 now() > cache_max 恒成立，会去补 [明天, 今天] 这一段，
        # 起始日期大于终止日期 ⇒ baostock 直接报错。
        req_end = (pd.Timestamp(download_end) if download_end
                   else pd.Timestamp.now().floor('D'))
        if req_end > cache_max:
            start_after = (cache_max + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            df_after = self._fetch(
                symbol,
                start_date=start_after,
                end_date=download_end or default_end,
                extra_fields=merged_extra,
            )
            if len(df_after) > 0:
                pieces.append(df_after)
                changed = True

        if not changed and verified_from == old_verified:
            # 问过了，数据源这段确实没有新数据 —— 留个记号，本时段内不再重复问。
            # 失败（抛异常）时不走到这里，所以网络故障该重试还是会重试。
            self._mark_checked(path)
            return path

        if changed:
            combined = pd.concat(pieces)
            combined = combined[~combined.index.duplicated(keep='last')]
            combined = combined.sort_index()
            table = pa.Table.from_pandas(combined)
        else:
            table = pa.Table.from_pandas(existing)  # 数据没动，只是要更新「已确认起点」

        if verified_from is not None:
            self._write_verified_from(path, table, verified_from)
        else:
            pq.write_table(table, path)
        return path

    def _rewrite_full(
        self, path: Path, symbol: str,
        download_start: str = None, download_end: str = None,
        extra_fields: Optional[List[str]] = None,
    ) -> Path:
        """整段重取并覆盖缓存（供不允许增量缓存的复权方式使用）。

        为什么要盖住缓存已存的整段：只下「请求范围」会把长历史截短；只补缺口又会
        留下范围外的老口径数据 —— 那也是缝。所以范围取「缓存已有范围 ∪ 请求范围」，
        重取回来的整段是同一个口径，整体替换。

        Args:
            path: 缓存文件路径
            symbol: 标的代码
            download_start / download_end: 本次请求范围（None 表示不设边界）
            extra_fields: 本次要请求的扩展字段

        Returns:
            Path: 数据文件路径

        Raises:
            RuntimeError: 数据源返回空数据（此时保留原缓存，绝不拿空数据覆盖）
        """
        existing = pd.read_parquet(path)
        cache_min = existing.index.min()
        cache_max = existing.index.max()

        req_start = pd.Timestamp(download_start) if download_start else None
        req_end = (pd.Timestamp(download_end) if download_end
                   else pd.Timestamp.now().floor('D'))

        range_start = min(x for x in (cache_min, req_start) if x is not None)
        range_end = max(cache_max, req_end)

        df = self._fetch(
            symbol,
            start_date=range_start.strftime('%Y-%m-%d'),
            end_date=range_end.strftime('%Y-%m-%d'),
            extra_fields=extra_fields,
        )
        if len(df) == 0:
            raise RuntimeError(
                f"{symbol}: 数据源（{self.source}）返回空数据，已保留原缓存"
            )
        # 这次就是从这个起点问的，一并记下「已确认起点」
        self._write_verified_from(path, pa.Table.from_pandas(df), range_start)
        return path

    def _needs_download(
        self, symbol: str,
        download_start: str = None,
        download_end: str = None,
    ) -> bool:
        """
        判断股票是否需要网络下载。
        缓存不存在、不覆盖请求范围、或需要拉最新数据时返回 True。

        「缺最新数据」这件事按本时段去重（见 _data_period）：一天以数据生成时刻
        切成前后两段，同一段里问过一次就够了 —— 数据源在这段时间里不会多出东西。
        休市日、节假日的缓存末日永远早于「今天」，若不按时段去重就会每次请求都
        白问一趟，还永远问不到结果。
        """
        path = self.target_dir / f"{symbol}.parquet"
        if not path.exists() or self._cache_missing_extra_fields(path):
            return True
        existing = pd.read_parquet(path)
        if not isinstance(existing.index, pd.DatetimeIndex):
            return False
        cache_min = existing.index.min()
        cache_max = existing.index.max()

        # 往前：起点早于缓存首日才有缺口。但这个缺口往往只是撞上长假（缓存首日
        # 之后才是交易日），所以要看它是否已经被确认过 —— 没确认过才值得再问一趟。
        if download_start is not None:
            req_start = pd.Timestamp(download_start)
            if req_start < cache_min:
                verified_from = self._read_verified_from(path)
                if verified_from is None or req_start < verified_from:
                    return True

        # 往后：终点晚于缓存末日（给了 end_date 就是确定的缺口，直接补）。
        if download_end is not None:
            return pd.Timestamp(download_end) > cache_max

        # 无 end_date = 要一直要到今天。缺的只是「今天」这一段时，本时段问过就不必再问：
        # 数据源在这段时间里不会多出东西，休市日 / 盘前盘中尤其明显，否则每次请求都要白问一趟。
        if cache_max < pd.Timestamp.now().floor('D'):
            return not self._checked_recently(path)
        return False

    def get(self, lazy: bool = False, start_date: str = None, end_date: str = None):
        """
        获取历史数据。

        并发下载所有股票数据，应用因子计算，并返回合并后的数据。真实标的读本地缓存
        （必要时下载），模拟标的（Simulate）按同一日期轴现场生成 —— 两者写法完全同构。

        Args:
            lazy: 是否以懒加载模式返回 dask DataFrame（支持大规模数据分区迭代）。
                  默认 False，返回 compute() 后的 pandas DataFrame（向后兼容）。
            start_date: 起始日期，格式 YYYY-MM-DD。用于从缓存中截取数据范围，
                        避免全量加载。传 None 表示从最早可用数据开始；模拟标的在
                        start_date=None 时从 SIM_START 起算。
            end_date: 截止日期，格式 YYYY-MM-DD。传 None 表示到最新可用数据。

        Returns:
            lazy=False: pd.DataFrame，列名格式 {symbol}|{factor}
            lazy=True: dd.DataFrame，列名格式 {symbol}|{factor}
            没有数据时抛出 RuntimeError

        注意：有因子时，start_date 会自动向后扩展 max_window 个交易日读取缓存，
        确保因子有足够的预热数据。最终返回的 DataFrame 仍严格限定在 [start_date, end_date]。

        模拟标的的日期轴取自 baostock 交易日历（区间内一日一根），因此需要能登录 baostock。
        """
        if not self.symbols:
            return pd.DataFrame()

        # 计算因子预热窗口
        max_window = self._min_rows_for_factors()

        # 构建 parquet predicate pushdown 过滤（日期 + 因子预热扩展）
        pq_filters = None
        read_start = None
        if start_date is not None or end_date is not None or max_window > 0:
            pq_filters = []
            if start_date is not None:
                read_start = pd.Timestamp(start_date)
            if max_window > 0:
                if read_start is not None:
                    # 向后扩展，确保因子有足够的预热数据
                    read_start = read_start - pd.offsets.BDay(max_window * 2)
                # 无 start_date 但有因子时，不需要扩展（从头读即可）
            if read_start is not None:
                pq_filters.append(('date', '>=', read_start))
            if end_date is not None:
                pq_filters.append(('date', '<=', pd.Timestamp(end_date)))
            if not pq_filters:
                pq_filters = None

        # 计算网络下载范围（带预热扩展的 start_date）
        download_start = read_start.strftime("%Y-%m-%d") if read_start is not None else None
        download_end = end_date

        # 需要下载的真实标的（含基准）；模拟标的全在内存生成，永不下载
        all_symbols = list(self._real_symbols)
        if self.benchmark and self.benchmark not in all_symbols:
            all_symbols.append(self.benchmark)
        need_download = [
            s for s in all_symbols
            if self._needs_download(s, download_start, download_end)
        ]

        # 模拟标的的日期轴：区间内的真实交易日（随指标预热一起向前扩展）
        need_calendar = bool(self._sim_specs)
        sim_start = sim_end = None
        if need_calendar:
            sim_start = (read_start.strftime("%Y-%m-%d")
                         if read_start is not None else self.SIM_START)
            sim_end = (pd.Timestamp(end_date) if end_date is not None
                       else pd.Timestamp.now().floor('D')).strftime("%Y-%m-%d")

        # 需要下载、或需要模拟交易日历时，登录 baostock
        bs_logged_in = False
        if (need_download and self.source == 'baostock') or need_calendar:
            lg = bs.login()
            if lg.error_code != '0':
                raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
            bs_logged_in = True

        errors = []
        sim_index = None
        try:
            if need_calendar:
                sim_index = self._trading_index(sim_start, sim_end)
            if need_download:
                # baostock 与 tdx 都是「进程级单例连接」（tdx 的 tq 类方法
                # 共用同一 run_id），并发调用会共用同一连接状态，故逐个下载；
                # tickflow 的客户端无此约束，可并发。
                if self.source in ('baostock', 'tdx'):
                    for symbol in tqdm(need_download, desc="下载数据"):
                        try:
                            self._download(symbol, download_start, download_end)
                        except Exception as e:
                            errors.append(f"{symbol}: {e}")
                            print(f"\n[警告] 下载 {symbol} 失败: {e}")
                else:
                    with ThreadPoolExecutor(max_workers=self.pool_size) as executor:
                        futures = {
                            executor.submit(
                                self._download, symbol, download_start, download_end,
                            ): symbol
                            for symbol in need_download
                        }
                        with tqdm(total=len(need_download), desc="下载数据") as pbar:
                            for future in as_completed(futures):
                                symbol = futures[future]
                                try:
                                    future.result()
                                except Exception as e:
                                    errors.append(f"{symbol}: {e}")
                                    print(f"\n[警告] 下载 {symbol} 失败: {e}")
                                pbar.update(1)
                                pbar.set_postfix_str(f"当前: {symbol}")
            if errors:
                raise RuntimeError(
                    f"共 {len(errors)} 只股票下载失败:\n" +
                    "\n".join(f"  - {e}" for e in errors)
                )
        finally:
            if bs_logged_in:
                bs.logout()

        if lazy:
            # 懒加载模式：返回 dask DataFrame，列名 {symbol}|{factor}
            dfs = []
            for symbol in self.symbols:
                if symbol in self._sim_specs:
                    # clear_divisions：真实缓存读出的 divisions 恒为未知（(None, None)），
                    # 模拟帧若带已知 divisions，混合 concat 时 dask 会在 min/max 上炸
                    ddf = dd.from_pandas(
                        self._generate_symbol(symbol, sim_index), npartitions=1,
                    ).clear_divisions()
                else:
                    parquet_path = self.target_dir / f"{symbol}.parquet"
                    if not parquet_path.exists():
                        logger.warning(f"数据文件不存在，跳过: {parquet_path}")
                        continue
                    ddf = dd.read_parquet(str(parquet_path), filters=pq_filters)
                ddf['returns'] = ddf['close'].diff() / ddf['close'].shift(1)
                ddf = self._drop_head_lazy(ddf)
                ddf = self._apply_factors(ddf)
                column_mapping = {col: f'{symbol}|{col}' for col in ddf.columns}
                dfs.append(ddf.rename(columns=column_mapping))

            if not dfs:
                raise RuntimeError(
                    f"所有股票数据加载失败（共 {len(self.symbols)} 只），"
                    f"请检查网络连接和股票代码是否正确"
                )

            ddf = dd.concat(dfs, axis=1, join='outer')
            # 切片回用户请求的日期范围（去掉指标预热扩展部分）
            if start_date is not None and max_window > 0:
                cutoff = pd.Timestamp(start_date)
                ddf = ddf.loc[cutoff:]

            # 基准数据
            if self.benchmark:
                ddf = self._add_benchmark(ddf, self.target_dir, pq_filters)

            # qka 内置指标（需要 benchmark 和 symbol 前缀）
            ddf = self._apply_qka_factors(ddf)

            return ddf

        else:
            # 全量模式（默认）
            dfs = []
            for symbol in self.symbols:
                if symbol in self._sim_specs:
                    df = dd.from_pandas(
                        self._generate_symbol(symbol, sim_index), npartitions=1,
                    ).clear_divisions()
                else:
                    parquet_path = self.target_dir / f"{symbol}.parquet"
                    if not parquet_path.exists():
                        logger.warning(f"数据文件不存在，跳过: {parquet_path}")
                        continue
                    df = dd.read_parquet(str(parquet_path), filters=pq_filters)
                df['returns'] = df['close'].diff() / df['close'].shift(1)
                column_mapping = {col: f'{symbol}|{col}' for col in df.columns}
                dfs.append(df.rename(columns=column_mapping))

            if not dfs:
                raise RuntimeError(
                    f"所有股票数据加载失败（共 {len(self.symbols)} 只），"
                    f"请检查网络连接和股票代码是否正确"
                )

            ddf = dd.concat(dfs, axis=1, join='outer')
            result = ddf.compute()

            # 停牌日按前收补齐（默认关，见 _fill_suspended_prices）。必须在算因子之前 ——
            # 否则因子看到的还是带空缺的序列，长窗口照样算不出来。
            result = self._fill_suspended_prices(result)

            # 掐头（默认关，见 _drop_head_returns）。必须在补齐之后、算因子之前：
            # 补齐会重算 returns，先掐会被洗回来；因子在后面才吃 returns。
            result = self._drop_head_returns(result)

            # 因子：逐票逐因子贴上（带缓存 —— 全盖住就不算，只缺尾巴就只补尾巴）
            # 注意在切片之前算：此时还带着预热数据，滚动窗口才够长。
            result = self._factors_with_cache(result)

            # 切片回用户请求的日期范围
            if start_date is not None and max_window > 0:
                result = result[result.index >= pd.Timestamp(start_date)]

            # 基准数据
            if self.benchmark:
                result = self._add_benchmark(result, self.target_dir, pq_filters)

            # qka 内置因子（需要 benchmark 和 symbol 前缀）
            result = self._qka_factors_with_cache(result)

            # 列顺序复原，与重构前一致
            return self._order_columns(result, self._qka_factor_names())

    def _add_benchmark(self, df, target_dir, pq_filters):
        """将基准数据的 returns 以 benchmark| 前缀追加到 DataFrame。"""
        bench_path = target_dir / f"{self.benchmark}.parquet"
        if not bench_path.exists():
            logger.warning(f"基准数据文件不存在: {bench_path}")
            return df
        bench_df = pd.read_parquet(bench_path, filters=pq_filters)
        bench_df['returns'] = bench_df['close'].diff() / bench_df['close'].shift(1)
        # 基准同样掐头：规则对所有序列一视同仁（"来啥废啥"，不猜哪天上市）
        if self.drop_head > 0:
            if len(bench_df) > self.drop_head:
                cutoff = bench_df.index[self.drop_head - 1]
                bench_df['returns'] = bench_df['returns'].where(bench_df.index > cutoff)
            else:
                bench_df['returns'] = np.nan
        bench_returns = bench_df['returns'].rename('benchmark|returns')

        if isinstance(df, dd.DataFrame):
            # dask: 用 assign 加列，pandas Series 会自动对齐分区
            return df.assign(**{'benchmark|returns': bench_returns})
        else:
            df['benchmark|returns'] = bench_returns.reindex(df.index)
            return df

    def _drop_head_returns(self, result):
        """掐头（默认路径用）：每条序列的前 drop_head 根，returns 记空。

        语义是「来啥废啥」—— 不猜哪天上市、不做探测：取回来的数据，开头 N 根
        一律当垫场。调用方把 start 传在上市日，N 根垫场就正好是「上市后前 N 个
        交易日」；start 传得更晚，也只是白掐 20 根（少 20 个样本），数值永远是对的。

        为什么放在停牌补齐之后：补齐会按补好的 close 重算 returns，先掐会被洗回来。

        定位"一只票自己的前 N 根"：按 close 非空计数（宽表里上市前的行 close 是
        空的，不算数）；基准列没有 close，退而按 returns 自身的非空值计数。
        """
        if self.drop_head <= 0:
            return result
        for col in [c for c in result.columns if c.endswith('|returns')]:
            base = col[:-len('|returns')]
            close_col = result[f'{base}|close'] if f'{base}|close' in result.columns else None
            counter = close_col if close_col is not None else result[col]
            head = counter.notna().cumsum() <= self.drop_head
            result.loc[head, col] = np.nan
        return result

    def _drop_head_lazy(self, ddf):
        """掐头（懒加载路径用）：单票自己的序列，前 drop_head 根 returns 记空。

        懒加载时每只票还是独立的 dask 帧（尚未拼宽表），帧的开头就是它自己的头。
        用「第 N 个索引标签」做切点：比它晚的行保留，早的（含第 N 根）记空。
        """
        if self.drop_head <= 0:
            return ddf
        labels = ddf.index.to_series().head(self.drop_head).compute()
        if labels.empty:
            return ddf
        if len(labels) < self.drop_head:
            # 序列总共不到 N 根：整条记空
            return ddf.map_partitions(lambda part: part.assign(returns=np.nan))
        cutoff = labels.iloc[-1]
        return ddf.map_partitions(
            lambda part: part.assign(returns=part['returns'].where(part.index > cutoff))
        )

    def _apply_factors(self, df):
        """
        对单只股票的数据应用预定义的指标/因子。

        支持三种形式：
        - 空 dict → 跳过
        - callable → 旧版 factor 风格，接收 df 返回 df
        - dict → 混合 TA 指标和自定义 callable

        Args:
            df: 单只股票的 DataFrame

        Returns:
            DataFrame: 包含原始列和指标列
        """
        inds = self._factors

        # 空 → 跳过
        if not inds:
            return df

        # 单函数形式（旧版 factor 的替代）
        if callable(inds):
            if isinstance(df, dd.DataFrame):
                return df.map_partitions(lambda p: inds(p.copy()))
            return inds(df.copy())

        # 字典形式
        if isinstance(df, dd.DataFrame):
            # 样本行数完全由 warmup 决定（用户显式声明前置窗口），不写死兜底值。
            # warmup=0 表示用户不预留前置数据，lambda 指标可能因此无法物化——属用户责任。
            sample = df.head(self._min_rows_for_factors())
            meta = self._compute_factor_cols(sample.copy())
            return df.map_partitions(
                lambda partition: self._compute_factor_cols(partition.copy()),
                meta=meta,
            )
        return self._compute_factor_cols(df.copy())

    def _compute_factor_cols(self, df, only=None):
        """在 pandas DataFrame 上计算指标/因子列（单只股票）。

        Args:
            df: 单票 DataFrame
            only: 只算这几个列名（None = 全算）。因子缓存按因子粒度补算时用。
        """

        # 分区过小时跳过，避免 ta-lib 在 dask meta 推断时崩溃
        min_rows = self._min_rows_for_factors()
        if len(df) < min_rows:
            return df

        for col_name, spec in self._factors.items():
            if only is not None and col_name not in only:
                continue
            # 自定义因子（callable 值）
            if callable(spec):
                result = spec(df)
                if isinstance(result, pd.DataFrame):
                    # 多列返回 → 逐列添加
                    for c in result.columns:
                        df[c] = result[c]
                else:
                    # 单值返回 → 列名 = key
                    df[col_name] = result
                continue

            # TA 指标（tuple 值）
            if not isinstance(spec, (list, tuple)):
                logger.warning(f"指标 {col_name} 的规格必须为 tuple 或 callable，跳过")
                continue

            ind_type = spec[0]

            # qka 内置指标：跳过，由 _apply_qka_factors 集中处理
            if _is_qka_factor(ind_type):
                continue

            args = list(spec[1:])

            # 收集前面连续的字符串参数作为列名（遇到第一个非字符串即停）
            cols = []
            rest_start = 0
            for i, arg in enumerate(args):
                if isinstance(arg, str):
                    cols.append(arg)
                    rest_start = i + 1
                else:
                    break
            if not cols:
                logger.warning(f"指标 {col_name} 缺少计算列名，跳过")
                continue
            rest = args[rest_start:]

            # 动态解析 ta 函数路径：'ta.trend.sma_indicator' → 导入并调用
            if not isinstance(ind_type, str) or '.' not in ind_type:
                logger.warning(f"指标 {col_name} 的类型必须为 'ta.xxx.yyy' 格式，跳过: {ind_type}")
                continue

            import importlib
            parts = ind_type.rsplit('.', 1)
            if len(parts) != 2:
                logger.warning(f"指标 {col_name} 类型格式错误: {ind_type}")
                continue
            module_name, func_name = parts
            try:
                mod = importlib.import_module(module_name)
                fn = getattr(mod, func_name)
            except (ImportError, AttributeError) as e:
                logger.warning(f"无法加载指标函数 {ind_type}: {e}")
                continue

            if len(cols) == 1:
                df[col_name] = fn(df[cols[0]], *rest)
            else:
                df[col_name] = fn(*[df[f] for f in cols], *rest)

        return df

    def _apply_qka_factors(self, df):
        """应用 qka 内置指标（带 symbol 前缀，含 benchmark 数据）。

        必须在 concat + 加 benchmark 之后调用，此时列名格式为
        {symbol}|returns 和 benchmark|returns。

        Args:
            df: 合并后的 DataFrame（列名已带 symbol 前缀）

        Returns:
            DataFrame: 含 qka 指标列
        """
        inds = self._factors
        if not inds or not isinstance(inds, dict):
            return df

        qka_specs = [
            (col_name, spec) for col_name, spec in inds.items()
            if isinstance(spec, (list, tuple))
            and _is_qka_factor(spec[0])
        ]
        if not qka_specs:
            return df

        if isinstance(df, dd.DataFrame):
            sample = df.head(self._min_rows_for_factors())
            meta = self._compute_qka_factor_cols(sample, qka_specs)
            return df.map_partitions(
                lambda p: self._compute_qka_factor_cols(p, qka_specs),
                meta=meta,
            )
        return self._compute_qka_factor_cols(df, qka_specs)

    def _compute_qka_factor_cols(self, df, qka_specs, symbols=None):
        """在已合并的 DataFrame 上计算 qka 内置指标。"""
        for col_key, spec in qka_specs:
            fn_name = spec[0].split('.', 1)[1] if spec[0].startswith('qka.') else spec[0]
            args = list(spec[1:])

            try:
                fn = getattr(indicator, fn_name)
            except AttributeError:
                logger.warning(f"qka 内置指标不存在: {fn_name}，跳过")
                continue

            # 为每只股票计算
            for symbol in (symbols if symbols is not None else self.symbols):
                col = f'{symbol}|{col_key}'
                try:
                    df[col] = fn(df, symbol, *args)
                except ValueError as e:
                    logger.warning(f"计算 {col_key} 失败: {e}")
                    df[col] = np.nan

        return df

    def _min_rows_for_factors(self):
        """计算所有因子所需的最小行数（含显式预热天数）。

        遍历所有因子条目的整数参数，取最大值作为窗口上限的保守估计，
        再与显式 warmup 取较大者。
        """
        if not self._factors or not isinstance(self._factors, dict):
            return self.warmup
        max_window = 0
        for spec in self._factors.values():
            if callable(spec) or not isinstance(spec, (list, tuple)):
                continue
            # spec[1:] 中跳过所有前导字符串（列名），收集剩余整数
            rest = list(spec[1:])
            idx = 0
            while idx < len(rest) and isinstance(rest[idx], str):
                idx += 1
            for v in rest[idx:]:
                if isinstance(v, int):
                    max_window = max(max_window, v)
        return max(max_window, self.warmup)

    # ── 因子缓存 ────────────────────────────────────────────────
    # 因子就是从行情算出来的「下一列」，所以跟行情一样纵向落盘。
    # 但目录**不按数据源/周期/复权分**（那三样是「行情」的口径），而是按**因子名**分：
    # 一个因子 = 一份独立的资产，可以单独查、单独发布、单独排名。
    #
    #     datadir/factors/{因子名}/{symbol}.parquet     （单列，索引同行情）
    #
    # 数据源 / 周期 / 复权 + 因子定义本身，一起压进文件的「配方指纹」——
    # 只要其中任一样变了，指纹就对不上，该票该因子整条重算并覆盖。

    FACTOR_DIR = 'factors'
    FACTOR_META_KEY = b'qka_factor_meta'
    FACTOR_CACHE_VERSION = 1
    _UNSET = object()

    # 停牌日要按前收填充的列（价格类）。停牌当天没有成交，价格就跟前一天一样；
    # volume / amount 不填 —— 那天确实没有成交量，硬填反而不诚实。
    SUSPENDED_FILL_COLUMNS = ('open', 'high', 'low', 'close')

    def _fill_suspended_prices(self, result):
        """把停牌日按「前收」补齐：当天价格 = 前一个交易日的收盘价。

        为什么需要：各标的只在自己的交易日有 K 线，对齐到同一张宽表后，**停牌日就是空缺**。
        而滚动类因子（α/β/波动率……）默认要求窗口内一天都不能缺 —— 只要这只票在过去 N 天里
        停过一天牌，指标就整条算不出来。

        填充口径：价格四列取前一交易日的值（当天收益率因此为 0，等价于「那天没交易」）；
        `returns` 按填充后的 close 重算。**上市前的空缺没有前值，仍然留空** ——
        不会凭空造出一段历史。

        只作用于默认（`lazy=False`）路径，由 `fill_suspended=True` 显式开启。
        """
        if not self.fill_suspended:
            return result
        col_index = self._columns_by_symbol(result.columns)
        replacements = {}
        for symbol in self.symbols:
            sym_cols = col_index.get(symbol)
            if not sym_cols:
                continue
            cols = [
                c for c in sym_cols
                if c.split('|', 1)[1] in self.SUSPENDED_FILL_COLUMNS
            ]
            if not cols:
                continue
            before = result[cols]
            filled = before.ffill()
            if filled.equals(before):
                continue        # 这只票一次没停过牌，什么都别动（省掉重算 returns）
            for c in cols:
                replacements[c] = filled[c]
            if f'{symbol}|close' in cols:
                # 口径与 get() 里一致：diff/shift，不用 pct_change（它的 fill_method 默认值在弃用中）
                close = filled[f'{symbol}|close']
                replacements[f'{symbol}|returns'] = close.diff() / close.shift(1)
        if not replacements:
            return result
        # 一次性换掉，而不是每票各写两遍（全市场就是上万次逐列插入）。
        # 拼回后按原列序重排，保证列顺序一点不变。
        names = list(replacements)
        merged = pd.concat(
            [result.drop(columns=names),
             pd.DataFrame(replacements, index=result.index)],
            axis=1,
        )
        return merged[result.columns]

    def _factor_plan(self):
        """{因子名: (定义, 指纹)}；只要有因子认不出配方就整体返回 None（这次不缓存）。

        认不出的典型是「取不到源码的可调用对象」（REPL 里现写的 lambda、
        动态拼出来的函数）——它的指纹没法跨进程稳定，宁可每次现算，
        也不能拿旧配方算出来的值冒充新值。
        """
        plan = getattr(self, '_factor_plan_cache', self._UNSET)
        if plan is not self._UNSET:
            return plan

        plan = None
        if isinstance(self._factors, dict) and self._factors:
            built = {}
            for name, spec in self._factors.items():
                fp = self._factor_signature(name, spec)
                if fp is None:
                    built = None
                    break
                built[name] = (spec, fp)
            plan = built
        self._factor_plan_cache = plan
        return plan

    def _factor_signature(self, name, spec):
        """单个因子的配方指纹（定义 + 数据口径）；认不出返回 None。

        数据口径 = 数据源 / 周期 / 复权 / **停牌是否补齐** / **掐头根数** —— 任一样变了，
        算出来的值就不一样，指纹必须跟着变，否则缓存会拿旧口径的值冒充新值。
        """
        payload = self._spec_payload(spec)
        if payload is None:
            return None
        blob = json.dumps({
            'v': self.FACTOR_CACHE_VERSION,
            'name': name,
            'spec': payload,
            'source': self.source,
            'period': self.period,
            'adjust': self.adjust,
            'fill_suspended': self.fill_suspended,
            'drop_head': self.drop_head,
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha1(blob.encode('utf-8')).hexdigest()

    @staticmethod
    def _spec_payload(spec):
        """把一份因子定义转成可稳定序列化的结构；认不出返回 None。"""
        if callable(spec):
            src = _callable_source(spec)
            return None if src is None else {'fn': src}
        if isinstance(spec, (list, tuple)):
            if all(isinstance(x, (str, int, float, bool)) for x in spec):
                return list(spec)
            return None
        return None

    def _factor_cache_path(self, name: str, symbol: str) -> Path:
        return self.datadir / self.FACTOR_DIR / name / f'{symbol}.parquet'

    def _read_factor_cache(self, name, symbol, fingerprint):
        """读该票该因子的缓存序列；文件不在 / 指纹不符 / 读不出来 → None。

        不在这里判断「盖没盖住范围」——那是 `_recompute_target` 的事：
        盖住了就一个字不算，只缺尾巴就只补尾巴。
        """
        path = self._factor_cache_path(name, symbol)
        if not path.exists():
            return None
        try:
            raw = (pq.read_schema(path).metadata or {}).get(self.FACTOR_META_KEY)
            if not raw or json.loads(raw.decode()).get('fingerprint') != fingerprint:
                return None
            df = pd.read_parquet(path)
        except Exception:
            return None
        if df.empty or name not in df.columns or not isinstance(df.index, pd.DatetimeIndex):
            return None
        return df[name]

    def _write_factor_cache(self, name, symbol, fingerprint, series) -> None:
        """把该票该因子的值并进缓存文件。

        同一指纹下只增不改（老值按索引保留，新算的覆盖同日）；指纹变了说明配方或
        口径换了，整条重写——绝不把两套口径的值混在一个文件里。
        """
        if series is None or series.empty:
            return
        path = self._factor_cache_path(name, symbol)
        merged = pd.DataFrame({name: series})
        if path.exists():
            try:
                old_meta = (pq.read_schema(path).metadata or {}).get(self.FACTOR_META_KEY)
                same = bool(old_meta) and \
                    json.loads(old_meta.decode()).get('fingerprint') == fingerprint
                old = pd.read_parquet(path)
                if same and name in old.columns:
                    merged = pd.concat([old[[name]], merged])
                    merged = merged[~merged.index.duplicated(keep='last')].sort_index()
            except Exception:
                pass
        path.parent.mkdir(parents=True, exist_ok=True)
        table = pa.Table.from_pandas(merged)
        meta = dict(table.schema.metadata or {})
        meta[self.FACTOR_META_KEY] = json.dumps({
            'fingerprint': fingerprint,
            'v': self.FACTOR_CACHE_VERSION,
            'source': self.source,
            'period': self.period,
            'adjust': self.adjust,
        }, ensure_ascii=False).encode()
        pq.write_table(table.replace_schema_metadata(meta), path)

    def _recompute_target(self, full, cached):
        """算出「这次要重算哪一段」。

        - 没有缓存 → 整段算（返回 full）
        - 缓存全盖住 → 不用算（返回 None）
        - 只缺尾巴 → **只算尾巴**（往前留出预热窗口，滚动指标才准）
        - 前面也缺 → 整段算
        """
        if cached is None:
            return full
        if cached.index.min() <= full.index.min() and cached.index.max() >= full.index.max():
            return None
        if cached.index.min() > full.index.min():
            return full
        min_rows = self._min_rows_for_factors()
        if min_rows <= 0:
            # 窗口完全靠猜（lambda + 没声明 warmup）⇒ 不敢只补尾巴，整段重算
            return full
        margin = pd.offsets.BDay(min_rows * 2)
        tail = full.loc[cached.index.max() - margin:].copy()
        if len(tail) < min_rows:
            return full
        return tail

    @staticmethod
    def _columns_by_symbol(columns):
        """一次遍历建「票 → 它有哪些列」的索引。

        全市场宽表 6 万列，而下面几处都是按票走的：若每票都重新扫一遍全部列名，
        就是 7556 × 6 万次字符串比较 —— 光这一项就足以把整轮跑批拖垮。
        """
        groups = {}
        for col in columns:
            if '|' in col:
                groups.setdefault(col.split('|', 1)[0], []).append(col)
        return groups

    @staticmethod
    def _symbol_slice(result, symbol, cols=None):
        """从宽表里取出该票的列、去掉 {symbol}| 前缀（缺失返回空表）。

        `cols` 传 ``_columns_by_symbol`` 里该票那一份，省掉一次全表扫描。
        """
        prefix = f'{symbol}|'
        if cols is None:
            cols = [c for c in result.columns if c.startswith(prefix)]
        sub = result[cols].copy()
        sub.columns = [c[len(prefix):] for c in cols]
        return sub

    @staticmethod
    def _collect_slice(symbol, sub, names):
        """把该票新算出来的列收进 ``{列名: 序列}``，交给调用方最后一次性拼上。

        逐列写进结果表会让 pandas 在内存里碎成几万块（每插一列就可能多出一个
        block），此后每次读写都得逐个遍历这些块。收集起来一次 concat，块数就稳住。
        """
        prefix = f'{symbol}|'
        return {
            f'{prefix}{name}': sub[name]
            for name in names
            if name in sub.columns
        }

    @staticmethod
    def _attach_columns(result, collected):
        """把收集到的列**一次**拼上。

        这是整套流程里唯一「往结果表加列」的动作 —— 一次 concat 取代原先的
        几万次逐列插入。
        """
        if not collected:
            return result
        new = pd.DataFrame(collected, index=result.index)
        return pd.concat([result, new], axis=1)

    def _qka_factor_names(self):
        """`self._factors` 里属于 qka 内置因子（α/β/夏普…）的列名，按声明顺序。"""
        if not isinstance(self._factors, dict):
            return []
        return [
            n for n, spec in self._factors.items()
            if isinstance(spec, (list, tuple)) and _is_qka_factor(spec[0])
        ]

    def _order_columns(self, result, qka_names):
        """把列重排回重构前的顺序，纯粹为了不改变既有行为。

        重构前：每票的行情列 → returns → ta/自定义因子，逐票成组；然后是 benchmark，
        最后是 qka 内置因子（**先按因子名、再按标的**）。
        因子缓存把那两类因子都挪到帧尾贴上，顺序就散了。消费者虽然都按列名取值，
        但没理由让它们替我们承担这个差异。
        """
        known = set(self.symbols)
        qka_cols = {f'{s}|{n}' for n in qka_names for s in self.symbols}
        groups, rest, tail = {}, [], []
        for col in result.columns:
            if col in qka_cols:
                tail.append(col)
                continue
            symbol = col.split('|', 1)[0] if '|' in col else None
            if symbol in known:
                groups.setdefault(symbol, []).append(col)
            else:
                rest.append(col)
        order = []
        for symbol in self.symbols:
            order.extend(groups.get(symbol, ()))
        order.extend(rest)
        order.extend(tail)
        return result[order]

    def _factors_with_cache(self, result):
        """逐票把 ta / 自定义因子算出来：命中缓存直接用，没命中才现算并写回。

        只用于默认（非懒加载）路径。懒加载路径行为完全不变。
        新列先收在 collected 里，循环结束一次拼上（见 `_attach_columns`）。
        """
        if not self._factors:
            return result
        # 没开因子缓存 → plan 强制为 None，走下面「现算不落盘」那条路
        plan = self._factor_plan() if self.factor_cache else None
        col_index = self._columns_by_symbol(result.columns)
        collected = {}
        for symbol in self.symbols:
            cols = col_index.get(symbol)
            if not cols:
                continue
            sub = self._symbol_slice(result, symbol, cols)
            if sub.empty:
                continue

            # 模拟标的没有缓存文件；没开缓存 / 配方认不出也一样 —— 一律现算不落盘
            if plan is None or symbol in self._sim_specs:
                before = set(sub.columns)
                sub = self._apply_factors(sub)
                collected.update(self._collect_slice(
                    symbol, sub, [c for c in sub.columns if c not in before]
                ))
                continue

            names = [
                n for n, (spec, _fp) in plan.items()
                if not (isinstance(spec, (list, tuple)) and _is_qka_factor(spec[0]))
            ]
            for name in names:
                spec, fp = plan[name]
                cached = self._read_factor_cache(name, symbol, fp)
                target = self._recompute_target(sub, cached)
                if target is None:
                    sub[name] = cached.reindex(sub.index)
                    continue
                self._compute_factor_cols(target, only={name})
                if target is sub:
                    series = sub[name]
                else:
                    # 补算的尾巴头部自带滚动预热 NaN，用缓存里的老值兜住，
                    # 不能拿 NaN 去覆盖本来好好的值。
                    series = target[name].reindex(sub.index).combine_first(
                        cached.reindex(sub.index)
                    )
                    sub[name] = series
                self._write_factor_cache(name, symbol, fp, series)
            collected.update(self._collect_slice(symbol, sub, names))
        return self._attach_columns(result, collected)

    def _qka_factors_with_cache(self, result):
        """逐票把 qka 内置因子（α/β/夏普…）算出来；开了因子缓存才吃缓存。需在 benchmark 之后调用。

        与 `_factors_with_cache` 一样：新列先收集、最后一次性拼上。另外这里不再
        拿整张宽表当计算台 —— 内置因子只看该票的 returns 加基准，给它一张只含
        这几列的小表就够了（宽表 6 万列，逐票拿它来算太贵）。
        """
        if not self.factor_cache:
            return self._apply_qka_factors(result)
        plan = self._factor_plan()
        names = []
        if plan is not None:
            names = [
                n for n, (spec, _fp) in plan.items()
                if isinstance(spec, (list, tuple)) and _is_qka_factor(spec[0])
            ]
        if not names:
            return self._apply_qka_factors(result)

        col_index = self._columns_by_symbol(result.columns)
        bench_cols = col_index.get('benchmark', [])
        collected = {}
        for name in names:
            spec, fp = plan[name]
            # 按「先因子名、再标的」的顺序贴，保持与重构前一致
            for symbol in self.symbols:
                sym_cols = col_index.get(symbol)
                if not sym_cols or f'{symbol}|returns' not in result.columns:
                    continue
                col = f'{symbol}|{name}'
                # 明确复制一份当计算台：内置因子要往它上面加列，而它是从宽表
                # 切出来的视图 —— 不复制的话 pandas 每次都会警告「在切片副本上赋值」。
                view = result[sym_cols + bench_cols].copy()
                if view.empty:
                    continue
                if symbol in self._sim_specs:
                    # 模拟标的没有缓存文件，直接算
                    self._compute_qka_factor_cols(view, [(name, spec)], symbols=[symbol])
                    collected[col] = view[col]
                    continue
                cached = self._read_factor_cache(name, symbol, fp)
                target = self._recompute_target(view, cached)
                if target is None:
                    collected[col] = cached.reindex(result.index)
                    continue
                # 这里给的是一张只有该票的小表，必须把标的限定成它自己
                self._compute_qka_factor_cols(target, [(name, spec)], symbols=[symbol])
                if target is view:
                    series = view[col]
                else:
                    # 同上：补算尾巴头部的预热 NaN 用缓存老值兜住
                    series = target[col].reindex(result.index).combine_first(
                        cached.reindex(result.index)
                    )
                collected[col] = series
                self._write_factor_cache(name, symbol, fp, series)
        return self._attach_columns(result, collected)

    def _get_from_baostock(
        self, symbol: str,
        start_date: str = '1990-01-01',
        end_date: str = '2050-12-31',
        extra_fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        从 baostock 获取单个股票的数据。

        Args:
            symbol: 标的代码，任意写法（600519.SH 或 sh.600519），内部统一转换
            start_date: 起始日期，格式 YYYY-MM-DD，默认 1990-01-01
            end_date: 截止日期，格式 YYYY-MM-DD，默认 2050-12-31
            extra_fields: 本次请求的扩展字段列表。None 时使用 self.extra_fields；
                调用方（_download）可传入"当前配置 ∪ 缓存已有列"的并集，保证列只增不减

        Returns:
            pd.DataFrame: 股票数据，以 date 为索引，包含 open, high, low, close, volume, amount
            及 extra_fields 指定的扩展列（如有）
        """
        # adjustflag: 1=不复权, 2=前复权, 3=后复权
        adjust_map = {'bfq': '1', 'qfq': '2', 'hfq': '3'}
        adjustflag = adjust_map.get(self.adjust, '2')

        # 基础字段 + extra_fields 扩展字段（缺省用 self.extra_fields）
        extra = list(extra_fields) if extra_fields is not None else self.extra_fields
        fields = ",".join(["date"] + self.BAOSTOCK_BASE_FIELDS + extra)

        # baostock 只认 sh.600519 写法 ⇒ 无论调用方用哪种写法都统一转换
        bs_symbol = self.to_baostock_symbol(symbol)

        rs = bs.query_history_k_data_plus(
            bs_symbol,
            fields,
            start_date=start_date,
            end_date=end_date,
            frequency='d',
            adjustflag=adjustflag,
        )
        if rs.error_code != '0':
            raise RuntimeError(f"baostock 查询 {symbol}({bs_symbol}) 失败: {rs.error_msg}")
        # 官网标准写法：get_row_data() 逐行取 + next() 翻页，避免 get_data() 的 df.append()
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        df = pd.DataFrame(data_list, columns=rs.fields) if data_list else pd.DataFrame()

        if len(df) == 0:
            return df

        # baostock 返回的数值列是字符串，转数值类型（基础列 + 本次请求的扩展字段）
        numeric_cols = self.BAOSTOCK_BASE_FIELDS + extra
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        return df

    # ── 取数分发 ────────────────────────────────────────────────

    def _fetch(
        self, symbol: str,
        start_date: str = '1990-01-01',
        end_date: str = '2050-12-31',
        extra_fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """按当前数据源分发到对应实现，返回结构一致（date 索引 + OHLCV/amount）。"""
        if self.source == 'baostock':
            return self._get_from_baostock(symbol, start_date, end_date, extra_fields)
        if self.source == 'tdx':
            return self._get_from_tdx(symbol, start_date, end_date, extra_fields)
        return self._get_from_tickflow(symbol, start_date, end_date, extra_fields)

    # ── TickFlow 数据源 ────────────────────────────────────────

    _tf_clients = {}    # {key 摘要: 客户端} —— 进程级复用；按 key 分开存，不同 key 不互相串
    _tf_client_lock = threading.Lock()

    @classmethod
    def _reset_tickflow_clients(cls):
        """丢掉已建好的 tickflow 客户端，下次按当前 key 重建。

        由 `set_tickflow_api_key()` 调用：客户端一旦建好就缓存住，不清的话
        「先建了免费档客户端、后设 key」会静默继续走免费档。
        """
        with cls._tf_client_lock:
            cls._tf_clients.clear()

    @classmethod
    def _tickflow_client(cls):
        """惰性创建并复用 TickFlow 客户端。

        有 key 走完整服务（api.tickflow.org），没有就走免费档
        （free-api.tickflow.org）。key 是**建客户端这一刻**现取的，
        所以设 key 的时机不必早于 import（见 `set_tickflow_api_key`）。
        """
        key = get_tickflow_api_key()
        cache_key = _key_fingerprint(key)
        client = cls._tf_clients.get(cache_key)
        if client is None:
            with cls._tf_client_lock:
                client = cls._tf_clients.get(cache_key)
                if client is None:
                    from tickflow import TickFlow
                    # free() 会往 stdout 打一段带 emoji 的「免费档」说明。
                    # stdout 被重定向到文件、且编码非 UTF-8 时（如打包版把后端输出
                    # 写入 GBK 日志），print emoji 会抛 UnicodeEncodeError 而中断下载，
                    # 故创建期间丢弃其标准输出。（redirect_stdout 改的是全局 sys.stdout，
                    # 并发首次创建会互相覆盖，故用锁串行化。）
                    with contextlib.redirect_stdout(io.StringIO()):
                        client = TickFlow(api_key=key) if key else TickFlow.free()
                    cls._tf_clients[cache_key] = client
        return client

    @staticmethod
    def _split_symbol(symbol: str):
        """
        拆出 (小写市场, 代码)。两种写法等价、都支持：

            600519.SH   （推荐，数字在前）
            sh.600519   （旧写法，兼容保留）

        Returns:
            (market, code)，如 ('sh', '600519')
        """
        if '.' not in symbol:
            raise ValueError(
                f"标的代码缺少市场标识: {symbol!r}（应形如 600519.SH 或 sh.600519）"
            )
        head, tail = symbol.split('.', 1)
        # 市场标识是两位字母（sh/sz/bj/hk/us），据此判断它在前还是在后
        if len(head) == 2 and head.isalpha():
            market, code = head, tail        # sh.600519
        else:
            code, market = head, tail        # 600519.SH
        return market.lower(), code

    @classmethod
    def to_baostock_symbol(cls, symbol: str) -> str:
        """任意写法 → baostock 写法，如 sh.600519"""
        market, code = cls._split_symbol(symbol)
        return f"{market}.{code}"

    @classmethod
    def to_tickflow_symbol(cls, symbol: str) -> str:
        """任意写法 → tickflow 写法，如 600519.SH"""
        market, code = cls._split_symbol(symbol)
        return f"{code}.{market.upper()}"

    @classmethod
    def to_tdx_symbol(cls, symbol: str) -> str:
        """任意写法 → 通达信写法，如 600519.SH（与 tickflow 同形）"""
        return cls.to_tickflow_symbol(symbol)

    def _get_from_tickflow(
        self, symbol: str,
        start_date: str = '1990-01-01',
        end_date: str = '2050-12-31',
        extra_fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        从 TickFlow 获取单只标的的日线数据。

        返回结构与 _get_from_baostock 一致（date 索引 + open/high/low/close/
        volume/amount），但有两处口径必须转换：
        - **volume**：TickFlow 单位为「手」，×100 换算成 baostock 口径的「股」
        - **timestamp**：TickFlow 给的是「北京时间当天零点」对应的 UTC 毫秒，
          需 +8 小时还原为北京日期，否则日期整体偏一天

        extra_fields 对 TickFlow 无意义（其历史日线不含扩展列），此处不处理。
        """
        # 周期映射（当前仅日/周/月线；分钟线 TickFlow 属付费能力，未接）
        period_map = {'1d': '1d', '1w': '1w', '1M': '1M'}
        if self.period not in period_map:
            raise RuntimeError(
                f"tickflow 源暂不支持周期 {self.period!r}（可选: {list(period_map)}）"
            )
        period = period_map[self.period]

        # 复权映射：tickflow forward=前复权 / backward=后复权 / none=不复权
        adjust_map = {'bfq': 'none', 'qfq': 'forward', 'hfq': 'backward'}
        adjust = adjust_map.get(self.adjust, 'forward')

        tf_symbol = self.to_tickflow_symbol(symbol)

        # 日期 → 毫秒时间戳（右端 +1 天，保证 end_date 当天落在闭区间内）
        start_ms = int(pd.Timestamp(start_date).timestamp() * 1000)
        end_ms = int((pd.Timestamp(end_date) + pd.Timedelta(days=1)).timestamp() * 1000)

        client = self._tickflow_client()
        try:
            data = client.klines.get(
                tf_symbol,
                period=period,
                # count 必须显式给足：TickFlow 默认只返回最近 100 条，
                # 不给会静默截断长区间（全历史会只剩最近 100 个交易日）
                count=10000,
                start_time=start_ms,
                end_time=end_ms,
                adjust=adjust,
            )
        except Exception as e:
            raise RuntimeError(f"tickflow 查询 {symbol}({tf_symbol}) 失败: {e}")

        ts = (data or {}).get('timestamp')
        if not ts:
            return pd.DataFrame()

        # UTC 毫秒 → 北京日期（当天零点）
        idx = (pd.to_datetime(pd.Series(ts), unit='ms')
               + pd.Timedelta(hours=8)).dt.normalize()
        idx.name = 'date'

        df = pd.DataFrame({
            'open': data['open'],
            'high': data['high'],
            'low': data['low'],
            'close': data['close'],
            'volume': [v * 100 for v in data['volume']],   # 手 → 股
            'amount': data['amount'],
        }, index=idx)

        for col in self.BAOSTOCK_BASE_FIELDS:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df

    # ── 通达信数据源（本机 TQ 版客户端，仅 Windows）────────────────

    # 通达信 get_market_data 字段名 → qka 标准列名
    TDX_FIELD_MAP = {
        'Open': 'open', 'High': 'high', 'Low': 'low',
        'Close': 'close', 'Volume': 'volume', 'Amount': 'amount',
    }

    def _get_from_tdx(
        self, symbol: str,
        start_date: str = '1990-01-01',
        end_date: str = '2050-12-31',
        extra_fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        从本机「支持 TQ 策略」的通达信客户端获取单只标的的日线数据。

        返回结构与 _get_from_baostock 一致（date 索引 + open/high/low/close/
        volume/amount），两处口径在本源内直接对齐：
        - **volume**：通达信给的就是「股」，与 baostock 口径一致，原样使用
        - **amount**：通达信单位是「万元」，×10000 换算成「元」

        复权由通达信自己按 dividend_type 算好（front=前复权 / back=后复权 /
        none=不复权），本处只做口径映射，不自行计算复权。

        取数前必须先 ``refresh_kline``：通达信本地只存「下载过」的 K 线，直接查
        没下载过的标的只会得到最新一根（历史静默缺失）。refresh_kline 让客户端
        把该标的的 K 线补齐，本地已有时也会很快返回。

        extra_fields 对通达信行情无意义（当前仅接行情，无扩展列），此处不处理。
        """
        # 周期映射（当前仅日线）
        period_map = {'1d': '1d'}
        if self.period not in period_map:
            raise RuntimeError(
                f"tdx 源暂不支持周期 {self.period!r}（可选: {list(period_map)}）"
            )

        # 复权映射：通达信 front=前复权 / back=后复权 / none=不复权
        adjust_map = {'bfq': 'none', 'qfq': 'front', 'hfq': 'back'}
        dividend_type = adjust_map.get(self.adjust, 'front')

        tdx_symbol = self.to_tdx_symbol(symbol)
        tq = tdx.get_tq()

        # 通达信只认 YYYYMMDD
        start = pd.Timestamp(start_date).strftime('%Y%m%d')
        end = pd.Timestamp(end_date).strftime('%Y%m%d')

        # 先让客户端补齐该标的的 K 线（失败返回 None），否则历史会静默缺失
        if tq.refresh_kline(stock_list=[tdx_symbol],
                            period=period_map[self.period]) is None:
            raise RuntimeError(
                f"通达信刷新 K 线缓存失败（{tdx_symbol}）："
                "请确认「TQ 版通达信」客户端已启动并已登录。"
            )

        try:
            raw = tq.get_market_data(
                stock_list=[tdx_symbol],
                start_time=start,
                end_time=end,
                dividend_type=dividend_type,
                period=period_map[self.period],
            )
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"通达信查询 {symbol}({tdx_symbol}) 失败: {e}") from e

        # 无任何数据时返回空 dict
        if not raw:
            return pd.DataFrame()

        # 每张字段表都是「日期为索引、列为代码」的宽表，只取当前这一列
        cols = {}
        for src, dst in self.TDX_FIELD_MAP.items():
            tbl = raw.get(src)
            if tbl is None or tdx_symbol not in getattr(tbl, 'columns', []):
                return pd.DataFrame()
            cols[dst] = tbl[tdx_symbol]

        df = pd.DataFrame(cols)
        df.index = pd.DatetimeIndex(df.index)
        df.index.name = 'date'
        df['amount'] = df['amount'] * 10000            # 万元 → 元
        df = df[df['close'].notna()]                   # 去掉多标的并集索引带出的空行
        df = df[~df.index.duplicated(keep='last')].sort_index()
        for col in self.BAOSTOCK_BASE_FIELDS:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
