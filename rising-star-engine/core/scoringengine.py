"""
Rising Star Trend Engine - ScoringEngine Micro-Module
Calculates a unified multi-factor score from 0 to 100 based on momentum, volume, and fundamentals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List
from core.dataconnector import MarketData
from core.indicatorengine import TechnicalIndicators

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoreResult:
    """Comprehensive score breakdown and tier assignment."""
    ticker: str
    total_score: int  # 0 to 100
    tier: str         # 'STRONG_RISING_STAR', 'EMERGING_CANDIDATE', 'WATCHLIST', 'AVOID'
    momentum_score: int  # Max 35
    volume_score: int    # Max 25
    fundamental_score: int # Max 20
    volatility_score: int  # Max 20
    summary: str
    factors: Dict[str, int] = field(default_factory=dict)


class ScoringEngine:
    """
    Weighted 100-point scoring algorithm for ranking market momentum leaders.
    """

    def calculate_score(self, data: MarketData, indicators: TechnicalIndicators) -> ScoreResult:
        factors: Dict[str, int] = {}

        # 1. Momentum & Breakout (Max 35 points)
        momentum_score = 0
        if indicators.is_20d_high_breakout:
            momentum_score += 20
            factors["20d_high_breakout"] = 20
        elif indicators.distance_to_20d_high_pct >= -3.0:
            momentum_score += 15
            factors["within_3pct_20d_high"] = 15
        elif indicators.distance_to_20d_high_pct >= -6.0:
            momentum_score += 10
            factors["within_6pct_20d_high"] = 10

        if indicators.is_above_ma50:
            momentum_score += 10
            factors["above_ma50"] = 10

        if indicators.is_trend_aligned:
            momentum_score += 5
            factors["trend_aligned"] = 5

        # 2. Institutional Volume Surge (Max 25 points)
        volume_score = 0
        surge = indicators.volume_surge_10d
        if surge >= 2.0:
            volume_score = 25
            factors["huge_volume_surge_2x"] = 25
        elif surge >= 1.5:
            volume_score = 20
            factors["strong_volume_surge_1.5x"] = 20
        elif surge >= 1.2:
            volume_score = 15
            factors["above_avg_volume_1.2x"] = 15
        elif surge >= 1.0:
            volume_score = 10
            factors["normal_volume_1.0x"] = 10
        else:
            factors["below_avg_volume"] = 0

        # 3. Fundamental Strength (Max 20 points)
        fundamental_score = 0
        if data.net_income_ttm and data.net_income_ttm > 0:
            fundamental_score += 10
            factors["positive_ttm_earnings"] = 10
        if data.net_income_q1 and data.net_income_q1 > 0:
            fundamental_score += 5
            factors["positive_mrq_earnings"] = 5
        if data.market_cap and data.market_cap >= 2_000_000_000:
            fundamental_score += 5
            factors["solid_mid_large_cap"] = 5

        # 4. Volatility & Base Tightness (Max 20 points)
        volatility_score = 0
        atr_pct = indicators.atr_pct
        if atr_pct <= 3.5:
            volatility_score = 20
            factors["tight_base_low_atr"] = 20
        elif atr_pct <= 5.0:
            volatility_score = 15
            factors["controlled_volatility"] = 15
        elif atr_pct <= 7.0:
            volatility_score = 10
            factors["moderate_volatility"] = 10
        else:
            volatility_score = 5
            factors["high_volatility"] = 5

        total_score = min(100, momentum_score + volume_score + fundamental_score + volatility_score)

        if total_score >= 80:
            tier = "STRONG_RISING_STAR"
            summary = f"🔥 Prime breakout leader ({total_score}/100) with explosive volume and trend alignment."
        elif total_score >= 65:
            tier = "EMERGING_CANDIDATE"
            summary = f"⚡ Emerging momentum candidate ({total_score}/100) approaching critical breakout pivot."
        elif total_score >= 50:
            tier = "WATCHLIST"
            summary = f"👀 Consolidation watch ({total_score}/100). Needs stronger volume expansion."
        else:
            tier = "AVOID"
            summary = f"❌ Low momentum score ({total_score}/100). Does not satisfy trend criteria."

        return ScoreResult(
            ticker=data.ticker,
            total_score=total_score,
            tier=tier,
            momentum_score=momentum_score,
            volume_score=volume_score,
            fundamental_score=fundamental_score,
            volatility_score=volatility_score,
            summary=summary,
            factors=factors,
        )
