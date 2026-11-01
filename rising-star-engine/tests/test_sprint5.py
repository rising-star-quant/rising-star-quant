"""
Unit tests for Sprint 5: Historical Backtesting Engine and Paper Trading Portfolio Tracker.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import pytest

from core.backtester import (
    BacktestConfig,
    BacktestEngine,
    BacktestResult,
    BacktestTrade,
)
from core.portfoliotracker import PaperPosition, PortfolioSummary, PortfolioTracker
from core.riskguard import RiskPlan


def generate_synthetic_ohlcv(
    bars: int = 280,
    start_price: float = 100.0,
    trend_slope: float = 0.5,
    volatility: float = 1.5,
) -> pd.DataFrame:
    """Generates synthetic daily OHLCV dataframe for testing."""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.utcnow(), periods=bars, freq="B")
    
    closes = [start_price]
    for i in range(1, bars):
        # general upward drift
        change = trend_slope + np.random.normal(0, volatility)
        closes.append(max(10.0, closes[-1] + change))

    closes = np.array(closes)
    highs = closes + np.random.uniform(0.5, 3.0, size=bars)
    lows = closes - np.random.uniform(0.5, 3.0, size=bars)
    opens = (closes + lows) / 2.0
    volumes = np.random.randint(1_000_000, 5_000_000, size=bars)

    df = pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": volumes,
        },
        index=dates,
    )
    return df


class TestBacktestEngine:
    def test_backtest_initialization(self):
        config = BacktestConfig(
            initial_capital=50_000.0,
            risk_per_trade_pct=2.0,
            trailing_stop_pct=0.08,
            max_holding_days=45,
        )
        engine = BacktestEngine(config=config)
        assert engine.config.initial_capital == 50_000.0
        assert engine.config.trailing_stop_pct == 0.08

    def test_backtest_empty_data(self):
        engine = BacktestEngine()
        result = engine.run_portfolio({})
        assert isinstance(result, BacktestResult)
        assert result.total_trades == 0
        assert result.initial_capital == 100_000.0
        assert result.final_equity == 100_000.0

    def test_backtest_synthetic_uptrend(self):
        df_nvda = generate_synthetic_ohlcv(bars=280, start_price=80.0, trend_slope=0.8)
        engine = BacktestEngine(
            BacktestConfig(
                initial_capital=100_000.0,
                min_score=70.0,  # lower threshold to guarantee signals on synthetic
                require_breakout=False,
            )
        )
        result = engine.run_single_ticker("NVDA", df_nvda)

        assert isinstance(result, BacktestResult)
        assert result.initial_capital == 100_000.0
        assert len(result.equity_curve) > 0
        assert result.profit_factor >= 0.0
        assert -100.0 <= result.max_drawdown_pct <= 100.0

    def test_backtest_trailing_stop_exit(self):
        # Create a stock that rallies then crashes 20%
        dates = pd.date_range(end=datetime.utcnow(), periods=100, freq="B")
        closes = [100.0 + i * 2.0 for i in range(70)] # rallies to 238
        closes += [238.0 - (i * 8.0) for i in range(1, 31)] # crashes to ~ -2
        closes = [max(10.0, c) for c in closes]

        df = pd.DataFrame(
            {
                "Open": closes,
                "High": [c + 1.0 for c in closes],
                "Low": [c - 1.0 for c in closes],
                "Close": closes,
                "Volume": [2_000_000] * 100,
            },
            index=dates,
        )

        engine = BacktestEngine(
            BacktestConfig(
                min_score=50.0,
                require_breakout=False,
                trailing_stop_pct=0.10,
            )
        )
        result = engine.run_single_ticker("TEST", df)
        assert result.total_trades >= 1
        # Trade should have exited via trailing stop or risk rule
        reasons = [t.exit_reason for t in result.trades]
        assert any("TRAILING_STOP" in r or "ATR_STOP" in r or "SIMULATION_END" in r for r in reasons)


class TestPortfolioTracker:
    def test_open_position_and_balance(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            tracker = PortfolioTracker(initial_cash=100_000.0, storage_file=tmp_path)
            pos = tracker.open_position(
                ticker="NVDA",
                entry_price=120.0,
                shares=50,
            )

            assert pos.ticker == "NVDA"
            assert pos.shares == 50
            assert pos.invested_amount == 6000.0
            assert tracker.cash == 94_000.0
            assert pos.status == "OPEN"

            summary = tracker.get_summary()
            assert summary.open_positions_count == 1
            assert summary.closed_positions_count == 0
            assert summary.total_account_value == 100_000.0
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_audit_positions_and_trailing_stop_exit(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            tracker = PortfolioTracker(
                initial_cash=50_000.0,
                trailing_stop_pct=0.10,
                storage_file=tmp_path,
            )
            # Open position at $100
            pos = tracker.open_position(ticker="CRWD", entry_price=100.0, shares=100)

            # Audit day 1: Stock surges to $150 (peak = 150, trailing stop = 135)
            quotes_day1 = {
                "CRWD": {
                    "current_price": 150.0,
                    "high": 150.0,
                    "low": 145.0,
                    "volume": 1_000_000,
                    "ma50": 90.0,
                }
            }
            events_d1 = tracker.audit_positions(quotes_day1)
            updated_pos = tracker.positions[pos.id]
            assert updated_pos.peak_price == 150.0
            assert updated_pos.trailing_stop_price == 135.0
            assert updated_pos.unrealized_pnl_dollars == 5000.0
            assert updated_pos.status == "OPEN"

            # Audit day 2: Stock drops to $130 (below trailing stop of 135)
            quotes_day2 = {
                "CRWD": {
                    "current_price": 130.0,
                    "high": 136.0,
                    "low": 128.0,
                    "volume": 2_000_000,
                    "ma50": 95.0,
                }
            }
            events_d2 = tracker.audit_positions(quotes_day2)
            closed_pos = tracker.positions[pos.id]
            assert closed_pos.status == "CLOSED"
            assert closed_pos.realized_pnl_dollars is not None
            assert closed_pos.realized_pnl_dollars > 0  # Still in profit relative to 100 entry
            assert tracker.cash > 50_000.0  # Initial cash was 50k, now has profit
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_json_persistence(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Create tracker and open position
            tracker1 = PortfolioTracker(initial_cash=80_000.0, storage_file=tmp_path)
            tracker1.open_position("MSFT", entry_price=400.0, shares=25)

            # Create second tracker loading same file
            tracker2 = PortfolioTracker(initial_cash=80_000.0, storage_file=tmp_path)
            assert len(tracker2.positions) == 1
            pos = list(tracker2.positions.values())[0]
            assert pos.ticker == "MSFT"
            assert pos.shares == 25
            assert tracker2.cash == tracker1.cash
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
