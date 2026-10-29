"""
Unit test suite for the Rising Star Trend Engine micro-modules.
Covers: DataConnector, RuleEngine, IndicatorEngine, ScoringEngine, RiskGuard, NotificationHub.
"""

from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from core.dataconnector import DataConnector, MarketData
from core.ruleengine import RuleEngine
from core.indicatorengine import IndicatorEngine
from core.scoringengine import ScoringEngine
from core.riskguard import RiskGuard
from core.notificationhub import NotificationHub


@pytest.fixture
def sample_market_data():
    """Generates 60 bars of synthetic market data."""
    dates = pd.date_range(end="2026-10-29", periods=60, freq="B")
    closes = [100.0 + i * 1.0 for i in range(60)] # Latest = 159.0
    highs = [c + 2.0 for c in closes]             # Latest high = 161.0
    lows = [c - 2.0 for c in closes]
    volumes = [1_000_000 + i * 10_000 for i in range(60)]
    volumes[-1] = 2_500_000 # Volume surge on last day

    return MarketData(
        ticker="NVDA",
        timestamp=pd.Timestamp.utcnow(),
        close_prices=closes,
        high_prices=highs,
        low_prices=lows,
        volumes=volumes,
        latest_close=closes[-1],
        latest_volume=volumes[-1],
        market_cap=2_500_000_000_000.0,
        public_float=24_000_000_000.0,
        net_income_q1=14_000_000_000.0,
        net_income_ttm=50_000_000_000.0,
        short_interest_pct=0.012,
        avg_volume_10d=1_500_000.0,
    )


class TestDataConnector:
    def test_dataconnector_fetch_success(self):
        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        mock_df = pd.DataFrame(
            {
                "Close": [100.0] * 30,
                "High": [105.0] * 30,
                "Low": [95.0] * 30,
                "Volume": [1_000_000] * 30,
            }
        )
        mock_ticker.history.return_value = mock_df
        mock_ticker.info = {"marketCap": 10_000_000_000.0, "netIncomeToCommon": 500_000_000.0}
        mock_yf.Ticker.return_value = mock_ticker

        connector = DataConnector(max_retries=1, backoff_factor=0.01, yf_module=mock_yf)
        data = connector.fetch_ticker_data("AAPL")

        assert data is not None
        assert data.ticker == "AAPL"
        assert len(data.close_prices) == 30
        assert data.latest_close == 100.0
        assert data.market_cap == 10_000_000_000.0

    def test_dataconnector_handles_missing_ticker(self):
        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_yf.Ticker.return_value = mock_ticker

        connector = DataConnector(max_retries=1, backoff_factor=0.01, yf_module=mock_yf)
        assert connector.fetch_ticker_data("UNKNOWN") is None


class TestRuleEngine:
    def test_qualifying_ticker_passes_rules(self, sample_market_data):
        rule_engine = RuleEngine(min_market_cap=1_000_000_000.0)
        res = rule_engine.evaluate(sample_market_data)

        assert res.is_eligible is True
        assert len(res.failed_rules) == 0
        assert len(res.passed_rules) >= 4

    def test_negative_earnings_violates_sp_rule(self, sample_market_data):
        unprofitable_data = MarketData(
            ticker="SPEC",
            timestamp=sample_market_data.timestamp,
            close_prices=sample_market_data.close_prices,
            high_prices=sample_market_data.high_prices,
            low_prices=sample_market_data.low_prices,
            volumes=sample_market_data.volumes,
            latest_close=100.0,
            latest_volume=1_000_000,
            market_cap=2_000_000_000.0,
            public_float=50_000_000.0,
            net_income_ttm=-50_000_000.0, # Negative
        )
        rule_engine = RuleEngine()
        res = rule_engine.evaluate(unprofitable_data)

        assert res.is_eligible is False
        assert any("Negative TTM Earnings" in f for f in res.failed_rules)


class TestIndicatorEngine:
    def test_indicator_calculations(self, sample_market_data):
        engine = IndicatorEngine()
        indicators = engine.calculate(sample_market_data)

        assert indicators.latest_close == 159.0
        assert indicators.ma20 > 0
        assert indicators.ma50 > 0
        assert indicators.is_above_ma50 is True
        assert indicators.is_20d_high_breakout is True
        assert indicators.volume_surge_10d > 1.2
        assert indicators.is_volume_expansion is True
        assert indicators.atr14 > 0


class TestScoringEngine:
    def test_scoring_high_momentum(self, sample_market_data):
        ind_engine = IndicatorEngine()
        indicators = ind_engine.calculate(sample_market_data)

        score_engine = ScoringEngine()
        score = score_engine.calculate_score(sample_market_data, indicators)

        assert score.total_score >= 80
        assert score.tier == "STRONG_RISING_STAR"
        assert score.momentum_score >= 30


class TestRiskGuard:
    def test_risk_plan_calculation(self, sample_market_data):
        ind_engine = IndicatorEngine()
        indicators = ind_engine.calculate(sample_market_data)

        guard = RiskGuard(max_stop_loss_pct=7.5, portfolio_risk_budget=1000.0)
        plan = guard.create_risk_plan(indicators)

        assert plan.stop_loss < plan.entry_price
        assert plan.risk_pct <= 7.5
        assert plan.target_2r > plan.entry_price
        assert plan.target_3r > plan.target_2r
        assert plan.target_5r > plan.target_3r
        assert plan.suggested_shares_1k_risk > 0


class TestNotificationHub:
    @patch("requests.post")
    def test_send_alert_dispatches_telegram(self, mock_post, sample_market_data):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        ind_engine = IndicatorEngine()
        indicators = ind_engine.calculate(sample_market_data)

        score_engine = ScoringEngine()
        score = score_engine.calculate_score(sample_market_data, indicators)

        guard = RiskGuard()
        plan = guard.create_risk_plan(indicators)

        hub = NotificationHub(bot_token="FAKE_BOT_TOKEN", chat_id="FAKE_CHAT_ID")
        assert hub.is_configured is True

        success = hub.send_alert(score, indicators, plan)
        assert success is True
        assert mock_post.called

    def test_unconfigured_hub_simulates_without_crashing(self, sample_market_data):
        hub = NotificationHub(bot_token=None, chat_id=None)
        assert hub.is_configured is False
        # Should return False and log locally without crashing
        assert hub.send_message("Test message") is False
