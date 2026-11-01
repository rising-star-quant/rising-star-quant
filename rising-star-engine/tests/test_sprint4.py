"""
Unit tests for Rising Star Trend Engine - Sprint 4: Full Market Integration, Automation & Execution Logic.
Covers:
1. S&P 500 constituent retrieval, local caching, and BatchMarketScanner.
2. 14-day ATR volatility calculation, dynamic stop-loss, profit targets, and position sizing.
3. Telegram NotificationHub Buy Alert cards and daily summary digest generation.
"""

from datetime import datetime
import os
import pytest

from core.universe import BatchMarketScanner, fetch_sp500_tickers, FALLBACK_SP500_TICKERS, chunk_list
from core.riskguard import RiskGuard, RiskPlan
from core.notificationhub import NotificationHub
from core.scoringengine import (
    ScorePayload,
    ScoreFactorBreakdown,
    GatekeeperResult,
)
from core.indicatorengine import (
    IndicatorMetrics,
    TechnicalTrend,
    VolumeMetrics,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def mock_ohlcv_data():
    """Generates 30 bars of price data for volatility and ATR calculations."""
    closes = [100.0 + i for i in range(30)]
    highs = [c + 2.5 for c in closes]
    lows = [c - 2.0 for c in closes]
    volumes = [1_000_000 + (i * 20_000) for i in range(30)]
    return {"highs": highs, "lows": lows, "closes": closes, "volumes": volumes}


@pytest.fixture
def sample_score_payload():
    return ScorePayload(
        ticker="CRWD",
        rising_star_score=91.5,
        tier="STRONG_RISING_STAR",
        is_buy_alert=True,
        breakout_triggered=True,
        is_sp_eligible=True,
        factor_breakdown=ScoreFactorBreakdown(
            technical_score=38.0,
            volume_score=28.5,
            sector_score=17.0,
            short_interest_score=8.0,
            raw_total=91.5,
        ),
        gatekeeper=GatekeeperResult(
            total_signals=20,
            winning_signals=14,
            losing_signals=6,
            win_rate=0.70,
            profit_factor=2.45,
            gatekeeper_approved=True,
        ),
        summary="High-conviction institutional momentum breakout.",
    )


@pytest.fixture
def sample_indicator_metrics():
    return IndicatorMetrics(
        ticker="CRWD",
        bars_processed=250,
        latest_close=320.0,
        latest_volume=3_500_000,
        resistance_20d=315.0,
        high_52w=322.0,
        distance_to_resistance_pct=1.59,
        distance_to_52w_high_pct=-0.62,
        breakout_triggered=True,
        breakout_type="20D_RESISTANCE",
        relative_sector_strength=14.2,
        technical_trend=TechnicalTrend(
            ma50=295.0,
            ma200=260.0,
            ma50_slope_20d=0.28,
            is_above_ma50=True,
            is_above_ma200=True,
            is_trend_aligned=True,
        ),
        volume_metrics=VolumeMetrics(
            up_day_avg_volume=3_200_000.0,
            down_day_avg_volume=1_800_000.0,
            up_down_volume_ratio=1.78,
            institutional_accumulation=True,
        ),
    )


# =====================================================================
# Test Suite 1: Universe & Batch Scanner
# =====================================================================

class TestUniverseIntegration:
    def test_fetch_sp500_tickers_fallback(self):
        tickers = fetch_sp500_tickers(cache_path="non_existent_cache.json", force_refresh=True)
        assert len(tickers) >= 50
        assert "NVDA" in tickers
        assert "PLTR" in tickers
        assert "AAPL" in tickers

    def test_chunk_list_helper(self):
        items = list(range(25))
        chunks = list(chunk_list(items, chunk_size=10))
        assert len(chunks) == 3
        assert len(chunks[0]) == 10
        assert len(chunks[1]) == 10
        assert len(chunks[2]) == 5

    def test_batch_market_scanner_resilience(self):
        scanner = BatchMarketScanner(batch_size=5, batch_delay_seconds=0.0)
        tickers = ["AAPL", "BAD_DATA", "NVDA", "FAIL_TICKER", "MSFT"]

        def mock_processor(t: str):
            if "BAD" in t:
                return None
            if "FAIL" in t:
                raise RuntimeError(f"Connection timed out for {t}")
            return {"ticker": t, "processed": True}

        results, stats = scanner.process_universe(tickers, mock_processor)

        assert stats["total_submitted"] == 5
        assert stats["successful_processed"] == 3
        assert stats["skipped_or_failed_count"] == 2
        assert len(results) == 3
        assert results[0]["ticker"] == "AAPL"
        assert results[1]["ticker"] == "NVDA"
        assert results[2]["ticker"] == "MSFT"


# =====================================================================
# Test Suite 2: Enhanced RiskGuard & Volatility Position Sizing
# =====================================================================

class TestRiskGuardPositionSizing:
    def test_compute_atr_14(self, mock_ohlcv_data):
        atr = RiskGuard.compute_atr(
            highs=mock_ohlcv_data["highs"],
            lows=mock_ohlcv_data["lows"],
            closes=mock_ohlcv_data["closes"],
            period=14,
        )
        assert atr > 0
        assert isinstance(atr, float)
        assert round(atr, 1) == 4.5

    def test_position_sizing_calculation(self, mock_ohlcv_data):
        guard = RiskGuard(
            default_account_equity=100_000.0,
            default_risk_per_trade_pct=1.0,  # 1% risk = $1,000 budget
            default_atr_multiplier=2.0,      # 2.0x ATR stop
            max_position_size_pct=20.0,      # Max $20,000 allocation
        )

        entry_price = 100.0
        plan = guard.compute_position_sizing(
            ticker="CRWD",
            entry_price=entry_price,
            highs=mock_ohlcv_data["highs"],
            lows=mock_ohlcv_data["lows"],
            closes=mock_ohlcv_data["closes"],
        )

        assert isinstance(plan, RiskPlan)
        assert plan.ticker == "CRWD"
        assert plan.entry_price == 100.0
        assert plan.atr_14 == 4.5
        # Stop loss = 100 - (4.5 * 2) = 91.0
        assert plan.stop_loss_price == 91.0
        assert plan.risk_distance_usd == 9.0
        assert plan.risk_pct == 9.0

        # Multi-target profit levels
        assert plan.target_1r == 109.0
        assert plan.target_2r == 118.0
        assert plan.target_3r == 127.0
        assert plan.target_5r == 145.0

        # Sizing: $1,000 / $9 = 111 shares
        assert plan.suggested_shares == 111
        assert plan.position_value_usd == 111 * 100.0
        assert plan.position_pct_of_account == 11.1
        assert plan.max_loss_usd <= 1_000.0

    def test_position_sizing_respects_capital_cap(self, mock_ohlcv_data):
        guard = RiskGuard(
            default_account_equity=100_000.0,
            default_risk_per_trade_pct=1.0,
            max_position_size_pct=20.0,
        )

        closes = [100.0] * 30
        highs = [100.2] * 30
        lows = [99.8] * 30

        plan = guard.compute_position_sizing(
            ticker="LOW_VOL",
            entry_price=100.0,
            highs=highs,
            lows=lows,
            closes=closes,
        )

        # Max allowed capital = $20,000 -> Max shares = 200
        assert plan.suggested_shares <= 200
        assert plan.position_value_usd <= 20_000.0
        assert plan.position_pct_of_account <= 20.0


# =====================================================================
# Test Suite 3: Telegram Alert Automation (NotificationHub)
# =====================================================================

class TestNotificationHub:
    def test_notification_hub_simulated_mode(self, sample_score_payload, sample_indicator_metrics, mock_ohlcv_data):
        hub = NotificationHub(bot_token=None, chat_id=None)
        assert hub.is_configured is False

        guard = RiskGuard()
        plan = guard.compute_position_sizing(
            ticker="CRWD",
            entry_price=320.0,
            highs=mock_ohlcv_data["highs"],
            lows=mock_ohlcv_data["lows"],
            closes=mock_ohlcv_data["closes"],
        )

        success = hub.send_buy_alert(
            ticker="CRWD",
            score=sample_score_payload,
            indicators=sample_indicator_metrics,
            risk=plan,
        )
        assert success is False

    def test_notification_hub_daily_digest(self):
        hub = NotificationHub(bot_token=None, chat_id=None)
        top_candidates = [
            {"ticker": "NVDA", "score": 94.2, "latest_close": 142.50, "is_buy_alert": True},
            {"ticker": "PLTR", "score": 88.0, "latest_close": 44.50, "is_buy_alert": True},
        ]

        success = hub.send_daily_digest(
            total_scanned=500,
            qualified_count=42,
            buy_alerts_count=2,
            top_candidates=top_candidates,
            elapsed_seconds=18.5,
        )
        assert success is False
