"""
Rising Star Trend Engine - Core Micro-Modules (Sprint 3: ScoringEngine & RiskGuard)
Strictly headless pure backend logic.
"""

from .dataconnector import DataConnector
from .ruleengine import RuleEngine, CompanyProfile, EligibilityResult
from .indicatorengine import IndicatorEngine, IndicatorMetrics, TechnicalTrend, VolumeMetrics
from .scoringengine import (
    ScoringEngine,
    ScorePayload,
    ScoreFactorBreakdown,
    HistoricalSignal,
    GatekeeperResult,
)
from .riskguard import RiskGuard, PositionState, RiskStatusPayload, RiskPlan
from .notificationhub import NotificationHub
from .universe import fetch_sp500_tickers, BatchMarketScanner, FALLBACK_SP500_TICKERS

__all__ = [
    "DataConnector",
    "RuleEngine",
    "CompanyProfile",
    "EligibilityResult",
    "IndicatorEngine",
    "IndicatorMetrics",
    "TechnicalTrend",
    "VolumeMetrics",
    "ScoringEngine",
    "ScorePayload",
    "ScoreFactorBreakdown",
    "HistoricalSignal",
    "GatekeeperResult",
    "RiskGuard",
    "PositionState",
    "RiskStatusPayload",
    "RiskPlan",
    "NotificationHub",
    "fetch_sp500_tickers",
    "BatchMarketScanner",
    "FALLBACK_SP500_TICKERS",
]

