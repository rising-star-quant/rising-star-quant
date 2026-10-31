"""
Rising Star Trend Engine - Sprint 2: RuleEngine Atomic Micro-Module
Evaluates 100% of formal S&P 500 eligibility rules:
1. U.S. Incorporation & Primary Exchange (NYSE, NASDAQ, Cboe)
2. Market Capitalization >= $18.0B (current S&P index inclusion floor)
3. Float-Adjusted Liquidity Ratio > 1.0 AND Public Float >= 50%
4. GAAP Financial Viability: Sum of GAAP Net Income over last 4 quarters (TTM) > 0 AND MRQ Net Income > 0

Refactored with data normalization & pipeline helpers:
- Exchange Mapping: Standardizes Yahoo Finance codes (NMS, NGM, NCM -> NASDAQ; NYQ -> NYSE, etc.)
- Public Float: Normalizes percentage inputs (e.g. 75.0 -> 0.75) to strict [0.0, 1.0] ratio
- Automated Annual Dollar Volume: Computes sum(Close * Volume) over trailing 252 sessions via .iloc[]
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator


# Canonical Yahoo Finance exchange code mappings
YAHOO_EXCHANGE_MAP: Dict[str, str] = {
    "NMS": "NASDAQ",  # Nasdaq Global Select Market
    "NGM": "NASDAQ",  # Nasdaq Global Market
    "NCM": "NASDAQ",  # Nasdaq Capital Market
    "NYQ": "NYSE",    # New York Stock Exchange
    "ASE": "NYSE",    # NYSE American
    "PCX": "NYSE",    # NYSE Arca
    "BATS": "CBOE",   # Cboe BZX
    "BTS": "CBOE",    # Cboe
    "XNAS": "NASDAQ",
    "XNYS": "NYSE",
}


def normalize_exchange_code(exchange: Optional[str]) -> str:
    """
    Standardizes exchange codes (including Yahoo Finance ticker info formats)
    into canonical S&P 500 eligible exchange identifiers (e.g. NMS/NGM/NCM -> NASDAQ).
    """
    if not exchange:
        return "NASDAQ"
    clean = str(exchange).strip().upper()
    return YAHOO_EXCHANGE_MAP.get(clean, clean)


def compute_annual_dollar_volume(
    closes: Optional[Union[List[float], Any]],
    volumes: Optional[Union[List[int], Any]],
    lookback_bars: int = 252,
) -> float:
    """
    Calculates the trailing annual dollar volume traded directly from historical price and volume bars.
    Formula: sum(Close * Volume) over trailing lookback_bars (typically 252 trading sessions).
    Uses .iloc[] positional indexing when Pandas Series is provided to prevent deprecation warnings.
    """
    if closes is None or volumes is None:
        return 0.0

    n = min(len(closes), len(volumes))
    if n == 0:
        return 0.0

    bars_to_use = min(n, lookback_bars)
    start_idx = n - bars_to_use

    total_dollar_vol = 0.0
    if hasattr(closes, "iloc") and hasattr(volumes, "iloc"):
        for i in range(start_idx, n):
            total_dollar_vol += float(closes.iloc[i]) * float(volumes.iloc[i])
    else:
        for i in range(start_idx, n):
            total_dollar_vol += float(closes[i]) * float(volumes[i])

    # If fewer than 252 bars available, annualize proportionally
    if 0 < bars_to_use < 252:
        total_dollar_vol = (total_dollar_vol / bars_to_use) * 252.0

    return round(total_dollar_vol, 2)


class CompanyProfile(BaseModel):
    """Normalized corporate profile data consumed by the RuleEngine."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    ticker: str = Field(..., description="Stock ticker symbol.")
    country: str = Field(default="US", description="Country of incorporation/headquarters (e.g., 'US', 'USA').")
    exchange: str = Field(default="NASDAQ", description="Primary listing exchange (e.g., 'NYSE', 'NASDAQ', 'CBOE').")
    market_cap: float = Field(..., ge=0, description="Total market capitalization in USD.")
    shares_outstanding: Optional[float] = Field(default=None, ge=0, description="Total common shares outstanding.")
    float_shares: Optional[float] = Field(default=None, ge=0, description="Freely tradable shares (public float).")
    public_float_pct: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Public float percentage as a ratio [0.0 to 1.0], e.g., 0.65 for 65%."
    )
    annual_dollar_volume: Optional[float] = Field(
        default=None,
        ge=0,
        description="Trailing 12-month annual dollar value traded."
    )
    avg_daily_volume_shares: Optional[float] = Field(default=None, ge=0, description="Average daily volume in shares.")
    latest_price: Optional[float] = Field(default=None, gt=0, description="Current share price in USD.")
    net_income_ttm: float = Field(..., description="Trailing 12-month (sum of last 4 quarters) GAAP Net Income.")
    net_income_mrq: float = Field(..., description="Most recent quarter (MRQ / Q1) GAAP Net Income.")

    @field_validator("exchange", mode="before")
    @classmethod
    def normalize_exchange(cls, v: Any) -> str:
        if isinstance(v, str):
            return normalize_exchange_code(v)
        return "NASDAQ"

    @field_validator("public_float_pct", mode="before")
    @classmethod
    def normalize_float_pct(cls, v: Any) -> Optional[float]:
        if v is None:
            return None
        try:
            val = float(v)
            # Normalize percentage (e.g., 75.0% -> 0.75)
            if val > 1.0:
                val = val / 100.0
            return max(0.0, min(1.0, round(val, 6)))
        except (ValueError, TypeError):
            return None


def build_profile_from_market_data(
    ticker: str,
    market_cap: float,
    net_income_ttm: float,
    net_income_mrq: float,
    exchange: str = "NASDAQ",
    country: str = "US",
    public_float_pct: Optional[float] = None,
    shares_outstanding: Optional[float] = None,
    float_shares: Optional[float] = None,
    annual_dollar_volume: Optional[float] = None,
    closes: Optional[Union[List[float], Any]] = None,
    volumes: Optional[Union[List[int], Any]] = None,
    latest_price: Optional[float] = None,
    avg_daily_volume_shares: Optional[float] = None,
) -> CompanyProfile:
    """
    Pipeline factory helper to construct a standardized, normalized CompanyProfile.
    - Standardizes Yahoo exchange codes (NMS, NGM, NCM -> NASDAQ).
    - Normalizes public_float_pct (ratio 0.0 to 1.0).
    - Automatically calculates annual_dollar_volume from historical price/volume data
      using sum(Close * Volume) if closes and volumes are provided.
    """
    if annual_dollar_volume is None and closes is not None and volumes is not None:
        annual_dollar_volume = compute_annual_dollar_volume(closes, volumes)

    return CompanyProfile(
        ticker=ticker,
        country=country,
        exchange=exchange,
        market_cap=market_cap,
        shares_outstanding=shares_outstanding,
        float_shares=float_shares,
        public_float_pct=public_float_pct,
        annual_dollar_volume=annual_dollar_volume,
        avg_daily_volume_shares=avg_daily_volume_shares,
        latest_price=latest_price,
        net_income_ttm=net_income_ttm,
        net_income_mrq=net_income_mrq,
    )


class EligibilityResult(BaseModel):
    """Strictly typed audit result emitted by RuleEngine."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    ticker: str
    is_eligible: bool = Field(..., description="True if 100% of formal S&P 500 eligibility rules are met.")
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    criteria_checklist: Dict[str, bool] = Field(
        ...,
        description="Dictionary mapping each criteria name to boolean pass/fail status."
    )
    failed_criteria: List[str] = Field(
        default_factory=list,
        description="List of specific criteria that failed evaluation."
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Audit metrics and evaluation breakdown values."
    )


class RuleEngine:
    """
    Stateless, pure-logic evaluation engine for formal S&P 500 index eligibility.
    """

    ELIGIBLE_COUNTRIES: Set[str] = {"US", "USA", "UNITED STATES"}
    ELIGIBLE_EXCHANGES: Set[str] = {
        "NYSE", "NASDAQ", "CBOE", "XNYS", "XNAS", "BATS", "BTS",
        "NEW YORK STOCK EXCHANGE", "NASDAQ GLOBAL SELECT", "NASDAQ CAPITAL MARKET",
        "NMS", "NGM", "NCM", "NYQ"
    }

    def __init__(
        self,
        min_market_cap: float = 18_000_000_000.0,  # $18.0B S&P floor
        min_public_float_pct: float = 0.50,         # Minimum 50% public float
        min_liquidity_ratio: float = 1.0,           # Float-adjusted liquidity ratio > 1.0
        require_gaap_viability: bool = True,
    ):
        self.min_market_cap = min_market_cap
        self.min_public_float_pct = min_public_float_pct
        self.min_liquidity_ratio = min_liquidity_ratio
        self.require_gaap_viability = require_gaap_viability

    def evaluate(
        self,
        profile: CompanyProfile,
        closes: Optional[Union[List[float], Any]] = None,
        volumes: Optional[Union[List[int], Any]] = None,
    ) -> EligibilityResult:
        """
        Evaluates a normalized CompanyProfile against S&P 500 criteria.
        If closes and volumes are provided and profile.annual_dollar_volume is None,
        automatically computes annual_dollar_volume via sum(Close * Volume).
        Pure function: does not mutate state or make network calls.
        """
        checklist: Dict[str, bool] = {}
        failed: List[str] = []
        details: Dict[str, Any] = {}

        # 1. U.S. Incorporation Check
        norm_country = (profile.country or "").strip().upper()
        is_us_inc = norm_country in self.ELIGIBLE_COUNTRIES
        checklist["us_incorporation"] = is_us_inc
        details["country"] = profile.country
        if not is_us_inc:
            failed.append("U.S. Incorporation (must be U.S. company)")

        # 2. Eligible Primary Exchange Check (standardizes NMS/NGM/NCM -> NASDAQ)
        norm_exchange = normalize_exchange_code(profile.exchange).strip().upper()
        is_valid_exchange = any(ex in norm_exchange for ex in self.ELIGIBLE_EXCHANGES)
        checklist["eligible_exchange"] = is_valid_exchange
        details["exchange"] = profile.exchange
        details["normalized_exchange"] = norm_exchange
        if not is_valid_exchange:
            failed.append("Primary Exchange (must be listed on NYSE, NASDAQ, or Cboe)")

        # 3. Market Capitalization Check (>= $18.0B)
        mcap = profile.market_cap
        is_mcap_valid = mcap >= self.min_market_cap
        checklist["market_cap_threshold"] = is_mcap_valid
        details["market_cap_usd"] = mcap
        details["market_cap_threshold_usd"] = self.min_market_cap
        if not is_mcap_valid:
            failed.append(f"Market Capitalization (${mcap/1e9:.2f}B < ${self.min_market_cap/1e9:.2f}B)")

        # 4. Public Float Percentage (>= 50%)
        float_pct = profile.public_float_pct
        if float_pct is None:
            if profile.float_shares and profile.shares_outstanding and profile.shares_outstanding > 0:
                raw_pct = profile.float_shares / profile.shares_outstanding
                float_pct = raw_pct / 100.0 if raw_pct > 1.0 else raw_pct
            elif profile.float_shares and profile.market_cap and profile.latest_price and profile.latest_price > 0:
                total_shares_est = profile.market_cap / profile.latest_price
                raw_pct = profile.float_shares / total_shares_est if total_shares_est > 0 else 0.0
                float_pct = raw_pct / 100.0 if raw_pct > 1.0 else raw_pct

        if float_pct is not None:
            float_pct = max(0.0, min(1.0, float_pct))

        details["public_float_pct"] = float_pct
        is_float_valid = float_pct is not None and float_pct >= self.min_public_float_pct
        checklist["public_float_minimum"] = is_float_valid
        if not is_float_valid:
            pct_str = f"{float_pct * 100:.1f}%" if float_pct is not None else "Unknown"
            failed.append(f"Public Float ({pct_str} < {self.min_public_float_pct * 100:.0f}%)")

        # 5. Float-Adjusted Liquidity Ratio (> 1.0)
        # S&P standard: (Annual Dollar Value Traded) / (Float-Adjusted Market Cap) > 1.0
        float_adj_market_cap = mcap * (float_pct if float_pct is not None else 1.0)
        annual_dollar_vol = profile.annual_dollar_volume

        # Automated derivation of annual dollar volume if missing
        if annual_dollar_vol is None or annual_dollar_vol <= 0:
            if closes is not None and volumes is not None:
                annual_dollar_vol = compute_annual_dollar_volume(closes, volumes)
            elif profile.avg_daily_volume_shares and profile.latest_price:
                annual_dollar_vol = profile.avg_daily_volume_shares * profile.latest_price * 252.0
            else:
                annual_dollar_vol = 0.0

        details["annual_dollar_volume"] = annual_dollar_vol
        details["float_adjusted_market_cap"] = float_adj_market_cap

        if float_adj_market_cap > 0:
            liquidity_ratio = annual_dollar_vol / float_adj_market_cap
        else:
            liquidity_ratio = 0.0

        details["liquidity_ratio"] = round(liquidity_ratio, 3)
        is_liquidity_valid = liquidity_ratio > self.min_liquidity_ratio
        checklist["liquidity_ratio_threshold"] = is_liquidity_valid
        if not is_liquidity_valid:
            failed.append(f"Float-Adjusted Liquidity Ratio ({liquidity_ratio:.2f} <= {self.min_liquidity_ratio:.2f})")

        # 6. GAAP Financial Viability
        # Criteria: Sum of GAAP Net Income over last 4 quarters > 0 AND MRQ Net Income > 0
        ttm_income = profile.net_income_ttm
        mrq_income = profile.net_income_mrq
        details["gaap_net_income_ttm"] = ttm_income
        details["gaap_net_income_mrq"] = mrq_income

        is_ttm_positive = ttm_income > 0
        is_mrq_positive = mrq_income > 0
        checklist["gaap_ttm_positive"] = is_ttm_positive
        checklist["gaap_mrq_positive"] = is_mrq_positive

        if not is_ttm_positive:
            failed.append(f"GAAP TTM Net Income (${ttm_income/1e6:.1f}M <= $0)")
        if not is_mrq_positive:
            failed.append(f"GAAP Most Recent Quarter Net Income (${mrq_income/1e6:.1f}M <= $0)")

        is_eligible = len(failed) == 0

        return EligibilityResult(
            ticker=profile.ticker.strip().upper(),
            is_eligible=is_eligible,
            evaluated_at=datetime.utcnow(),
            criteria_checklist=checklist,
            failed_criteria=failed,
            details=details,
        )
