"""
Rising Star Trend Engine - Sprint 1: DataConnector Module
Resilient data ingestion adapter with exponential backoff for yfinance market data.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Callable, Dict, List, Optional, TypeVar

try:
    import yfinance as yf
except ImportError:  # Graceful fallback if yfinance is not installed in local environment
    yf = None

from src.schemas import FinancialMetrics, MarketDataPayload, TechnicalMetrics

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DataConnectorError(Exception):
    """Base exception for DataConnector operational errors."""
    pass


class RateLimitError(DataConnectorError):
    """Raised when an external market data provider throttles requests."""
    pass


class DataConnector:
    """
    Ingests and normalizes equity fundamentals and historical OHLCV data.
    Implements exponential backoff and jitter to withstand API rate limits and network drops.
    """

    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        lookback_days: int = 60,
        jitter: bool = True,
        yf_module: Any = None,
    ):
        """
        Initialize the DataConnector.

        :param max_retries: Number of retry attempts on transient network or 429 errors.
        :param backoff_factor: Multiplier for exponential backoff sleep interval (seconds).
        :param lookback_days: Number of historical trading days to fetch.
        :param jitter: Whether to apply randomized jitter to backoff intervals to prevent thundering herds.
        :param yf_module: Optional injectable yfinance module for mocking and unit testing.
        """
        self.max_retries = max(0, max_retries)
        self.backoff_factor = max(0.1, backoff_factor)
        self.lookback_days = max(20, lookback_days)
        self.jitter = jitter
        self.yf = yf_module if yf_module is not None else yf

    def _execute_with_retry(
        self, operation_name: str, func: Callable[[], T]
    ) -> Optional[T]:
        """
        Executes a callable with exponential backoff and retry on transient errors.
        Logs warnings and returns None if retries are exhausted.
        """
        attempt = 0
        while attempt <= self.max_retries:
            try:
                return func()
            except Exception as exc:
                err_str = str(exc).lower()
                is_rate_limit = (
                    "429" in err_str
                    or "rate limit" in err_str
                    or "too many requests" in err_str
                )
                is_transient = (
                    is_rate_limit
                    or "connection" in err_str
                    or "timeout" in err_str
                    or "temporary" in err_str
                )

                attempt += 1
                if attempt > self.max_retries or not is_transient:
                    logger.warning(
                        "Operation '%s' failed permanently after %d attempts: %s",
                        operation_name,
                        attempt,
                        exc,
                    )
                    return None

                sleep_time = self.backoff_factor * (2 ** (attempt - 1))
                if self.jitter:
                    sleep_time += random.uniform(0.05, 0.25 * sleep_time)

                logger.warning(
                    "Transient error in '%s' (attempt %d/%d): %s. Backing off for %.2fs...",
                    operation_name,
                    attempt,
                    self.max_retries,
                    exc,
                    sleep_time,
                )
                time.sleep(sleep_time)

        return None

    def fetch_ticker_data(self, ticker: str) -> Optional[MarketDataPayload]:
        """
        Fetches historical OHLCV and fundamental metrics for a given ticker symbol.
        Normalizes and returns a strictly-typed MarketDataPayload, or None if unavailable.

        :param ticker: Equity ticker symbol (e.g. 'NVDA', 'AAPL').
        :return: Normalized MarketDataPayload or None on failure/missing data.
        """
        if not ticker or not isinstance(ticker, str) or not ticker.strip():
            logger.warning("Invalid ticker symbol provided: %r", ticker)
            return None

        clean_ticker = ticker.strip().upper()

        if self.yf is None:
            logger.warning("yfinance module is not installed or available.")
            return None

        def _fetch() -> Optional[MarketDataPayload]:
            ticker_obj = self.yf.Ticker(clean_ticker)

            # 1. Fetch OHLCV History
            history_df = ticker_obj.history(period=f"{self.lookback_days}d")
            if history_df is None or history_df.empty:
                logger.warning("No price history returned for ticker: %s", clean_ticker)
                return None

            # Need at least 20 trading sessions to compute technical metrics (e.g. 20d high)
            if len(history_df) < 20:
                logger.warning(
                    "Insufficient history for ticker %s: expected >= 20 bars, got %d",
                    clean_ticker,
                    len(history_df),
                )
                return None

            # Extract OHLCV series
            if "Close" not in history_df.columns or "Volume" not in history_df.columns:
                logger.warning("Expected 'Close' and 'Volume' columns in history for %s", clean_ticker)
                return None

            close_series = history_df["Close"].dropna().astype(float).tolist()
            volume_series = history_df["Volume"].dropna().astype(int).tolist()

            if len(close_series) < 20 or len(volume_series) < 20:
                logger.warning("Cleaned series length is less than 20 for ticker %s", clean_ticker)
                return None

            # Calculate 20d high (using 'High' column if available, otherwise 'Close')
            if "High" in history_df.columns:
                highs_20d = float(history_df["High"].iloc[-20:].max())
            else:
                highs_20d = float(max(close_series[-20:]))

            # Calculate 10-day average volume
            last_10_vols = volume_series[-10:]
            avg_volume_10d = float(sum(last_10_vols) / len(last_10_vols))

            latest_close = float(close_series[-1])
            latest_volume = int(volume_series[-1])

            technicals = TechnicalMetrics(
                avg_volume_10d=avg_volume_10d,
                highs_20d=highs_20d,
                close_prices=close_series,
                volumes=volume_series,
                latest_close=latest_close,
                latest_volume=latest_volume,
            )

            # 2. Fetch Fundamentals & Corporate Info
            info: Dict[str, Any] = {}
            try:
                info = getattr(ticker_obj, "info", None) or {}
            except Exception as info_err:
                logger.warning("Failed to fetch info for %s: %s", clean_ticker, info_err)
                info = {}

            market_cap = info.get("marketCap")
            public_float = info.get("floatShares") or info.get("sharesOutstanding")
            short_interest_pct = info.get("shortPercentOfFloat")
            avg_volume_10d_info = info.get("averageDailyVolume10Day") or info.get("averageVolume10days")

            # Extract quarterly and TTM net income safely
            net_income_ttm = info.get("netIncomeToCommon")

            net_income_q1 = None
            try:
                quarterly_financials = getattr(ticker_obj, "quarterly_financials", None)
                if quarterly_financials is not None and not quarterly_financials.empty:
                    if "Net Income" in quarterly_financials.index:
                        net_income_q1 = float(quarterly_financials.loc["Net Income"].iloc[0])
            except Exception as fin_err:
                logger.debug("Could not extract quarterly net income for %s: %s", clean_ticker, fin_err)

            financials = FinancialMetrics(
                market_cap=float(market_cap) if market_cap is not None else None,
                public_float=float(public_float) if public_float is not None else None,
                avg_volume_10d=float(avg_volume_10d_info) if avg_volume_10d_info is not None else None,
                net_income_q1=net_income_q1,
                net_income_ttm=float(net_income_ttm) if net_income_ttm is not None else None,
                short_interest_pct=float(short_interest_pct) if short_interest_pct is not None else None,
            )

            # 3. Aggregate & Validate via Pydantic Root Model
            return MarketDataPayload(
                ticker=clean_ticker,
                financials=financials,
                technicals=technicals,
            )

        return self._execute_with_retry(f"fetch_ticker_data({clean_ticker})", _fetch)
