"""
Rising Star Trend Engine - Sprint 5: Paper Trading & Portfolio Tracker
Monitors active paper trading positions triggered by BUY ALERTS.
Tracks entry, peak high, dynamic ATR/trailing stops, P&L, holding duration, and RiskGuard exits.
Strictly headless, Pydantic v2 validated, and JSON persistent.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from core.riskguard import PositionState, RiskGuard, RiskPlan

logger = logging.getLogger("PortfolioTracker")


class PaperPosition(BaseModel):
    """Represents a simulated paper trading position."""
    model_config = ConfigDict(extra="ignore")

    id: str
    ticker: str
    status: str = Field(default="OPEN")  # "OPEN" or "CLOSED"
    entry_date: str
    entry_price: float
    shares: int
    invested_amount: float
    peak_price: float
    trailing_stop_price: float
    atr_stop_price: Optional[float] = None
    target_1r: Optional[float] = None
    target_2r: Optional[float] = None
    target_3r: Optional[float] = None
    current_price: float
    current_value: float
    unrealized_pnl_dollars: float
    unrealized_pnl_pct: float
    days_held: int = 0
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    realized_pnl_dollars: Optional[float] = None
    realized_pnl_pct: Optional[float] = None


class PortfolioSummary(BaseModel):
    """High-level snapshot of paper portfolio health."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    total_account_value: float
    cash: float
    invested_capital: float
    total_unrealized_pnl_dollars: float
    total_realized_pnl_dollars: float
    open_positions_count: int
    closed_positions_count: int
    win_rate_pct: float
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PortfolioTracker:
    """
    Manages live simulation of trading book:
    - Opens new paper positions on confirmed Buy Alerts
    - Audits active positions via RiskGuard criteria
    - Executes automated paper exits
    - Persists state to portfolio.json
    """

    def __init__(
        self,
        initial_cash: float = 100_000.0,
        trailing_stop_pct: float = 0.10,
        storage_file: str = "portfolio.json",
    ) -> None:
        self.initial_cash = float(initial_cash)
        self.cash = float(initial_cash)
        self.trailing_stop_pct = trailing_stop_pct
        self.storage_file = storage_file
        self.positions: Dict[str, PaperPosition] = {}
        self.risk_guard = RiskGuard(trailing_stop_pct=trailing_stop_pct)
        self.load()

    def open_position(
        self,
        ticker: str,
        entry_price: float,
        shares: int,
        risk_plan: Optional[RiskPlan] = None,
        entry_date: Optional[str] = None,
    ) -> PaperPosition:
        """Opens a simulated paper position."""
        date_str = entry_date or datetime.utcnow().strftime("%Y-%m-%d")
        pos_id = f"pos-{ticker}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        invested = round(shares * entry_price, 2)
        if invested > self.cash:
            logger.warning(
                "Insufficient paper cash ($%.2f) to open %s position requiring $%.2f. Adjusting shares.",
                self.cash,
                ticker,
                invested,
            )
            shares = max(1, int(self.cash / entry_price))
            invested = round(shares * entry_price, 2)

        self.cash = max(0.0, round(self.cash - invested, 2))

        trailing_stop = round(entry_price * (1.0 - self.trailing_stop_pct), 2)
        atr_stop = risk_plan.stop_loss_price if risk_plan else trailing_stop
        t1 = risk_plan.take_profit_levels.get("1R", round(entry_price * 1.05, 2)) if risk_plan else None
        t2 = risk_plan.take_profit_levels.get("2R", round(entry_price * 1.10, 2)) if risk_plan else None
        t3 = risk_plan.take_profit_levels.get("3R", round(entry_price * 1.20, 2)) if risk_plan else None

        pos = PaperPosition(
            id=pos_id,
            ticker=ticker.upper(),
            status="OPEN",
            entry_date=date_str,
            entry_price=round(entry_price, 2),
            shares=shares,
            invested_amount=invested,
            peak_price=round(entry_price, 2),
            trailing_stop_price=trailing_stop,
            atr_stop_price=atr_stop,
            target_1r=t1,
            target_2r=t2,
            target_3r=t3,
            current_price=round(entry_price, 2),
            current_value=invested,
            unrealized_pnl_dollars=0.0,
            unrealized_pnl_pct=0.0,
            days_held=0,
        )

        self.positions[pos.id] = pos
        logger.info(
            "Opened paper position for %s: %d shares @ $%.2f (Invested: $%.2f, Remaining Cash: $%.2f)",
            ticker,
            shares,
            entry_price,
            invested,
            self.cash,
        )
        self.save()
        return pos

    def audit_positions(
        self,
        latest_quotes: Dict[str, Dict[str, Any]],
        current_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Audits all open positions against current market prices using RiskGuard:
        - Updates peak price & trailing stop
        - Checks for trailing stop breaches, MA50 breakdown, or holding periods
        - Closes triggered positions
        """
        date_str = current_date or datetime.utcnow().strftime("%Y-%m-%d")
        audit_events: List[Dict[str, Any]] = []

        for pos in list(self.positions.values()):
            if pos.status != "OPEN":
                continue

            quote = latest_quotes.get(pos.ticker)
            if not quote:
                continue

            current_price = float(quote.get("current_price", quote.get("close", pos.current_price)))
            high_price = float(quote.get("high", current_price))
            low_price = float(quote.get("low", current_price))
            volume = float(quote.get("volume", 0.0))
            ma50 = float(quote.get("ma50", current_price * 0.95))
            avg_volume_50d = float(quote.get("avg_volume_50d", volume))

            pos.days_held += 1
            if high_price > pos.peak_price:
                pos.peak_price = round(high_price, 2)
                pos.trailing_stop_price = round(pos.peak_price * (1.0 - self.trailing_stop_pct), 2)

            pos.current_price = round(current_price, 2)
            pos.current_value = round(pos.shares * current_price, 2)
            pos.unrealized_pnl_dollars = round(pos.current_value - pos.invested_amount, 2)
            pos.unrealized_pnl_pct = round(
                ((pos.current_price - pos.entry_price) / pos.entry_price) * 100.0, 2
            )

            # Evaluate with RiskGuard
            pos_state = PositionState(
                ticker=pos.ticker,
                entry_price=pos.entry_price,
                highest_price_post_entry=pos.peak_price,
                days_held=pos.days_held,
                current_price=current_price,
                daily_low=low_price,
                ma50=ma50,
                volume=volume,
                avg_volume_50d=avg_volume_50d,
            )

            risk_eval = self.risk_guard.evaluate_active_position(pos_state)

            if risk_eval.exit_triggered:
                # Trigger automated paper exit
                exit_price = risk_eval.stop_price or current_price
                closed_pos = self.close_position(
                    position_id=pos.id,
                    exit_price=exit_price,
                    exit_reason=f"RiskGuard: {risk_eval.trigger_reason}",
                    exit_date=date_str,
                )
                audit_events.append({
                    "action": "CLOSED",
                    "ticker": pos.ticker,
                    "reason": risk_eval.trigger_reason,
                    "exit_price": exit_price,
                    "realized_pnl": closed_pos.realized_pnl_dollars,
                    "realized_pnl_pct": closed_pos.realized_pnl_pct,
                })
            else:
                audit_events.append({
                    "action": "HOLD",
                    "ticker": pos.ticker,
                    "current_price": current_price,
                    "unrealized_pnl_pct": pos.unrealized_pnl_pct,
                    "trailing_stop": pos.trailing_stop_price,
                })

        self.save()
        return audit_events

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        exit_reason: str = "MANUAL_CLOSE",
        exit_date: Optional[str] = None,
    ) -> PaperPosition:
        """Closes an open position and credits proceeds back to cash."""
        if position_id not in self.positions:
            raise KeyError(f"Position '{position_id}' not found.")

        pos = self.positions[position_id]
        if pos.status == "CLOSED":
            return pos

        date_str = exit_date or datetime.utcnow().strftime("%Y-%m-%d")
        proceeds = round(pos.shares * exit_price, 2)
        realized_pnl = round(proceeds - pos.invested_amount, 2)
        realized_pct = round(((exit_price - pos.entry_price) / pos.entry_price) * 100.0, 2)

        pos.status = "CLOSED"
        pos.exit_date = date_str
        pos.exit_price = round(exit_price, 2)
        pos.exit_reason = exit_reason
        pos.realized_pnl_dollars = realized_pnl
        pos.realized_pnl_pct = realized_pct
        pos.current_value = 0.0
        pos.unrealized_pnl_dollars = 0.0
        pos.unrealized_pnl_pct = 0.0

        self.cash = round(self.cash + proceeds, 2)
        logger.info(
            "Closed position %s (%s) @ $%.2f. Realized P&L: $%.2f (%+.2f%%). Cash: $%.2f",
            pos.id,
            pos.ticker,
            exit_price,
            realized_pnl,
            realized_pct,
            self.cash,
        )
        self.save()
        return pos

    def get_summary(self) -> PortfolioSummary:
        """Calculates portfolio valuation and performance."""
        open_positions = [p for p in self.positions.values() if p.status == "OPEN"]
        closed_positions = [p for p in self.positions.values() if p.status == "CLOSED"]

        invested_capital = sum(p.current_value for p in open_positions)
        unrealized_pnl = sum(p.unrealized_pnl_dollars for p in open_positions)
        realized_pnl = sum(p.realized_pnl_dollars or 0.0 for p in closed_positions)
        total_account_value = round(self.cash + invested_capital, 2)

        wins = [p for p in closed_positions if (p.realized_pnl_dollars or 0.0) > 0]
        win_rate = (len(wins) / len(closed_positions) * 100.0) if closed_positions else 0.0

        return PortfolioSummary(
            total_account_value=total_account_value,
            cash=round(self.cash, 2),
            invested_capital=round(invested_capital, 2),
            total_unrealized_pnl_dollars=round(unrealized_pnl, 2),
            total_realized_pnl_dollars=round(realized_pnl, 2),
            open_positions_count=len(open_positions),
            closed_positions_count=len(closed_positions),
            win_rate_pct=round(win_rate, 2),
        )

    def save(self, filepath: Optional[str] = None) -> None:
        """Persists current state to JSON file."""
        target = filepath or self.storage_file
        data = {
            "initial_cash": self.initial_cash,
            "cash": self.cash,
            "trailing_stop_pct": self.trailing_stop_pct,
            "positions": {pid: p.model_dump(mode="json") for pid, p in self.positions.items()},
            "summary": self.get_summary().model_dump(mode="json"),
        }
        try:
            with open(target, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.debug("Saved portfolio state to %s", target)
        except Exception as exc:
            logger.error("Failed to save portfolio to %s: %s", target, exc)

    def load(self, filepath: Optional[str] = None) -> None:
        """Loads portfolio state from JSON file if it exists."""
        target = filepath or self.storage_file
        if not os.path.exists(target):
            return

        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.initial_cash = float(data.get("initial_cash", self.initial_cash))
            self.cash = float(data.get("cash", self.cash))
            self.trailing_stop_pct = float(data.get("trailing_stop_pct", self.trailing_stop_pct))
            raw_pos = data.get("positions", {})
            self.positions = {pid: PaperPosition(**pdata) for pid, pdata in raw_pos.items()}
            logger.info("Loaded %d positions from %s", len(self.positions), target)
        except Exception as exc:
            logger.warning("Could not read portfolio file %s: %s", target, exc)
