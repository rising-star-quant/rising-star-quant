"""
Rising Star Trend Engine - Sprint 1: Domain Schemas
Pydantic v2 models for financial fundamentals, technical metrics, and market data payloads.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class FinancialMetrics(BaseModel):
    """
    Fundamental corporate financial metrics for trend and quality filtering.
    All fields are optional with None defaults to gracefully handle varied market coverage.
    """
    model_config = ConfigDict(frozen=True, extra="ignore")

    market_cap: Optional[float] = Field(
        default=None,
        description="Total market capitalization in USD.",
        ge=0
    )
    public_float: Optional[float] = Field(
        default=None,
        description="Freely tradable shares available to the public.",
        ge=0
    )
    avg_volume_10d: Optional[float] = Field(
        default=None,
        description="10-day average trading volume reported in fundamentals (if available).",
        ge=0
    )
    net_income_q1: Optional[float] = Field(
        default=None,
        description="Net income for the most recent reporting quarter (Q1 / latest MRQ)."
    )
    net_income_ttm: Optional[float] = Field(
        default=None,
        description="Trailing twelve months (TTM) net income."
    )
    short_interest_pct: Optional[float] = Field(
        default=None,
        description="Short interest as a percentage of public float (e.g. 0.085 for 8.5%).",
        ge=0,
        le=1.0
    )


class TechnicalMetrics(BaseModel):
    """
    Quantitative technical metrics computed from historical OHLCV price action.
    """
    model_config = ConfigDict(frozen=True, extra="ignore")

    avg_volume_10d: float = Field(
        ...,
        description="Calculated average trading volume over the last 10 trading sessions.",
        ge=0
    )
    highs_20d: float = Field(
        ...,
        description="Highest price achieved over the last 20 trading sessions.",
        gt=0
    )
    close_prices: List[float] = Field(
        ...,
        description="Ordered list of historical closing prices (oldest to newest)."
    )
    volumes: List[int] = Field(
        ...,
        description="Ordered list of historical trading volumes (oldest to newest)."
    )
    latest_close: float = Field(
        ...,
        description="Most recent closing price.",
        gt=0
    )
    latest_volume: int = Field(
        ...,
        description="Most recent session volume.",
        ge=0
    )

    @field_validator("close_prices")
    @classmethod
    def validate_close_prices(cls, v: List[float]) -> List[float]:
        if not v:
            raise ValueError("close_prices must contain at least one price entry.")
        for p in v:
            if p <= 0:
                raise ValueError("Closing prices must be strictly positive.")
        return v

    @field_validator("volumes")
    @classmethod
    def validate_volumes(cls, v: List[int]) -> List[int]:
        if not v:
            raise ValueError("volumes must contain at least one volume entry.")
        for vol in v:
            if vol < 0:
                raise ValueError("Trading volume cannot be negative.")
        return v

    @model_validator(mode="after")
    def validate_series_lengths(self) -> TechnicalMetrics:
        if len(self.close_prices) != len(self.volumes):
            raise ValueError(
                f"Series length mismatch: close_prices has {len(self.close_prices)} items "
                f"while volumes has {len(self.volumes)} items."
            )
        return self


class MarketDataPayload(BaseModel):
    """
    Aggregated strictly-typed data contract consumed by the Rising Star Trend Engine.
    Combines corporate fundamentals and historical technical price action.
    """
    model_config = ConfigDict(frozen=True, extra="ignore")

    ticker: str = Field(
        ...,
        description="Normalized stock ticker symbol in uppercase (e.g. 'NVDA', 'AAPL').",
        min_length=1,
        max_length=12
    )
    as_of: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when market data was ingested and normalized."
    )
    financials: FinancialMetrics = Field(
        ...,
        description="Corporate financial and float metrics."
    )
    technicals: TechnicalMetrics = Field(
        ...,
        description="Historical OHLCV time series and derived momentum indicators."
    )

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("Ticker symbol cannot be empty.")
        return cleaned

    @property
    def is_20d_high_breakout(self) -> bool:
        """Returns True if the latest close is within 0.5% of the 20-day high."""
        if self.technicals.highs_20d <= 0:
            return False
        return self.technicals.latest_close >= (self.technicals.highs_20d * 0.995)

    @property
    def volume_surge_ratio(self) -> float:
        """Ratio of latest volume to the 10-day average volume."""
        if self.technicals.avg_volume_10d <= 0:
            return 1.0
        return self.technicals.latest_volume / self.technicals.avg_volume_10d

    def compute_annual_dollar_volume(self, lookback_bars: int = 252) -> float:
        """
        Calculates trailing annual dollar volume traded directly from historical price & volume:
        sum(Close * Volume) over the trailing lookback_bars (defaults to 252 sessions).
        Annualizes proportionally if fewer than 252 bars are available.
        """
        closes = self.technicals.close_prices
        volumes = self.technicals.volumes
        n = min(len(closes), len(volumes))
        if n == 0:
            return 0.0

        bars = min(n, lookback_bars)
        start_idx = n - bars
        total_vol = sum(closes[i] * volumes[i] for i in range(start_idx, n))
        if 0 < bars < 252:
            total_vol = (total_vol / bars) * 252.0
        return round(total_vol, 2)

