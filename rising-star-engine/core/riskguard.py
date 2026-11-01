"""
Rising Star Trend Engine - Sprint 3 & 4: RiskGuard Micro-Module
Autonomous risk management engine with dynamic position monitoring and volatility sizing:
1. Active Position Auditing:
   - Trailing Stop-Loss: Triggers exit when price drops past predefined percentage (default 10%) below peak.
   - Moving Average Breakdown: Triggers exit if Close < MA50 on >20% above-average volume.
   - Time-Based Holding Period Limit: Enforces 60 trading days timeout.
2. Sprint 4 Enhanced Position Sizing & Dynamic Risk Planning:
   - 14-day Average True Range (ATR) dynamic stop-loss levels.
   - Multi-target take-profit thresholds (1R, 2R, 3R, 5R runners).
   - Volatility-adjusted portfolio position sizing respecting account equity and risk limits.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
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


class RiskPlan(BaseModel):
    """
    Actionable risk management and position sizing execution plan emitted for emerging breakout candidates.
    Adheres to institutional volatility sizing standards (ATR stops and risk-budget allocation).
    """
    model_config = ConfigDict(frozen=True, extra="ignore")

    ticker: str
    entry_price: float = Field(..., gt=0, description="Candidate entry price (latest close).")
    atr_14: float = Field(..., gt=0, description="14-day Average True Range volatility measure.")
    stop_loss_price: float = Field(..., gt=0, description="ATR-based dynamic stop loss price.")
    risk_distance_usd: float = Field(..., gt=0, description="Dollar distance per share to stop loss.")
    risk_pct: float = Field(..., gt=0, description="Percentage risk to stop loss from entry.")
    target_1r: float = Field(..., gt=0, description="Take-profit target 1 (1:1 Risk/Reward).")
    target_2r: float = Field(..., gt=0, description="Take-profit target 2 (2:1 Risk/Reward).")
    target_3r: float = Field(..., gt=0, description="Take-profit target 3 (3:1 Risk/Reward).")
    target_5r: float = Field(..., gt=0, description="Take-profit target 5 (5:1 Risk/Reward runner).")
    account_equity: float = Field(default=100_000.0, ge=0, description="Base portfolio equity in USD.")
    risk_per_trade_usd: float = Field(..., ge=0, description="Max dollar risk allocated to this trade.")
    suggested_shares: int = Field(..., ge=1, description="Recommended position size in shares.")
    position_value_usd: float = Field(..., ge=0, description="Total capital allocated to position.")
    position_pct_of_account: float = Field(..., ge=0, le=100.0, description="Portfolio exposure percentage.")
    max_loss_usd: float = Field(..., ge=0, description="Calculated maximum capital loss if stop is hit.")
    volatility_tier: str = Field(..., description="'LOW', 'NORMAL', or 'HIGH_VOLATILITY'.")
    calculated_at: datetime = Field(default_factory=datetime.utcnow)

    # Aliases for NotificationHub compatibility
    @property
    def stop_loss(self) -> float:
        return self.stop_loss_price

    @property
    def suggested_shares_1k_risk(self) -> int:
        return self.suggested_shares


class RiskGuard:
    """
    Headless autonomous risk management engine.
    - Monitors active positions (trailing stop, MA50 volume breakdown, time limits).
    - Computes ATR-based dynamic stops, take-profit thresholds, and position sizing for emerging candidates.
    """

    def __init__(
        self,
        trailing_stop_pct: float = 10.0,       # 10% trailing stop below peak
        ma_volume_surge_pct: float = 20.0,     # >20% above 50-day avg volume on MA breakdown
        max_holding_days: int = 60,            # 60 trading days timeout
        default_atr_multiplier: float = 2.0,   # 2.0x ATR for dynamic stops
        default_account_equity: float = 100_000.0,
        default_risk_per_trade_pct: float = 1.0, # 1% risk per trade
        max_position_size_pct: float = 20.0,     # Max 20% portfolio allocation
    ):
        self.trailing_stop_pct = trailing_stop_pct
        self.ma_vol_multiplier = 1.0 + (ma_volume_surge_pct / 100.0)  # 1.20x
        self.max_holding_days = max_holding_days
        self.default_atr_multiplier = default_atr_multiplier
        self.default_account_equity = default_account_equity
        self.default_risk_per_trade_pct = default_risk_per_trade_pct
        self.max_position_size_pct = max_position_size_pct

    @staticmethod
    def compute_atr(
        highs: Union[List[float], Any],
        lows: Union[List[float], Any],
        closes: Union[List[float], Any],
        period: int = 14,
    ) -> float:
        """
        Calculates the 14-day Average True Range (ATR) using explicit .iloc[] positional access
        to prevent any Pandas FutureWarning deprecations.
        """
        n = min(len(highs), len(lows), len(closes))
        if n < 2:
            return 1.0

        tr_values: List[float] = []
        is_pos_high = hasattr(highs, "iloc")
        is_pos_low = hasattr(lows, "iloc")
        is_pos_close = hasattr(closes, "iloc")

        for i in range(1, n):
            h = float(highs.iloc[i] if is_pos_high else highs[i])
            l = float(lows.iloc[i] if is_pos_low else lows[i])
            c_prev = float(closes.iloc[i - 1] if is_pos_close else closes[i - 1])

            tr = max(h - l, abs(h - c_prev), abs(l - c_prev))
            tr_values.append(tr)

        if not tr_values:
            return 1.0

        bars_to_use = min(len(tr_values), period)
        recent_trs = tr_values[-bars_to_use:]
        return round(float(sum(recent_trs) / len(recent_trs)), 2)

    def compute_position_sizing(
        self,
        ticker: str,
        entry_price: float,
        highs: Union[List[float], Any],
        lows: Union[List[float], Any],
        closes: Union[List[float], Any],
        account_equity: Optional[float] = None,
        risk_per_trade_pct: Optional[float] = None,
        atr_multiplier: Optional[float] = None,
        max_position_pct: Optional[float] = None,
    ) -> RiskPlan:
        """
        Calculates dynamic ATR stop-loss, take-profit thresholds (1R, 2R, 3R, 5R),
        and recommended share size based on portfolio risk tolerance.
        """
        equity = account_equity if account_equity is not None else self.default_account_equity
        risk_pct_val = risk_per_trade_pct if risk_per_trade_pct is not None else self.default_risk_per_trade_pct
        mult = atr_multiplier if atr_multiplier is not None else self.default_atr_multiplier
        max_pos_pct = max_position_pct if max_position_pct is not None else self.max_position_size_pct

        # 1. Volatility Calculation
        atr = self.compute_atr(highs, lows, closes, period=14)
        if atr <= 0:
            atr = round(entry_price * 0.025, 2)  # 2.5% fallback ATR

        # 2. Dynamic Stop-Loss & Risk Distance
        risk_distance = round(atr * mult, 2)
        if risk_distance >= entry_price:
            risk_distance = round(entry_price * 0.15, 2)  # Cap max risk distance at 15%

        stop_loss_price = round(max(0.01, entry_price - risk_distance), 2)
        risk_pct = round((risk_distance / entry_price) * 100.0, 2)

        # 3. Take-Profit Levels (1R, 2R, 3R, 5R runner)
        target_1r = round(entry_price + risk_distance, 2)
        target_2r = round(entry_price + (2.0 * risk_distance), 2)
        target_3r = round(entry_price + (3.0 * risk_distance), 2)
        target_5r = round(entry_price + (5.0 * risk_distance), 2)

        # 4. Position Sizing
        # Dollar risk budget = Account Equity * (Risk % / 100)
        risk_budget_usd = round(equity * (risk_pct_val / 100.0), 2)
        shares_by_risk = int(risk_budget_usd / (risk_distance or 1.0))

        # Hard cap by maximum position allocation (e.g. max 20% of account)
        max_capital_allowed = equity * (max_pos_pct / 100.0)
        shares_by_capital = int(max_capital_allowed / entry_price)

        suggested_shares = max(1, min(shares_by_risk, shares_by_capital))
        position_value = round(suggested_shares * entry_price, 2)
        pos_pct = round((position_value / equity) * 100.0, 2)
        max_loss = round(suggested_shares * risk_distance, 2)

        # 5. Volatility Tier
        atr_ratio = atr / entry_price
        if atr_ratio < 0.02:
            vol_tier = "LOW"
        elif atr_ratio > 0.045:
            vol_tier = "HIGH_VOLATILITY"
        else:
            vol_tier = "NORMAL"

        return RiskPlan(
            ticker=ticker.strip().upper(),
            entry_price=round(entry_price, 2),
            atr_14=atr,
            stop_loss_price=stop_loss_price,
            risk_distance_usd=risk_distance,
            risk_pct=risk_pct,
            target_1r=target_1r,
            target_2r=target_2r,
            target_3r=target_3r,
            target_5r=target_5r,
            account_equity=round(equity, 2),
            risk_per_trade_usd=risk_budget_usd,
            suggested_shares=suggested_shares,
            position_value_usd=position_value,
            position_pct_of_account=pos_pct,
            max_loss_usd=max_loss,
            volatility_tier=vol_tier,
            calculated_at=datetime.utcnow(),
        )

    def evaluate_position(self, position: PositionState) -> RiskStatusPayload:
        """
        Pure headless function that evaluates an active position against all exit risk limits.
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

        # 1. Trailing Stop-Loss Evaluation
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

        # 2. Moving Average Breakdown (Close < MA50 on >20% Above-Avg Volume)
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

        # 3. Time-Based Holding Period Limit (60 Trading Days)
        days_remaining = max(0, self.max_holding_days - days)
        details["days_held"] = days
        details["max_holding_days"] = self.max_holding_days

        is_time_limit_reached = days >= self.max_holding_days
        if is_time_limit_reached:
            exit_reasons.append(
                f"Time Limit Expired: Position held for {days} trading days "
                f"(max allowed: {self.max_holding_days} days)"
            )

        # Action Resolution
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
