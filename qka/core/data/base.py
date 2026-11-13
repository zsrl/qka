from __future__ import annotations

import contextlib
import hashlib
import inspect
import io
import json
import os
import textwrap
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, List, Optional, Union

import dask.dataframe as dd
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm

from qka.core import indicator, tdx
from qka.core.simulate import Simulate
from qka.utils.logger import logger

from ._common import (
    _QKA_BUILTIN_NAMES, _accepts_rf, _callable_source, _is_qka_factor,
    _key_fingerprint, _rf_given_positionally, get_tickflow_api_key,
)

from .cache import CacheMixin
from .factors import FactorMixin
from .sources.baostock import BaostockMixin
from .sources.sim import SimMixin
from .sources.tdx import TdxMixin
from .sources.tickflow import TickflowMixin


class Data(TickflowMixin, BaostockMixin, TdxMixin, SimMixin,
           CacheMixin, FactorMixin):
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
        cache_only: bool = False,
        risk_free: Optional[Union[float, "pd.Series"]] = None,
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

            cache_only: **只读本地缓存，绝不发起网络请求**（默认 False）。
                纯读场景（回测、看报告、批量分析）请显式传 True —— 否则缓存不全时
                会悄悄联网去补，既慢又不可控。缓存缺失时直接抛 RuntimeError 并列出
                缺哪些标的，不会静默返回半截数据。

            risk_free: **无风险利率（年化，小数）**，供 α / 夏普等需要它的因子使用。
                不传 → 因子沿用各自默认值（α、夏普均为 0，与老版本行为一致）。
                两种写法：

                - **标量**：`0.02` —— 全程一个数，简洁但不含时变性
                - **序列**：带日期索引的 `pd.Series`，如中债国债到期收益率曲线。
                  因子会取**每个窗口内的平均值**（见 indicator._rf_window_mean）。

                  用的是**短期**国债收益率：长期国债含期限溢价、中途卖出还有价格
                  风险，严格说不构成「无风险」，所以不按窗口长度去配长端曲线。

                ```python
                y1 = pd.read_csv('cn_bond_yield.csv', index_col='date', parse_dates=True)['y1'] / 100
                data = Data(symbols=['600519.SH'], benchmark='000300.SH',
                            factors={'alpha_1y': ('qka.alpha', 250)}, risk_free=y1)
                ```

        注：现值货币时间价值一律按**年化口径**参与运算 —— 因为 α 公式里的 Rp、Rm
        都是「窗口均值 × 252」，rf 必须站在同一个量纲上，不要先除以 252。

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
        # 因子现在写进行情文件本身（因子就是行情表的一列），所以一票只读写一次。
        # {symbol: (DataFrame, {因子名: 元数据})} —— 一次取数流程内复用，不跨流程持久化。
        self._quote_cache = {}
        # 停牌日按前收填充：默认关。见 _fill_suspended_prices
        self.fill_suspended = bool(fill_suspended)
        # 只读模式：一次网络请求都不发（见 _needs_download / get 的缓存校验）
        self.cache_only = bool(cache_only)
        # 无风险利率：标量或带日期索引的序列，供 α / 夏普使用。
        # None = 不传，因子各自用默认值（老行为不变）
        self.risk_free = risk_free

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

        # 只读模式：先把缓存齐不齐查一遍，缺的直接报错 —— 绝不退回联网。
        if self.cache_only:
            needed = list(self._real_symbols)
            if self.benchmark and self.benchmark not in needed:
                needed.append(self.benchmark)
            missing = [s for s in needed
                       if not (self.target_dir / f"{s}.parquet").exists()]
            if missing:
                preview = '、'.join(missing[:8])
                more = f' 等共 {len(missing)} 只' if len(missing) > 8 else ''
                raise RuntimeError(
                    f"cache_only=True，但本地没有这些标的的缓存：{preview}{more}。"
                    f" 先取数补齐，或改用 cache_only=False。"
                )

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
            # tickflow 有批量接口：先用一次请求把落后的票批量补上，剩下补不齐的
            # （首次建缓存 / 前复权要整段重取 / 缓存缺扩展列）才逐只下载。
            # 日常调用通常只落后一两天，这一段能把 N 次请求压到几次。
            if need_download and self.source == 'tickflow':
                need_download = self._prefetch_latest(
                    need_download, download_start, download_end)

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
                    ddf = self._strip_factor_cols(
                        dd.read_parquet(str(parquet_path), filters=pq_filters),
                        parquet_path)
                ddf['returns'] = ddf['close'].diff() / ddf['close'].shift(1)
                ddf = self._drop_head_lazy(ddf)
                # 🚨 因子不在这里算 —— 要等基准注入之后统一算（见下方 _apply_all_factors）。
                #    原因：内置因子和自定义因子没有本质区别，都可能是「相对基准」的，
                #    唯一合理的位置是「拿到基准之后」，而不是分两处、按两种时机各算一遍。
                column_mapping = {col: f'{symbol}|{col}' for col in ddf.columns}
                dfs.append(ddf.rename(columns=column_mapping))

            if not dfs:
                raise RuntimeError(
                    f"所有股票数据加载失败（共 {len(self.symbols)} 只），"
                    f"请检查网络连接和股票代码是否正确"
                )

            ddf = dd.concat(dfs, axis=1, join='outer')

            # 基准数据（必须在算因子之前 —— 因子可能需要它）
            if self.benchmark:
                ddf = self._add_benchmark(ddf, self.target_dir, pq_filters)

            # 所有因子，一处计算：内置 / ta / 自定义一视同仁
            ddf = self._apply_all_factors(ddf)

            # 切片回用户请求的日期范围（去掉指标预热扩展部分）——
            # 必须放在算因子之后：因子要吃掉预热那段数据，切早了窗口就不够长。
            if start_date is not None and max_window > 0:
                cutoff = pd.Timestamp(start_date)
                ddf = ddf.loc[cutoff:]

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
                    df = self._strip_factor_cols(
                        dd.read_parquet(str(parquet_path), filters=pq_filters),
                        parquet_path)
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

            # 基准数据（必须在算因子之前 —— 因子可能需要它）
            if self.benchmark:
                result = self._add_benchmark(result, self.target_dir, pq_filters)

            # 所有因子，一处计算：内置 / ta / 自定义一视同仁（带缓存）
            # 注意仍在切片之前：此时还带着预热数据，滚动窗口才够长。
            result = self._all_factors_with_cache(result)

            # 切片回用户请求的日期范围
            if start_date is not None and max_window > 0:
                result = result[result.index >= pd.Timestamp(start_date)]

            # 列顺序复原，与重构前一致
            return self._order_columns(result, self._qka_factor_names())


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
            # 🚨 起点往前多留 5 天，**不要**用 cache_max+1：
            #    TickFlow 对「单日区间」会返回空数据（2026-10-20 实测：
            #    _fetch('2026-10-20','2026-10-20') → 0 行；
            #    _fetch('2026-10-19','2026-10-20') → 正常 1 行）。
            #    只补一个紧邻交易日时就是单日区间 ⇒ 增量永远静默取空。
            #    跨周末/长假时区间自然多天，所以这个坑一直没暴露。
            #    多取的几天下面靠 drop_duplicates(keep='last') 去掉，代价可以忽略。
            start_after = (cache_max - pd.Timedelta(days=5)).strftime("%Y-%m-%d")
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
            # 问过了，数据源这段确实没有新数据；不改动缓存文件，直接返回。
            return path

        if changed:
            combined = pd.concat(pieces)
            combined = combined[~combined.index.duplicated(keep='last')]
            combined = combined.sort_index()
            # 🚨 因子列是派生数据，必须在合并后补回旧值：
            #    增量取数会往前多要 5 天（见上面的 start_after），那些新行只有行情列。
            #    keep='last' 之后，重叠日期的因子值会被新行的空值覆盖 —— 不补的话，
            #    每天更新都会悄悄抹掉最近几天的因子，而且完全看不出来。
            combined = self._restore_factor_columns(combined, existing, path)
            table = pa.Table.from_pandas(combined)
        else:
            table = pa.Table.from_pandas(existing)  # 数据没动，只是要更新「已确认起点」

        if verified_from is not None:
            self._write_verified_from(path, table, verified_from)
        else:
            pq.write_table(table, path)
        return path


    def _prefetch_latest(
        self, symbols: List[str], download_start: str = None,
        download_end: str = None,
    ) -> List[str]:
        """先用批量接口把缓存补上，返回**仍需逐只下载**的票。

        这是 `get()` 下载前的预热：绝大多数日常调用只是「缓存落后一两天」，
        一次批量请求就能补齐，不必每只各发一个请求。

        **取数区间由缓存自己决定，不拍条数：**
          起点 = 这批票里最早的缓存末日 − 5 天（与 `_download` 的 start_after 同口径）
          终点 = 请求的 end_date（None 则到今天）

        前复权不做增量（历史会被分红送股改写），整批原样返回，交给 `_download`
        整段重取。

        Args:
            symbols: 待下载的标的
            download_start / download_end: 本次请求范围，与 `_download` 同义

        Returns:
            List[str]: 仍需逐只下载的标的
        """
        if not self.incremental:
            return list(symbols)

        # 起点取决于「本地最旧的那只补到哪天」。读各票末日只读一列，几百只
        # 一两秒，比多发几百个请求便宜得多。
        no_cache = set()          # 本地根本没有缓存文件 —— 这类必须逐只建文件
        lasts = []
        for s in symbols:
            p = self.target_dir / f"{s}.parquet"
            if not p.exists():
                no_cache.add(s)
                continue
            try:
                idx = pd.read_parquet(p, columns=['close']).index
                lasts.append(pd.to_datetime(idx).max())
            except Exception:
                no_cache.add(s)   # 读不出来当没有缓存，交给逐只重建
                continue
        if not lasts:
            return list(symbols)

        start = (min(lasts) - pd.Timedelta(days=5)).strftime('%Y-%m-%d')
        end = download_end or pd.Timestamp.now().floor('D').strftime('%Y-%m-%d')
        if pd.Timestamp(start) > pd.Timestamp(end):
            return [s for s in symbols if s in no_cache]

        # 🚨 批量失败必须重试批量，**绝不回落逐只**（2026-11-13 定）。
        #    以前这里是 `return list(symbols)`：整批 500 只一次性推去逐只 =
        #    500 次请求，必然把 60 次/分钟的限流打爆。实测代价：
        #    一天的取数从 9 分钟被拖到 64 分钟，日志里 40 次限流退避。
        #    现在退避重试 3 次；全失败就抛出去让上层整批重来，也不逐只。
        bars_map = None
        last_err = None
        for attempt, wait in enumerate((10, 30, 60), start=1):
            try:
                bars_map = self._get_many_from_tickflow(symbols, start, end)
                break
            except Exception as e:
                last_err = e
                logger.warning(
                    f"批量补数第 {attempt} 次失败（{wait}s 后重试批量，不回落逐只）：{e}")
                time.sleep(wait)
        if bars_map is None:
            raise RuntimeError(f"批量补数连续 3 次失败：{last_err}") from last_err

        for s, bars in bars_map.items():
            try:
                self._append_bars(s, bars)
            except Exception as e:
                # 单只写盘失败不带崩整批，也不因此把它推去逐只 —— 下次批量再补
                logger.warning(f"{s}: 批量补数写入失败（不逐只重试，下次再补）：{e}")

        # 补过之后重新问一遍：只把「本地根本没有缓存文件」的留下，那必须逐只建文件。
        # 🚨 有缓存但还缺数据的，**不逐只**：要么数据源本来就没有（退市 / 未上市 /
        #    可转债认购款代码），要么当天还没生成完。逐只去问结果一样，只会白烧
        #    限流额度。它们留给下一轮批量（下次日更）再补，不会丢。
        still = [s for s in symbols
                 if self._needs_download(s, download_start, download_end)]
        skip = [s for s in still if s not in no_cache]
        if skip:
            logger.warning(
                f"批量补数后仍有 {len(skip)} 只缺数据，按「数据源无此数据」跳过"
                f"（不逐只重试）：{', '.join(skip[:5])}"
                f"{' 等' if len(skip) > 5 else ''}")
        return [s for s in still if s in no_cache]


    def _needs_download(
        self, symbol: str,
        download_start: str = None,
        download_end: str = None,
    ) -> bool:
        """
        判断股票是否需要网络下载。
        缓存不存在、不覆盖请求范围、或需要拉最新数据时返回 True。

        纯读场景请传 cache_only=True（见构造函数），那样一次网络请求都不会发。
        """
        # 只读模式：不管缺不缺都不去网络（缺了由 get() 统一报错）
        if self.cache_only:
            return False

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

        # 无 end_date = 要一直要到今天：缓存末日早于今天就得问。
        # 这里曾经按「数据就绪时刻（17:00）」把一天切成两段，靠文件 mtime 判断
        # 「本时段问过没有」来省请求 —— 那是个坏设计：数据源实际就绪时间会飘到
        # 22:00 之后，17:05 问一次空之后就会被判定「问过了」，当天再也取不到。
        # 现在只做确定性判断，要不要联网交给调用方用 cache_only 显式声明。
        return cache_max < pd.Timestamp.now().floor('D')


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

    @classmethod
    def to_baostock_symbol(cls, symbol: str) -> str:
        """任意写法 → baostock 写法，如 sh.600519"""
        market, code = cls._split_symbol(symbol)
        return f"{market}.{code}"

    @classmethod

    @classmethod
    def to_tickflow_symbol(cls, symbol: str) -> str:
        """任意写法 → tickflow 写法，如 600519.SH"""
        market, code = cls._split_symbol(symbol)
        return f"{code}.{market.upper()}"

    @classmethod

    @classmethod
    def to_tdx_symbol(cls, symbol: str) -> str:
        """任意写法 → 通达信写法，如 600519.SH（与 tickflow 同形）"""
        return cls.to_tickflow_symbol(symbol)

