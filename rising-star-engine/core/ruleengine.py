"""
Rising Star Trend Engine - RuleEngine Micro-Module
Validates baseline S&P-style qualification criteria and fundamental hygiene filters.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from core.dataconnector import MarketData

logger = logging.getLogger(__name__)


@dataclass
class RuleCheckResult:
    """Result of S&P eligibility and hygiene baseline checks."""
    is_eligible: bool
    ticker: str
    passed_rules: List[str] = field(default_factory=list)
    failed_rules: List[str] = field(default_factory=list)
    details: Dict[str, any] = field(default_factory=dict)


class RuleEngine:
    """
    Evaluates institutional baseline filters:
    1. Minimum Market Cap (default: $1B+ for emerging growth, customizable)
    2. Positive Earnings (Cumulative TTM Net Income > 0, MRQ Net Income > 0)
    3. Public Float Adequacy (>= 10,000,000 shares)
    4. Institutional Liquidity (Average Daily Dollar Volume >= $5,000,000)
    5. Anti-Penny Stock Threshold (Price >= $5.00)
    """

    def __init__(
        self,
        min_market_cap: float = 1_000_000_000.0,  # $1B minimum
        require_positive_ttm_earnings: bool = True,
        min_public_float: float = 10_000_000.0,   # 10M shares
        min_daily_dollar_volume: float = 5_000_000.0, # $5M daily traded volume
        min_share_price: float = 5.0,              # $5.00 minimum
    ):
        self.min_market_cap = min_market_cap
        self.require_positive_ttm_earnings = require_positive_ttm_earnings
        self.min_public_float = min_public_float
        self.min_daily_dollar_volume = min_daily_dollar_volume
        self.min_share_price = min_share_price

    def evaluate(self, data: MarketData) -> RuleCheckResult:
        """
        Runs all baseline eligibility rules against the provided MarketData object.
        """
        passed: List[str] = []
        failed: List[str] = []
        details: Dict[str, any] = {}

        # Rule 1: Share Price >= $5
        price = data.latest_close
        details["latest_close"] = price
        if price >= self.min_share_price:
            passed.append(f"Price (${price:.2f} >= ${self.min_share_price:.2f})")
        else:
            failed.append(f"Penny stock filter violated: ${price:.2f} < ${self.min_share_price:.2f}")

        # Rule 2: Market Capitalization
        mcap = data.market_cap
        details["market_cap"] = mcap
        if mcap is not None and mcap >= self.min_market_cap:
            passed.append(f"Market Cap (${mcap/1e9:.2f}B >= ${self.min_market_cap/1e9:.2f}B)")
        elif mcap is not None:
            failed.append(f"Market Cap below threshold: ${mcap/1e9:.2f}B < ${self.min_market_cap/1e9:.2f}B")
        else:
            # Tolerant if unlisted or privately held float
            failed.append("Missing Market Cap fundamental")

        # Rule 3: Positive TTM Net Income (S&P standard)
        ttm_income = data.net_income_ttm
        details["net_income_ttm"] = ttm_income
        if self.require_positive_ttm_earnings:
            if ttm_income is not None and ttm_income > 0:
                passed.append(f"Positive TTM Net Income (${ttm_income/1e6:.1f}M)")
            elif ttm_income is not None:
                failed.append(f"Negative TTM Earnings (${ttm_income/1e6:.1f}M <= 0)")
            else:
                failed.append("Missing TTM Net Income")

        # Rule 4: Public Float
        p_float = data.public_float
        details["public_float"] = p_float
        if p_float is not None and p_float >= self.min_public_float:
            passed.append(f"Public Float ({p_float/1e6:.1f}M shares >= {self.min_public_float/1e6:.1f}M)")
        elif p_float is not None:
            failed.append(f"Restricted Public Float ({p_float/1e6:.1f}M shares)")
        else:
            # If unknown float, record note
            passed.append("Float check skipped (unreported)")

        # Rule 5: Daily Dollar Volume (Liquidity)
        avg_vol = data.avg_volume_10d
        if avg_vol is None and len(data.volumes) >= 10:
            avg_vol = sum(data.volumes[-10:]) / 10.0
        details["avg_volume_10d"] = avg_vol

        daily_dollar_vol = (avg_vol or 0) * price
        details["daily_dollar_volume"] = daily_dollar_vol
        if daily_dollar_vol >= self.min_daily_dollar_volume:
            passed.append(f"Institutional Liquidity (${daily_dollar_vol/1e6:.1f}M/day >= ${self.min_daily_dollar_volume/1e6:.1f}M)")
        else:
            failed.append(f"Illiquid: ${daily_dollar_vol/1e6:.1f}M/day < ${self.min_daily_dollar_volume/1e6:.1f}M")

        is_eligible = len(failed) == 0
        return RuleCheckResult(
            is_eligible=is_eligible,
            ticker=data.ticker,
            passed_rules=passed,
            failed_rules=failed,
            details=details,
        )
