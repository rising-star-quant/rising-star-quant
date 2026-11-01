"""
Rising Star Trend Engine - Sprint 5: Historical Backtesting Engine
Evaluates multi-year quantitative performance of Rising Star Trend strategy across S&P 500 equities.
Strictly headless pure backend logic, Pydantic v2 validated, and reproducible.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from core.indicatorengine import IndicatorEngine, IndicatorMetrics
from core.ruleengine import CompanyProfile, RuleEngine
from core.scoringengine import ScoringEngine
from core.riskguard import PositionState, RiskGuard

logger = logging.getLogger("BacktestEngine")


class BacktestConfig(BaseModel):
    """Configuration parameters for historical simulation."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    initial_capital: float = Field(default=100_000.0, ge=1000.0)
    risk_per_trade_pct: float = Field(default=1.0, gt=0.0, le=10.0)
    max_active_positions: int = Field(default=8, ge=1, le=50)
    trailing_stop_pct: float = Field(default=0.10, ge=0.02, le=0.30)
    ma_breakdown_vol_mult: float = Field(default=1.20, ge=1.0, le=3.0)
    max_holding_days: int = Field(default=60, ge=5, le=250)
    min_score: float = Field(default=85.0, ge=50.0, le=100.0)
    require_breakout: bool = Field(default=True)
    require_sp500_eligibility: bool = Field(default=False)
    use_atr_stops: bool = Field(default=True)
    atr_stop_multiplier: float = Field(default=2.0, ge=1.0, le=5.0)


class BacktestTrade(BaseModel):
    """Records an individual executed trade within the simulation."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    ticker: str
    entry_date: str
    entry_price: float
    shares: int
    exit_date: str
    exit_price: float
    exit_reason: str
    pnl_dollars: float
    pnl_pct: float
    holding_days: int
    peak_price: float


class EquityCurvePoint(BaseModel):
    """Daily equity snapshot along the backtesting timeline."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    date: str
    portfolio_equity: float
    cash: float
    open_positions_count: int
    cumulative_return_pct: float
    drawdown_pct: float


class BacktestResult(BaseModel):
    """Aggregated quantitative performance metrics."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    initial_capital: float
    final_equity: float
    total_return_pct: float
    annualized_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown_pct: float
    avg_trade_pnl_pct: float
    avg_holding_days: float
    trades: List[BacktestTrade] = Field(default_factory=list)
    equity_curve: List[EquityCurvePoint] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)


class BacktestEngine:
    """
    Simulates the Rising Star Trend strategy across historical price bars.
    Executes day-by-day rolling window evaluations:
    - Indicator calculations on historical 250-bar lookback
    - ScoringEngine multi-factor synthesis and Buy Alert validation
    - RiskGuard exit evaluation (Trailing Stop, MA50 breakdown, Max Holding period)
    """

    def __init__(self, config: Optional[BacktestConfig] = None) -> None:
        self.config = config or BacktestConfig()
        self.indicator_engine = IndicatorEngine()
        self.scoring_engine = ScoringEngine()
        self.risk_guard = RiskGuard(
            trailing_stop_pct=self.config.trailing_stop_pct,
            ma_breakdown_volume_multiplier=self.config.ma_breakdown_vol_mult,
            max_holding_days=self.config.max_holding_days,
        )

    def run_single_ticker(
        self,
        ticker: str,
        df: pd.DataFrame,
        profile: Optional[CompanyProfile] = None,
    ) -> BacktestResult:
        """Runs backtest on a single ticker OHLCV dataframe."""
        return self.run_portfolio({ticker: df}, profiles={ticker: profile} if profile else None)

    def run_portfolio(
        self,
        historical_data: Dict[str, pd.DataFrame],
        profiles: Optional[Dict[str, CompanyProfile]] = None,
    ) -> BacktestResult:
        """
        Runs portfolio-level event-driven backtest across multiple assets.
        Aligns dates across all tickers to simulate realistic cash constraints.
        """
        profiles = profiles or {}
        cleaned_data: Dict[str, pd.DataFrame] = {}

        # Normalize data columns & index
        for sym, df in historical_data.items():
            if df is None or len(df) < 60:
                continue
            df_norm = df.copy()
            df_norm.columns = [str(c).capitalize() for c in df_norm.columns]
            if "Close" not in df_norm.columns or "High" not in df_norm.columns or "Low" not in df_norm.columns or "Volume" not in df_norm.columns:
                continue
            cleaned_data[sym] = df_norm

        if not cleaned_data:
            return self._empty_result()

        # Build chronological timeline across all tickers
        all_dates_set = set()
        for df in cleaned_data.values():
            for idx in df.index:
                all_dates_set.add(str(idx)[:10])
        timeline = sorted(list(all_dates_set))

        # Backtest state
        cash = float(self.config.initial_capital)
        closed_trades: List[BacktestTrade] = []
        equity_curve: List[EquityCurvePoint] = []
        
        # open_positions: ticker -> dict of position attributes
        open_positions: Dict[str, Dict[str, Any]] = {}
        peak_equity = float(self.config.initial_capital)

        for date_str in timeline:
            # 1. Update existing open positions and check exits
            tickers_to_close: List[Tuple[str, float, str]] = []

            for sym, pos in list(open_positions.items()):
                df = cleaned_data.get(sym)
                if df is None:
                    continue

                matching_rows = df[df.index.astype(str).str.startswith(date_str)]
                if matching_rows.empty:
                    continue

                row = matching_rows.iloc[0]
                high = float(row["High"])
                low = float(row["Low"])
                close = float(row["Close"])
                volume = float(row["Volume"])

                pos["days_held"] += 1
                if high > pos["peak_price"]:
                    pos["peak_price"] = high
                    pos["trailing_stop_price"] = high * (1.0 - self.config.trailing_stop_pct)

                # Check Exit Criteria via RiskGuard rules
                exit_price = None
                exit_reason = None

                # Rule A: Trailing Stop Loss
                if low <= pos["trailing_stop_price"]:
                    exit_price = min(pos["trailing_stop_price"], float(row.get("Open", close)))
                    exit_reason = "TRAILING_STOP"
                # Rule B: ATR Stop Loss (if enabled)
                elif self.config.use_atr_stops and pos.get("atr_stop_price") and low <= pos["atr_stop_price"]:
                    exit_price = min(pos["atr_stop_price"], float(row.get("Open", close)))
                    exit_reason = "ATR_STOP"
                # Rule C: Max Holding Days
                elif pos["days_held"] >= self.config.max_holding_days:
                    exit_price = close
                    exit_reason = "MAX_HOLDING_DAYS"
                else:
                    # Rule D: Moving Average Breakdown with volume
                    current_idx = df.index.get_loc(row.name) if row.name in df.index else -1
                    if isinstance(current_idx, int) and current_idx >= 50:
                        hist_slice = df.iloc[: current_idx + 1]
                        ma50 = float(hist_slice["Close"].rolling(50).mean().iloc[-1])
                        avg_vol = float(hist_slice["Volume"].rolling(50).mean().iloc[-1])
                        if close < ma50 and volume >= (avg_vol * self.config.ma_breakdown_vol_mult):
                            exit_price = close
                            exit_reason = "MA50_BREAKDOWN"

                if exit_reason and exit_price is not None:
                    tickers_to_close.append((sym, exit_price, exit_reason))

            # Process closures
            for sym, exit_price, exit_reason in tickers_to_close:
                pos = open_positions.pop(sym)
                shares = pos["shares"]
                proceeds = shares * exit_price
                cash += proceeds
                pnl_dollars = proceeds - (shares * pos["entry_price"])
                pnl_pct = ((exit_price - pos["entry_price"]) / pos["entry_price"]) * 100.0

                closed_trades.append(
                    BacktestTrade(
                        ticker=sym,
                        entry_date=pos["entry_date"],
                        entry_price=round(pos["entry_price"], 2),
                        shares=shares,
                        exit_date=date_str,
                        exit_price=round(exit_price, 2),
                        exit_reason=exit_reason,
                        pnl_dollars=round(pnl_dollars, 2),
                        pnl_pct=round(pnl_pct, 2),
                        holding_days=pos["days_held"],
                        peak_price=round(pos["peak_price"], 2),
                    )
                )

            # 2. Check for New Entry Signals across universe
            if len(open_positions) < self.config.max_active_positions and cash > 1000.0:
                for sym, df in cleaned_data.items():
                    if sym in open_positions:
                        continue
                    if len(open_positions) >= self.config.max_active_positions:
                        break

                    matching_rows = df[df.index.astype(str).str.startswith(date_str)]
                    if matching_rows.empty:
                        continue

                    row = matching_rows.iloc[0]
                    row_loc = df.index.get_loc(row.name) if row.name in df.index else -1
                    if not isinstance(row_loc, int) or row_loc < 50:
                        continue

                    hist_window = df.iloc[max(0, row_loc - 249) : row_loc + 1]
                    if len(hist_window) < 50:
                        continue

                    # Calculate Indicators
                    try:
                        metrics: IndicatorMetrics = self.indicator_engine.calculate(
                            ticker=sym,
                            df=hist_window,
                            sector_etf_df=None,
                        )
                    except Exception:
                        continue

                    # Check Eligibility if required
                    if self.config.require_sp500_eligibility:
                        profile = profiles.get(sym)
                        if profile:
                            elig = RuleEngine.evaluate(profile)
                            if not elig.is_eligible:
                                continue

                    # Calculate Score
                    try:
                        score_payload = self.scoring_engine.calculate_score(
                            ticker=sym,
                            indicator_metrics=metrics,
                            short_interest_pct=0.03,
                            sector_sentiment=75.0,
                            macro_environment="RISK_ON",
                        )
                    except Exception:
                        continue

                    # Validate Trigger
                    entry_signal = (
                        score_payload.rising_star_score >= self.config.min_score
                        and (not self.config.require_breakout or metrics.breakout_triggered)
                    )

                    if entry_signal:
                        curr_close = float(row["Close"])
                        if curr_close <= 0.01:
                            continue

                        # Risk sizing calculation
                        risk_capital = (self.config.initial_capital * (self.config.risk_per_trade_pct / 100.0))
                        
                        # Stop distance based on ATR or Trailing Stop
                        atr_val = metrics.volume_metrics.avg_volume_50d  # fallback proxy
                        # Compute ATR(14) if possible
                        if len(hist_window) >= 15:
                            highs = hist_window["High"].values
                            lows = hist_window["Low"].values
                            closes = hist_window["Close"].values
                            tr = np.maximum(
                                highs[1:] - lows[1:],
                                np.maximum(
                                    np.abs(highs[1:] - closes[:-1]),
                                    np.abs(lows[1:] - closes[:-1]),
                                ),
                            )
                            atr = float(np.mean(tr[-14:]))
                        else:
                            atr = curr_close * 0.03

                        stop_distance = max(atr * self.config.atr_stop_multiplier, curr_close * self.config.trailing_stop_pct)
                        shares_by_risk = math.floor(risk_capital / stop_distance) if stop_distance > 0 else 10
                        max_shares_by_cash = math.floor((cash * 0.95) / curr_close)
                        shares = max(1, min(shares_by_risk, max_shares_by_cash))

                        cost = shares * curr_close
                        if cost <= cash and shares > 0:
                            cash -= cost
                            open_positions[sym] = {
                                "entry_date": date_str,
                                "entry_price": curr_close,
                                "shares": shares,
                                "peak_price": curr_close,
                                "trailing_stop_price": curr_close * (1.0 - self.config.trailing_stop_pct),
                                "atr_stop_price": curr_close - (atr * self.config.atr_stop_multiplier),
                                "days_held": 0,
                            }

            # 3. Mark to Market Portfolio Equity
            open_position_val = 0.0
            for sym, pos in open_positions.items():
                df = cleaned_data.get(sym)
                matching_rows = df[df.index.astype(str).str.startswith(date_str)] if df is not None else None
                if matching_rows is not None and not matching_rows.empty:
                    current_price = float(matching_rows.iloc[0]["Close"])
                else:
                    current_price = pos["entry_price"]
                open_position_val += pos["shares"] * current_price

            total_equity = cash + open_position_val
            if total_equity > peak_equity:
                peak_equity = total_equity

            drawdown_pct = ((peak_equity - total_equity) / peak_equity) * 100.0 if peak_equity > 0 else 0.0
            cum_return_pct = ((total_equity - self.config.initial_capital) / self.config.initial_capital) * 100.0

            equity_curve.append(
                EquityCurvePoint(
                    date=date_str,
                    portfolio_equity=round(total_equity, 2),
                    cash=round(cash, 2),
                    open_positions_count=len(open_positions),
                    cumulative_return_pct=round(cum_return_pct, 2),
                    drawdown_pct=round(drawdown_pct, 2),
                )
            )

        # Close any open positions at last available price for final reckoning
        last_date = timeline[-1] if timeline else "END"
        for sym, pos in list(open_positions.items()):
            df = cleaned_data.get(sym)
            final_price = float(df["Close"].iloc[-1]) if df is not None and len(df) > 0 else pos["entry_price"]
            shares = pos["shares"]
            proceeds = shares * final_price
            cash += proceeds
            pnl_dollars = proceeds - (shares * pos["entry_price"])
            pnl_pct = ((final_price - pos["entry_price"]) / pos["entry_price"]) * 100.0
            closed_trades.append(
                BacktestTrade(
                    ticker=sym,
                    entry_date=pos["entry_date"],
                    entry_price=round(pos["entry_price"], 2),
                    shares=shares,
                    exit_date=last_date,
                    exit_price=round(final_price, 2),
                    exit_reason="SIMULATION_END",
                    pnl_dollars=round(pnl_dollars, 2),
                    pnl_pct=round(pnl_pct, 2),
                    holding_days=pos["days_held"],
                    peak_price=round(pos["peak_price"], 2),
                )
            )

        final_equity = cash
        return self._compute_summary_metrics(
            initial_capital=self.config.initial_capital,
            final_equity=final_equity,
            trades=closed_trades,
            equity_curve=equity_curve,
            timeline_length=len(timeline),
        )

    def _compute_summary_metrics(
        self,
        initial_capital: float,
        final_equity: float,
        trades: List[BacktestTrade],
        equity_curve: List[EquityCurvePoint],
        timeline_length: int,
    ) -> BacktestResult:
        """Calculates quantitative performance stats: Win Rate, Sharpe, Drawdown, Profit Factor."""
        total_return_pct = ((final_equity - initial_capital) / initial_capital) * 100.0
        years = max(timeline_length / 252.0, 0.1)
        annualized_return_pct = (((final_equity / initial_capital) ** (1.0 / years)) - 1.0) * 100.0

        total_trades = len(trades)
        wins = [t for t in trades if t.pnl_dollars > 0]
        losses = [t for t in trades if t.pnl_dollars <= 0]
        win_rate_pct = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0

        gross_profits = sum(t.pnl_dollars for t in wins)
        gross_losses = abs(sum(t.pnl_dollars for t in losses))
        if gross_losses > 0:
            profit_factor = round(gross_profits / gross_losses, 2)
        else:
            profit_factor = round(gross_profits, 2) if gross_profits > 0 else 1.0

        # Max Drawdown
        max_dd = max([pt.drawdown_pct for pt in equity_curve], default=0.0)

        # Daily returns for Sharpe Ratio
        if len(equity_curve) > 5:
            eq_series = pd.Series([pt.portfolio_equity for pt in equity_curve])
            daily_returns = eq_series.pct_change().dropna()
            mean_ret = float(daily_returns.mean())
            std_ret = float(daily_returns.std())
            sharpe_ratio = round((mean_ret / std_ret) * math.sqrt(252), 2) if std_ret > 0 else 0.0
        else:
            sharpe_ratio = 0.0

        avg_trade_pnl = float(np.mean([t.pnl_pct for t in trades])) if trades else 0.0
        avg_holding = float(np.mean([t.holding_days for t in trades])) if trades else 0.0

        return BacktestResult(
            initial_capital=round(initial_capital, 2),
            final_equity=round(final_equity, 2),
            total_return_pct=round(total_return_pct, 2),
            annualized_return_pct=round(annualized_return_pct, 2),
            total_trades=total_trades,
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate_pct=round(win_rate_pct, 2),
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            max_drawdown_pct=round(max_dd, 2),
            avg_trade_pnl_pct=round(avg_trade_pnl, 2),
            avg_holding_days=round(avg_holding, 1),
            trades=trades,
            equity_curve=equity_curve,
        )

    def _empty_result(self) -> BacktestResult:
        """Fallback result when no valid data is provided."""
        return BacktestResult(
            initial_capital=self.config.initial_capital,
            final_equity=self.config.initial_capital,
            total_return_pct=0.0,
            annualized_return_pct=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate_pct=0.0,
            profit_factor=1.0,
            sharpe_ratio=0.0,
            max_drawdown_pct=0.0,
            avg_trade_pnl_pct=0.0,
            avg_holding_days=0.0,
        )
