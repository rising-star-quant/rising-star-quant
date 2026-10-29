"""
Rising Star Trend Engine - RiskGuard Micro-Module
Calculates dynamic ATR-based stop losses, asymmetric profit targets, and capital position sizing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional
from core.indicatorengine import TechnicalIndicators

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskPlan:
    """Comprehensive risk management and trade execution plan."""
    ticker: str
    entry_price: float
    stop_loss: float
    risk_per_share: float
    risk_pct: float
    target_2r: float
    target_3r: float
    target_5r: float
    suggested_shares_1k_risk: int
    is_favorable_rr: bool
    notes: str


class RiskGuard:
    """
    Enforces asymmetric risk-reward asymmetry (minimum 2:1 up to 5:1).
    Dynamic stop loss adapts to ATR and the 50-day moving average.
    """

    def __init__(
        self,
        max_stop_loss_pct: float = 7.5,     # Never risk more than 7.5% from entry
        atr_multiplier: float = 2.0,        # 2x ATR cushion below entry
        portfolio_risk_budget: float = 1000.0, # Default $1,000 risk per position
    ):
        self.max_stop_loss_pct = max_stop_loss_pct
        self.atr_multiplier = atr_multiplier
        self.portfolio_risk_budget = portfolio_risk_budget

    def create_risk_plan(self, indicators: TechnicalIndicators) -> RiskPlan:
        entry = indicators.latest_close
        atr = indicators.atr14
        ma50 = indicators.ma50

        # Calculate potential stops:
        # 1. ATR Trailing Stop (entry - 2 * ATR)
        atr_stop = entry - (self.atr_multiplier * atr)

        # 2. Key Moving Average support stop (just below MA50)
        ma50_stop = ma50 * 0.985 if ma50 < entry else atr_stop

        # 3. Maximum percentage hard stop (e.g. entry * 0.925)
        max_hard_stop = entry * (1.0 - (self.max_stop_loss_pct / 100.0))

        # Select the tightest logical stop that does not choke natural market noise
        stop_loss = max(atr_stop, max_hard_stop)
        # If MA50 is close below entry, use it as structural pivot
        if ma50_stop > max_hard_stop and ma50_stop < entry:
            stop_loss = max(stop_loss, ma50_stop)

        risk_per_share = round(entry - stop_loss, 2)
        risk_pct = round((risk_per_share / entry) * 100.0, 2) if entry > 0 else 0.0

        # Asymmetric profit targets
        target_2r = round(entry + (2.0 * risk_per_share), 2)
        target_3r = round(entry + (3.0 * risk_per_share), 2)
        target_5r = round(entry + (5.0 * risk_per_share), 2)

        # Position sizing based on dollar risk budget
        shares = int(self.portfolio_risk_budget // risk_per_share) if risk_per_share > 0 else 0

        is_favorable_rr = risk_pct <= self.max_stop_loss_pct

        notes = (
            f"Dynamic stop at ${stop_loss:.2f} ({risk_pct}% risk). "
            f"Targets: 2R=${target_2r:.2f}, 3R=${target_3r:.2f}, 5R=${target_5r:.2f}."
        )

        return RiskPlan(
            ticker=indicators.ticker,
            entry_price=entry,
            stop_loss=round(stop_loss, 2),
            risk_per_share=risk_per_share,
            risk_pct=risk_pct,
            target_2r=target_2r,
            target_3r=target_3r,
            target_5r=target_5r,
            suggested_shares_1k_risk=shares,
            is_favorable_rr=is_favorable_rr,
            notes=notes,
        )
