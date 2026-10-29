"""
Rising Star Trend Engine - Sprint 3: RiskGuard Micro-Module
Autonomous risk management engine that monitors active positions independently of entry signals:
1. Trailing Stop-Loss: Triggers exit when price drops past predefined percentage (default 10%) below post-entry peak.
2. Moving Average Breakdown: Triggers exit if Close < MA50 accompanied by >20% above-average volume.
3. Time-Based Holding Period Limit: Enforces a strict 60 trading days holding timeout.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PositionState(BaseModel):
    """Normalized active position state consumed by RiskGuard."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    ticker: str = Field(..., description="Stock ticker symbol.")
    entry_date: datetime = Field(..., description="Timestamp or date when position was opened.")
    entry_price: float = Field(..., gt=0, description="Average entry execution price.")
    shares: int = Field(default=100, ge=1, description="Number of shares held.")
    days_held: int = Field(..., ge=0, description="Trading days held since position inception.")
    highest_high_post_entry: float = Field(
        ...,
        gt=0,
        description="Highest high price reached since trade execution (peak)."
    )
    latest_close: float = Field(..., gt=0, description="Most recent session closing price.")
    latest_volume: int = Field(..., ge=0, description="Most recent session trading volume.")
    ma50: float = Field(..., gt=0, description="50-day simple moving average support level.")
    avg_volume_50d: float = Field(..., gt=0, description="50-day average daily trading volume.")


class RiskStatusPayload(BaseModel):
    """Strictly typed risk evaluation data contract emitted by RiskGuard."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    ticker: str
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    action: str = Field(
        ...,
        description="'HOLD', 'EXIT_TRAILING_STOP', 'EXIT_MA50_BREAKDOWN', 'EXIT_TIME_LIMIT', or 'EXIT_MULTIPLE_TRIGGERS'."
    )
    is_exit_triggered: bool = Field(..., description="True if any exit condition has been triggered.")
    exit_reasons: List[str] = Field(default_factory=list, description="Descriptive list of triggered exit criteria.")
    trailing_stop_price: float = Field(..., gt=0, description="Calculated dynamic trailing stop price.")
    current_drawdown_from_peak_pct: float = Field(
        ...,
        description="Percentage decline from the post-entry peak price (highest_high_post_entry)."
    )
    current_pnl_pct: float = Field(
        ...,
        description="Unrealized P&L percentage from entry price: ((latest_close - entry) / entry) * 100."
    )
    days_held: int
    days_remaining: int = Field(..., description="Trading sessions remaining before 60-day limit.")
    risk_details: Dict[str, Any] = Field(default_factory=dict)


class RiskGuard:
    """
    Headless autonomous risk management engine.
    Continuously monitors active positions against:
    - Trailing stop-loss (-10% from post-entry high)
    - MA50 breakdown confirmed with +20% volume surge
    - 60 trading days maximum holding time limit
    """

    def __init__(
        self,
        trailing_stop_pct: float = 10.0,       # 10% trailing stop below peak
        ma_volume_surge_pct: float = 20.0,     # >20% above 50-day avg volume on MA breakdown
        max_holding_days: int = 60,            # 60 trading days timeout
    ):
        self.trailing_stop_pct = trailing_stop_pct
        self.ma_vol_multiplier = 1.0 + (ma_volume_surge_pct / 100.0)  # 1.20x
        self.max_holding_days = max_holding_days

    def evaluate_position(self, position: PositionState) -> RiskStatusPayload:
        """
        Pure headless function that evaluates an active position against all risk limits.
        """
        ticker = position.ticker.strip().upper()
        entry = position.entry_price
        close = position.latest_close
        peak = max(position.highest_high_post_entry, close)
        vol = position.latest_volume
        ma50 = position.ma50
        avg_vol50 = position.avg_volume_50d
        days = position.days_held

        exit_reasons: List[str] = []
        details: Dict[str, Any] = {}

        # -------------------------------------------------------------
        # 1. Trailing Stop-Loss Evaluation
        # -------------------------------------------------------------
        # Trailing stop price = Peak * (1 - trailing_stop_pct / 100)
        trailing_stop_price = round(peak * (1.0 - (self.trailing_stop_pct / 100.0)), 2)
        drawdown_pct = round(((peak - close) / peak) * 100.0, 2)
        details["trailing_stop_price"] = trailing_stop_price
        details["drawdown_from_peak_pct"] = drawdown_pct
        details["peak_price"] = peak

        is_trailing_stop_breached = close < trailing_stop_price
        if is_trailing_stop_breached:
            exit_reasons.append(
                f"Trailing Stop Breached: Price ${close:.2f} dropped {drawdown_pct:.1f}% "
                f"from peak ${peak:.2f} (stop level: ${trailing_stop_price:.2f})"
            )

        # -------------------------------------------------------------
        # 2. Moving Average Breakdown (Close < MA50 on >20% Above-Avg Volume)
        # -------------------------------------------------------------
        vol_threshold = avg_vol50 * self.ma_vol_multiplier
        details["ma50_level"] = ma50
        details["volume_threshold"] = round(vol_threshold, 1)

        is_below_ma50 = close < ma50
        is_heavy_volume = vol > vol_threshold

        is_ma50_breakdown = is_below_ma50 and is_heavy_volume
        if is_ma50_breakdown:
            surge_ratio = round(vol / avg_vol50, 2)
            exit_reasons.append(
                f"MA50 Institutional Breakdown: Closed ${close:.2f} below MA50 (${ma50:.2f}) "
                f"on {surge_ratio}x volume ({vol:,} vs 50d avg {int(avg_vol50):,})"
            )
        elif is_below_ma50:
            details["ma50_warning"] = "Below MA50 but lacking volume confirmation; exit deferred."

        # -------------------------------------------------------------
        # 3. Time-Based Holding Period Limit (60 Trading Days)
        # -------------------------------------------------------------
        days_remaining = max(0, self.max_holding_days - days)
        details["days_held"] = days
        details["max_holding_days"] = self.max_holding_days

        is_time_limit_reached = days >= self.max_holding_days
        if is_time_limit_reached:
            exit_reasons.append(
                f"Time Limit Expired: Position held for {days} trading days "
                f"(max allowed: {self.max_holding_days} days)"
            )

        # -------------------------------------------------------------
        # Action Resolution
        # -------------------------------------------------------------
        is_exit_triggered = len(exit_reasons) > 0

        if not is_exit_triggered:
            action = "HOLD"
        elif len(exit_reasons) > 1:
            action = "EXIT_MULTIPLE_TRIGGERS"
        elif is_trailing_stop_breached:
            action = "EXIT_TRAILING_STOP"
        elif is_ma50_breakdown:
            action = "EXIT_MA50_BREAKDOWN"
        else:
            action = "EXIT_TIME_LIMIT"

        pnl_pct = round(((close - entry) / entry) * 100.0, 2)

        return RiskStatusPayload(
            ticker=ticker,
            action=action,
            is_exit_triggered=is_exit_triggered,
            exit_reasons=exit_reasons,
            trailing_stop_price=trailing_stop_price,
            current_drawdown_from_peak_pct=drawdown_pct,
            current_pnl_pct=pnl_pct,
            days_held=days,
            days_remaining=days_remaining,
            risk_details=details,
        )
