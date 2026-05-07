"""
QKA 仓位管理模块

提供仓位计算工具，支持多种资金管理策略。
通过 `strategy.sizing.*()` 调用，自动获取 broker 的资金和持仓信息。
"""

from math import floor


class SizingAccessor:
    """
    仓位计算工具
    
    挂载在 Strategy.sizing 下，用于计算每次交易的股数。
    自动获取 Broker 的资金信息（cash、positions、total_value）。
    
    A 股最小交易单位 100 股，所有方法自动按手向下取整。
    """
    
    # A 股最小手数
    MIN_LOT = 100

    def __init__(self, broker):
        self._broker = broker

    def _round_lot(self, shares: float) -> int:
        """按手取整（向下），不足一手返回 0"""
        if shares < self.MIN_LOT:
            return 0
        return int(floor(shares / self.MIN_LOT) * self.MIN_LOT)

    def _validate_positive(self, value, name: str):
        if value <= 0:
            raise ValueError(f"{name} 必须为正数，got {value}")

    def _validate_non_negative(self, value, name: str):
        if value < 0:
            raise ValueError(f"{name} 不能为负数，got {value}")

    def _validate_range(self, value, lo, hi, name: str):
        if not (lo <= value <= hi):
            raise ValueError(f"{name} 必须在 [{lo}, {hi}] 范围内，got {value}")

    # ── 核心方法 ──

    def fixed_shares(self, n: int) -> int:
        """
        固定股数。
        
        如果 n 不足一手（100股），返回 0。
        
        Args:
            n: 股数
        
        Returns:
            int: 按手取整后的股数
        """
        self._validate_positive(n, 'n')
        return self._round_lot(n)

    def fixed_amount(self, amount: float, price: float) -> int:
        """
        固定金额。
        
        计算 amount 能买多少股，向下按手取整。
        
        Args:
            amount: 投入金额
            price: 每股价格
        
        Returns:
            int: 可买入股数（按手取整）
        """
        self._validate_positive(amount, 'amount')
        self._validate_positive(price, 'price')
        return self._round_lot(amount / price)

    def percent(self, ratio: float, price: float) -> int:
        """
        资金百分比。
        
        使用可用现金的 ratio 比例买入，按手取整。
        
        Args:
            ratio: 0~1 之间的比例，如 0.1 表示 10%
            price: 每股价格
        
        Returns:
            int: 可买入股数
        """
        self._validate_range(ratio, 0, 1, 'ratio')
        self._validate_positive(price, 'price')
        if self._broker.cash <= 0:
            return 0
        return self._round_lot(self._broker.cash * ratio / price)

    def atr_risk(self, risk_ratio: float, price: float, atr_value: float,
                 multiplier: float = 2.0) -> int:
        """
        ATR 风险仓位。
        
        基于 ATR（平均真实波幅）计算仓位，确保单笔亏损不超过 risk_ratio 比例。
        
        公式：股数 = (cash * risk_ratio) / (atr_value * multiplier)
        
        Args:
            risk_ratio: 0~1，单笔最大亏损占资金比例
            price: 每股价格
            atr_value: ATR 当前值
            multiplier: 止损倍数，默认 2（即止损位为入场价 ± 2 * ATR）
        
        Returns:
            int: 可买入股数
        """
        self._validate_range(risk_ratio, 0, 1, 'risk_ratio')
        self._validate_positive(price, 'price')
        self._validate_non_negative(atr_value, 'atr_value')
        self._validate_positive(multiplier, 'multiplier')
        if self._broker.cash <= 0 or atr_value <= 0:
            return 0
        risk_per_share = atr_value * multiplier
        if risk_per_share <= 0:
            return 0
        return self._round_lot(self._broker.cash * risk_ratio / risk_per_share)

    def kelly(self, win_rate: float, win_loss_ratio: float, price: float) -> int:
        """
        凯利公式。
        
        f* = (p * b - q) / b
        
        其中：
        - p = 胜率
        - b = 赔率（盈利/亏损）
        - q = 1 - p（败率）
        
        当 f* ≤ 0 时返回 0（不建议下注）。
        
        Args:
            win_rate: 胜率，0~1
            win_loss_ratio: 赔率（平均盈利 / 平均亏损）
            price: 每股价格
        
        Returns:
            int: 可买入股数
        """
        self._validate_range(win_rate, 0, 1, 'win_rate')
        self._validate_positive(win_loss_ratio, 'win_loss_ratio')
        self._validate_positive(price, 'price')
        if self._broker.cash <= 0:
            return 0
        p = win_rate
        b = win_loss_ratio
        q = 1 - p
        fraction = (p * b - q) / b
        if fraction <= 0:
            return 0
        return self._round_lot(self._broker.cash * fraction / price)
