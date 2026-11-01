"""
Rising Star Trend Engine - Core Micro-Modules
Strictly headless pure backend logic, Pydantic v2 validated.
"""

from .dataconnector import DataConnector, MarketData
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
from .backtester import BacktestEngine, BacktestConfig, BacktestTrade, BacktestResult, EquityCurvePoint
from .portfoliotracker import PortfolioTracker, PaperPosition, PortfolioSummary

__all__ = [
    "DataConnector",
    "MarketData",
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
    "BacktestEngine",
    "BacktestConfig",
    "BacktestTrade",
    "BacktestResult",
    "EquityCurvePoint",
    "PortfolioTracker",
    "PaperPosition",
    "PortfolioSummary",
]
