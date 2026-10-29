"""
Unit tests for Rising Star Trend Engine - Sprint 1: DataConnector and Domain Schemas.
Uses unittest.mock to mock external market data providers and yfinance responses.
"""

import logging
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from src.data_connector import DataConnector
from src.schemas import FinancialMetrics, MarketDataPayload, TechnicalMetrics


@pytest.fixture
def sample_history_df():
    """Generates 30 days of realistic synthetic OHLCV data."""
    dates = pd.date_range(end="2026-10-28", periods=30, freq="B")
    # Base close starts at 100 and rises towards 150
    close_vals = [100.0 + i * 1.5 for i in range(30)]
    high_vals = [c + 2.0 for c in close_vals]
    low_vals = [c - 2.0 for c in close_vals]
    open_vals = [c - 0.5 for c in close_vals]
    # Volumes between 1,000,000 and 2,000,000
    volume_vals = [1_000_000 + (i * 30_000) for i in range(30)]

    df = pd.DataFrame(
        {
            "Open": open_vals,
            "High": high_vals,
            "Low": low_vals,
            "Close": close_vals,
            "Volume": volume_vals,
        },
        index=dates,
    )
    return df


@pytest.fixture
def sample_fundamentals_info():
    """Generates standard corporate fundamental metrics dictionary."""
    return {
        "marketCap": 2_500_000_000.0,
        "floatShares": 85_000_000.0,
        "shortPercentOfFloat": 0.065,
        "averageDailyVolume10Day": 1_800_000.0,
        "netIncomeToCommon": 320_000_000.0,
    }


class TestDataConnector:
    """Test suite for DataConnector resilience and payload normalization."""

    def test_successful_payload_creation(self, sample_history_df, sample_fundamentals_info):
        """
        Verify that valid OHLCV and fundamental data produces a strictly-typed
        MarketDataPayload with accurate calculated technical metrics.
        """
        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = sample_history_df
        mock_ticker.info = sample_fundamentals_info

        # Mock quarterly financials dataframe
        mock_fin_df = pd.DataFrame(
            {"2026-06-30": [95_000_000.0]},
            index=["Net Income"],
        )
        mock_ticker.quarterly_financials = mock_fin_df
        mock_yf.Ticker.return_value = mock_ticker

        connector = DataConnector(max_retries=2, backoff_factor=0.01, yf_module=mock_yf)
        payload = connector.fetch_ticker_data("NVDA")

        assert payload is not None
        assert isinstance(payload, MarketDataPayload)
        assert payload.ticker == "NVDA"

        # Check technical metrics
        assert len(payload.technicals.close_prices) == 30
        assert len(payload.technicals.volumes) == 30
        assert payload.technicals.latest_close == sample_history_df["Close"].iloc[-1]
        assert payload.technicals.latest_volume == int(sample_history_df["Volume"].iloc[-1])

        # 20d High should match highest high in last 20 bars
        expected_20d_high = float(sample_history_df["High"].iloc[-20:].max())
        assert payload.technicals.highs_20d == expected_20d_high

        # 10d average volume
        expected_10d_vol = float(sample_history_df["Volume"].iloc[-10:].mean())
        assert abs(payload.technicals.avg_volume_10d - expected_10d_vol) < 1e-4

        # Check financial metrics
        assert payload.financials.market_cap == 2_500_000_000.0
        assert payload.financials.public_float == 85_000_000.0
        assert payload.financials.short_interest_pct == 0.065
        assert payload.financials.net_income_ttm == 320_000_000.0
        assert payload.financials.net_income_q1 == 95_000_000.0

        # Verify breakout helper properties
        assert payload.is_20d_high_breakout is True

    def test_missing_ticker_returns_none(self, caplog):
        """
        Verify that non-existent or empty ticker symbols return None gracefully
        and log an informative warning.
        """
        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()  # Empty dataframe
        mock_yf.Ticker.return_value = mock_ticker

        connector = DataConnector(max_retries=1, backoff_factor=0.01, yf_module=mock_yf)

        with caplog.at_level(logging.WARNING):
            result = connector.fetch_ticker_data("INVALID_TICKER")

        assert result is None
        assert any("No price history returned" in rec.message for rec in caplog.records)

    def test_blank_ticker_string_returns_none(self, caplog):
        """Empty or whitespace ticker string should be rejected immediately."""
        connector = DataConnector()
        with caplog.at_level(logging.WARNING):
            assert connector.fetch_ticker_data("") is None
            assert connector.fetch_ticker_data("   ") is None
        assert any("Invalid ticker symbol" in rec.message for rec in caplog.records)

    def test_insufficient_history_returns_none(self, caplog):
        """
        Tickers with fewer than 20 trading days cannot reliably compute 20d breakout
        metrics and should be logged and skipped.
        """
        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        short_df = pd.DataFrame(
            {
                "Close": [10.0] * 12,
                "High": [11.0] * 12,
                "Volume": [100_000] * 12,
            }
        )
        mock_ticker.history.return_value = short_df
        mock_yf.Ticker.return_value = mock_ticker

        connector = DataConnector(max_retries=1, backoff_factor=0.01, yf_module=mock_yf)
        with caplog.at_level(logging.WARNING):
            res = connector.fetch_ticker_data("NEW_IPO")

        assert res is None
        assert any("Insufficient history" in rec.message for rec in caplog.records)

    @patch("time.sleep")
    def test_rate_limit_retry_exponential_backoff(self, mock_sleep, sample_history_df, sample_fundamentals_info):
        """
        Verify that rate-limit errors (HTTP 429) trigger exponential backoff retries,
        recovering successfully if a subsequent attempt succeeds.
        """
        mock_yf = MagicMock()
        mock_ticker = MagicMock()

        # Simulate 2 consecutive 429 rate limit errors, then success on 3rd attempt
        mock_ticker.history.side_effect = [
            Exception("429 Client Error: Too Many Requests for url"),
            Exception("Rate limit exceeded. Please throttle requests."),
            sample_history_df,
        ]
        mock_ticker.info = sample_fundamentals_info
        mock_yf.Ticker.return_value = mock_ticker

        connector = DataConnector(
            max_retries=3,
            backoff_factor=0.5,
            jitter=False,
            yf_module=mock_yf,
        )

        payload = connector.fetch_ticker_data("AAPL")

        assert payload is not None
        assert payload.ticker == "AAPL"
        # Should have retried twice before succeeding on attempt 3
        assert mock_sleep.call_count == 2
        # Backoff: attempt 1 -> 0.5s, attempt 2 -> 1.0s
        mock_sleep.assert_any_call(0.5)
        mock_sleep.assert_any_call(1.0)

    @patch("time.sleep")
    def test_retry_exhaustion_returns_none(self, mock_sleep, caplog):
        """
        Verify that persistent errors exceeding max_retries return None gracefully
        and log a permanent failure warning without raising an unhandled exception.
        """
        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = Exception("429 Too Many Requests: Rate limit reached")
        mock_yf.Ticker.return_value = mock_ticker

        connector = DataConnector(
            max_retries=2,
            backoff_factor=0.1,
            jitter=False,
            yf_module=mock_yf,
        )

        with caplog.at_level(logging.WARNING):
            result = connector.fetch_ticker_data("TSLA")

        assert result is None
        assert mock_sleep.call_count == 2
        assert any("failed permanently" in rec.message for rec in caplog.records)

    def test_missing_fundamentals_uses_optional_none(self, sample_history_df):
        """
        Verify that missing or unpopulated fundamental fields default to None
        without failing schema validation.
        """
        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = sample_history_df
        # Empty info and no quarterly financials
        mock_ticker.info = {}
        mock_ticker.quarterly_financials = None
        mock_yf.Ticker.return_value = mock_ticker

        connector = DataConnector(max_retries=1, backoff_factor=0.01, yf_module=mock_yf)
        payload = connector.fetch_ticker_data("PLTR")

        assert payload is not None
        assert payload.financials.market_cap is None
        assert payload.financials.public_float is None
        assert payload.financials.short_interest_pct is None
        assert payload.financials.net_income_q1 is None
        assert payload.financials.net_income_ttm is None
        # Technicals should still be fully populated
        assert payload.technicals.highs_20d > 0
        assert payload.technicals.avg_volume_10d > 0


class TestSchemas:
    """Direct validation tests for Pydantic v2 domain schemas."""

    def test_technical_metrics_validation_rejects_empty(self):
        with pytest.raises(ValueError):
            TechnicalMetrics(
                avg_volume_10d=1000,
                highs_20d=50,
                close_prices=[],
                volumes=[],
                latest_close=50,
                latest_volume=1000,
            )

    def test_technical_metrics_validation_mismatched_lengths(self):
        with pytest.raises(ValueError, match="Series length mismatch"):
            TechnicalMetrics(
                avg_volume_10d=1000,
                highs_20d=50,
                close_prices=[10.0, 11.0, 12.0],
                volumes=[1000, 2000],  # 2 vs 3
                latest_close=12.0,
                latest_volume=2000,
            )

    def test_financial_metrics_allows_partial_data(self):
        fin = FinancialMetrics(market_cap=1_000_000.0)
        assert fin.market_cap == 1_000_000.0
        assert fin.public_float is None
        assert fin.short_interest_pct is None
