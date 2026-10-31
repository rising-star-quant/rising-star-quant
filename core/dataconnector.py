"""
Rising Star Trend Engine - DataConnector Micro-Module
Ingests historical OHLCV and fundamental metrics using yfinance with exponential backoff.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TypeVar

try:
    import yfinance as yf
except ImportError:
    yf = None

logger = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass(frozen=True)
class MarketData:
    """Standardized market data contract emitted by DataConnector."""
    ticker: str
    timestamp: datetime
    close_prices: List[float]
    high_prices: List[float]
    low_prices: List[float]
    volumes: List[int]
    latest_close: float
    latest_volume: int
    market_cap: Optional[float] = None
    public_float: Optional[float] = None
    net_income_q1: Optional[float] = None
    net_income_ttm: Optional[float] = None
    short_interest_pct: Optional[float] = None
    avg_volume_10d: Optional[float] = None
    exchange: Optional[str] = None


class DataConnector:
    """
    Resilient data ingestion adapter with exponential backoff and retry logic.
    """

    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        lookback_days: int = 120,
        jitter: bool = True,
        yf_module: Any = None,
    ):
        self.max_retries = max(0, max_retries)
        self.backoff_factor = max(0.1, backoff_factor)
        self.lookback_days = max(30, lookback_days)
        self.jitter = jitter
        self.yf = yf_module if yf_module is not None else yf

    def _execute_with_retry(self, operation_name: str, func: Callable[[], T]) -> Optional[T]:
        attempt = 0
        while attempt <= self.max_retries:
            try:
                return func()
            except Exception as exc:
                err_str = str(exc).lower()
                is_transient = any(kw in err_str for kw in ["429", "rate limit", "throttle", "timeout", "connection"])

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

    def fetch_ticker_data(self, ticker: str) -> Optional[MarketData]:
        """
        Fetches historical OHLCV bars and fundamentals for a single ticker.
        """
        if not ticker or not isinstance(ticker, str) or not ticker.strip():
            logger.warning("Invalid ticker symbol provided: %r", ticker)
            return None

        clean_ticker = ticker.strip().upper()

        if self.yf is None:
            logger.warning("yfinance is not available in environment.")
            return None

        def _fetch() -> Optional[MarketData]:
            ticker_obj = self.yf.Ticker(clean_ticker)

            # 1. Fetch History
            history_df = ticker_obj.history(period=f"{self.lookback_days}d")
            if history_df is None or history_df.empty or len(history_df) < 20:
                logger.warning("No or insufficient price history (<20 bars) for %s", clean_ticker)
                return None

            close_series = [float(x) for x in history_df["Close"].dropna().tolist()]
            high_series = [float(x) for x in history_df["High"].dropna().tolist()]
            low_series = [float(x) for x in history_df["Low"].dropna().tolist()]
            volume_series = [int(x) for x in history_df["Volume"].dropna().tolist()]

            if len(close_series) < 20:
                return None

            latest_close = close_series[-1]
            latest_volume = volume_series[-1]

            # 2. Fetch Fundamentals
            info: Dict[str, Any] = {}
            try:
                info = getattr(ticker_obj, "info", None) or {}
            except Exception as e:
                logger.debug("Failed to fetch info for %s: %s", clean_ticker, e)

            market_cap = info.get("marketCap")
            public_float = info.get("floatShares") or info.get("sharesOutstanding")
            short_interest_pct = info.get("shortPercentOfFloat")
            avg_volume_10d = info.get("averageDailyVolume10Day") or info.get("averageVolume10days")
            net_income_ttm = info.get("netIncomeToCommon")
            raw_exchange = info.get("exchange")

            # Extract quarterly net income
            net_income_q1 = None
            try:
                qf = getattr(ticker_obj, "quarterly_financials", None)
                if qf is not None and not qf.empty and "Net Income" in qf.index:
                    net_income_q1 = float(qf.loc["Net Income"].iloc[0])
            except Exception:
                pass

            return MarketData(
                ticker=clean_ticker,
                timestamp=datetime.utcnow(),
                close_prices=close_series,
                high_prices=high_series,
                low_prices=low_series,
                volumes=volume_series,
                latest_close=latest_close,
                latest_volume=latest_volume,
                market_cap=float(market_cap) if market_cap is not None else None,
                public_float=float(public_float) if public_float is not None else None,
                net_income_q1=net_income_q1,
                net_income_ttm=float(net_income_ttm) if net_income_ttm is not None else None,
                short_interest_pct=float(short_interest_pct) if short_interest_pct is not None else None,
                avg_volume_10d=float(avg_volume_10d) if avg_volume_10d is not None else None,
                exchange=str(raw_exchange) if raw_exchange else None,
            )


        return self._execute_with_retry(f"fetch_ticker_data({clean_ticker})", _fetch)
