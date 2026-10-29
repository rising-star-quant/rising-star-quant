"""
Rising Star Trend Engine - Sprint 2: RuleEngine Atomic Micro-Module
Evaluates 100% of formal S&P 500 eligibility rules:
1. U.S. Incorporation & Primary Exchange (NYSE, NASDAQ, Cboe)
2. Market Capitalization >= $18.0B (current S&P index inclusion floor)
3. Float-Adjusted Liquidity Ratio > 1.0 AND Public Float >= 50%
4. GAAP Financial Viability: Sum of GAAP Net Income over last 4 quarters (TTM) > 0 AND MRQ Net Income > 0
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, ConfigDict, Field


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
        "NYSE", "NASDAQ", "CBOE", "XNYS", "XNAS", "BATS",
        "NEW YORK STOCK EXCHANGE", "NASDAQ GLOBAL SELECT", "NASDAQ CAPITAL MARKET"
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

    def evaluate(self, profile: CompanyProfile) -> EligibilityResult:
        checklist: Dict[str, bool] = {}
        failed: List[str] = []
        details: Dict[str, Any] = {}

        norm_country = (profile.country or "").strip().upper()
        is_us_inc = norm_country in self.ELIGIBLE_COUNTRIES
        checklist["us_incorporation"] = is_us_inc
        details["country"] = profile.country
        if not is_us_inc:
            failed.append("U.S. Incorporation (must be U.S. company)")

        norm_exchange = (profile.exchange or "").strip().upper()
        is_valid_exchange = any(ex in norm_exchange for ex in self.ELIGIBLE_EXCHANGES)
        checklist["eligible_exchange"] = is_valid_exchange
        details["exchange"] = profile.exchange
        if not is_valid_exchange:
            failed.append("Primary Exchange (must be listed on NYSE, NASDAQ, or Cboe)")

        mcap = profile.market_cap
        is_mcap_valid = mcap >= self.min_market_cap
        checklist["market_cap_threshold"] = is_mcap_valid
        details["market_cap_usd"] = mcap
        details["market_cap_threshold_usd"] = self.min_market_cap
        if not is_mcap_valid:
            failed.append(f"Market Capitalization (${mcap/1e9:.2f}B < ${self.min_market_cap/1e9:.2f}B)")

        float_pct = profile.public_float_pct
        if float_pct is None:
            if profile.float_shares and profile.shares_outstanding and profile.shares_outstanding > 0:
                float_pct = profile.float_shares / profile.shares_outstanding
            elif profile.float_shares and profile.market_cap and profile.latest_price and profile.latest_price > 0:
                total_shares_est = profile.market_cap / profile.latest_price
                float_pct = profile.float_shares / total_shares_est if total_shares_est > 0 else None

        details["public_float_pct"] = float_pct
        is_float_valid = float_pct is not None and float_pct >= self.min_public_float_pct
        checklist["public_float_minimum"] = is_float_valid
        if not is_float_valid:
            pct_str = f"{float_pct * 100:.1f}%" if float_pct is not None else "Unknown"
            failed.append(f"Public Float ({pct_str} < {self.min_public_float_pct * 100:.0f}%)")

        float_adj_market_cap = mcap * (float_pct if float_pct is not None else 1.0)
        annual_dollar_vol = profile.annual_dollar_volume

        if annual_dollar_vol is None:
            if profile.avg_daily_volume_shares and profile.latest_price:
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
