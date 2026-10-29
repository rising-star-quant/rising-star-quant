"""
Unit tests for Rising Star Trend Engine - Sprint 3: ScoringEngine and RiskGuard.
Strictly headless backend verification covering:
- Multi-factor score weighting (40/30/20/10)
- BUY ALERT trigger validation (Score >= 85 AND breakout_triggered == True)
- Backtest Gatekeeper simulation (Profit Factor >= 1.2 AND Win Rate >= 50%)
- Trailing Stop-Loss exit (-10% from post-entry high)
- MA50 breakdown with volume confirmation (+20% surge)
- Time-based maximum holding limit (60 trading days)
"""

from datetime import datetime, timedelta
import pytest

from core.indicatorengine import IndicatorMetrics, TechnicalTrend, VolumeMetrics
from core.ruleengine import EligibilityResult
from core.scoringengine import (
    GatekeeperResult,
    HistoricalSignal,
    ScorePayload,
    ScoringEngine,
)
from core.riskguard import PositionState, RiskGuard, RiskStatusPayload


@pytest.fixture
def perfect_indicator_metrics() -> IndicatorMetrics:
    return IndicatorMetrics(
        ticker="NVDA",
        calculated_at=datetime.utcnow(),
        bars_processed=250,
        latest_close=145.0,
        latest_volume=65_000_000,
        resistance_20d=144.0,
        high_52w=144.0,
        distance_to_resistance_pct=0.7,
        distance_to_52w_high_pct=0.7,
        breakout_triggered=True,
        breakout_type="DUAL_BREAKOUT",
        relative_sector_strength=35.0,
        technical_trend=TechnicalTrend(
            ma50=130.0,
            ma200=115.0,
            ma50_slope_20d=0.35,
            is_above_ma50=True,
            is_above_ma200=True,
            is_trend_aligned=True,
        ),
        volume_metrics=VolumeMetrics(
            up_day_avg_volume=55_000_000.0,
            down_day_avg_volume=30_000_000.0,
            up_down_volume_ratio=1.83,
            institutional_accumulation=True,
        ),
    )


@pytest.fixture
def qualifying_historical_signals() -> list[HistoricalSignal]:
    return [
        HistoricalSignal(entry_price=100.0, exit_price=120.0),
        HistoricalSignal(entry_price=100.0, exit_price=115.0),
        HistoricalSignal(entry_price=100.0, exit_price=115.0),
        HistoricalSignal(entry_price=100.0, exit_price=110.0),
        HistoricalSignal(entry_price=100.0, exit_price=90.0),
        HistoricalSignal(entry_price=100.0, exit_price=80.0),
    ]


@pytest.fixture
def failing_historical_signals() -> list[HistoricalSignal]:
    return [
        HistoricalSignal(entry_price=100.0, exit_price=110.0),
        HistoricalSignal(entry_price=100.0, exit_price=90.0),
        HistoricalSignal(entry_price=100.0, exit_price=95.0),
        HistoricalSignal(entry_price=100.0, exit_price=95.0),
    ]


class TestScoringEngine:
    def test_high_score_with_breakout_triggers_buy_alert(
        self, perfect_indicator_metrics, qualifying_historical_signals
    ):
        engine = ScoringEngine(buy_score_threshold=85.0)
        payload = engine.calculate_score(
            indicators=perfect_indicator_metrics,
            short_interest_pct=0.05,
            historical_signals=qualifying_historical_signals,
        )

        assert isinstance(payload, ScorePayload)
        assert payload.rising_star_score >= 85.0
        assert payload.breakout_triggered is True
        assert payload.gatekeeper.gatekeeper_approved is True
        assert payload.is_buy_alert is True
        assert payload.tier == "STRONG_RISING_STAR"
        assert "BUY ALERT" in payload.summary

    def test_high_score_without_breakout_does_not_trigger_buy(
        self, perfect_indicator_metrics, qualifying_historical_signals
    ):
        non_breakout_metrics = perfect_indicator_metrics.model_copy(
            update={"breakout_triggered": False, "breakout_type": "NONE"}
        )

        engine = ScoringEngine(buy_score_threshold=85.0)
        payload = engine.calculate_score(
            indicators=non_breakout_metrics,
            short_interest_pct=0.05,
            historical_signals=qualifying_historical_signals,
        )

        assert payload.rising_star_score >= 85.0
        assert payload.breakout_triggered is False
        assert payload.is_buy_alert is False
        assert "Awaiting breakout confirmation" in payload.summary

    def test_gatekeeper_failure_suppresses_buy_alert(
        self, perfect_indicator_metrics, failing_historical_signals
    ):
        engine = ScoringEngine(
            buy_score_threshold=85.0,
            gatekeeper_min_profit_factor=1.2,
            gatekeeper_min_win_rate=0.50,
        )
        payload = engine.calculate_score(
            indicators=perfect_indicator_metrics,
            short_interest_pct=0.05,
            historical_signals=failing_historical_signals,
        )

        assert payload.rising_star_score >= 85.0
        assert payload.breakout_triggered is True
        assert payload.gatekeeper.gatekeeper_approved is False
        assert payload.gatekeeper.profit_factor < 1.2
        assert payload.gatekeeper.win_rate < 0.50
        assert payload.is_buy_alert is False
        assert "SUPPRESSED ALERT" in payload.summary

    def test_factor_weighting_normalization(self, perfect_indicator_metrics):
        engine = ScoringEngine()
        payload = engine.calculate_score(
            indicators=perfect_indicator_metrics,
            short_interest_pct=0.05,
        )

        bd = payload.factor_breakdown
        assert bd.technical_score <= 40.0
        assert bd.volume_score <= 30.0
        assert bd.sector_score <= 20.0
        assert bd.short_interest_score <= 10.0
        assert abs(payload.rising_star_score - (bd.technical_score + bd.volume_score + bd.sector_score + bd.short_interest_score)) < 1e-4

    def test_disqualified_by_rule_engine_yields_zero_score(self, perfect_indicator_metrics):
        mock_rule_fail = EligibilityResult(
            ticker="NVDA",
            is_eligible=False,
            criteria_checklist={"us_incorporation": False},
            failed_criteria=["U.S. Incorporation"],
            details={},
        )

        engine = ScoringEngine()
        payload = engine.calculate_score(
            indicators=perfect_indicator_metrics,
            rule_result=mock_rule_fail,
        )

        assert payload.rising_star_score == 0.0
        assert payload.is_sp_eligible is False
        assert payload.tier == "DISQUALIFIED"
        assert payload.is_buy_alert is False


@pytest.fixture
def standard_active_position() -> PositionState:
    return PositionState(
        ticker="PLTR",
        entry_date=datetime.utcnow() - timedelta(days=20),
        entry_price=40.0,
        shares=200,
        days_held=20,
        highest_high_post_entry=46.0,
        latest_close=44.5,
        latest_volume=30_000_000,
        ma50=38.0,
        avg_volume_50d=25_000_000.0,
    )


class TestRiskGuard:
    def test_normal_holding_position_holds(self, standard_active_position):
        guard = RiskGuard(trailing_stop_pct=10.0, max_holding_days=60)
        status = guard.evaluate_position(standard_active_position)

        assert isinstance(status, RiskStatusPayload)
        assert status.action == "HOLD"
        assert status.is_exit_triggered is False
        assert len(status.exit_reasons) == 0
        assert status.days_remaining == 40
        assert status.current_pnl_pct > 0

    def test_trailing_stop_exit_triggered(self, standard_active_position):
        breached_position = standard_active_position.model_copy(
            update={"latest_close": 40.50}
        )

        guard = RiskGuard(trailing_stop_pct=10.0)
        status = guard.evaluate_position(breached_position)

        assert status.is_exit_triggered is True
        assert status.action == "EXIT_TRAILING_STOP"
        assert status.trailing_stop_price == 41.40
        assert status.current_drawdown_from_peak_pct > 10.0
        assert any("Trailing Stop Breached" in r for r in status.exit_reasons)

    def test_ma50_breakdown_with_volume_triggers_exit(self, standard_active_position):
        breakdown_position = standard_active_position.model_copy(
            update={
                "latest_close": 37.50,
                "latest_volume": 35_000_000,
                "highest_high_post_entry": 41.0,
            }
        )

        guard = RiskGuard(trailing_stop_pct=10.0, ma_volume_surge_pct=20.0)
        status = guard.evaluate_position(breakdown_position)

        assert status.is_exit_triggered is True
        assert status.action == "EXIT_MA50_BREAKDOWN"
        assert any("MA50 Institutional Breakdown" in r for r in status.exit_reasons)

    def test_ma50_breakdown_without_volume_defers_exit(self, standard_active_position):
        light_vol_position = standard_active_position.model_copy(
            update={
                "latest_close": 37.50,
                "latest_volume": 18_000_000,
                "highest_high_post_entry": 41.0,
            }
        )

        guard = RiskGuard(trailing_stop_pct=10.0, ma_volume_surge_pct=20.0)
        status = guard.evaluate_position(light_vol_position)

        assert status.is_exit_triggered is False
        assert status.action == "HOLD"
        assert "ma50_warning" in status.risk_details

    def test_time_based_limit_60_days_triggers_exit(self, standard_active_position):
        expired_position = standard_active_position.model_copy(
            update={"days_held": 60}
        )

        guard = RiskGuard(max_holding_days=60)
        status = guard.evaluate_position(expired_position)

        assert status.is_exit_triggered is True
        assert status.action == "EXIT_TIME_LIMIT"
        assert status.days_remaining == 0
        assert any("Time Limit Expired" in r for r in status.exit_reasons)

    def test_multiple_exit_triggers_detected(self, standard_active_position):
        multi_exit_position = standard_active_position.model_copy(
            update={
                "days_held": 65,
                "latest_close": 35.0,
            }
        )

        guard = RiskGuard(trailing_stop_pct=10.0, max_holding_days=60)
        status = guard.evaluate_position(multi_exit_position)

        assert status.is_exit_triggered is True
        assert status.action == "EXIT_MULTIPLE_TRIGGERS"
        assert len(status.exit_reasons) >= 2
