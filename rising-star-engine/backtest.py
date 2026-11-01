"""
Rising Star Trend Engine - Standalone Backtest CLI Runner (Sprint 5)
Executes historical strategy simulation on specified tickers or S&P 500 components.
Calculates Win Rate, Sharpe Ratio, Profit Factor, Max Drawdown, and exports results.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from core.backtester import BacktestConfig, BacktestEngine, BacktestResult
from core.dataconnector import DataConnector
from core.universe import FALLBACK_SP500_TICKERS, fetch_sp500_tickers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("BacktestRunner")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rising Star Trend Engine - Historical Backtester",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=["NVDA", "CRWD", "MSFT", "AAPL", "AMD"],
        help="List of tickers to backtest",
    )
    parser.add_argument(
        "--sp500",
        action="store_true",
        help="Use full S&P 500 components for the simulation",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of tickers when using --sp500",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=100_000.0,
        help="Starting simulation capital (default: $100,000)",
    )
    parser.add_argument(
        "--risk-pct",
        type=float,
        default=1.0,
        help="Risk per trade percentage (default: 1.0%%)",
    )
    parser.add_argument(
        "--trailing-stop",
        type=float,
        default=0.10,
        help="Trailing stop loss percentage (default: 0.10 = 10%%)",
    )
    parser.add_argument(
        "--max-holding-days",
        type=int,
        default=60,
        help="Maximum holding period in days (default: 60)",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default="backtest_results.json",
        help="Output path for backtest summary JSON",
    )
    parser.add_argument(
        "--output-trades-csv",
        type=str,
        default="backtest_trades.csv",
        help="Output path for detailed trade log CSV",
    )

    args = parser.parse_args()

    # Determine universe
    if args.sp500:
        logger.info("Fetching S&P 500 components for backtest...")
        tickers = fetch_sp500_tickers()
        if args.limit and args.limit > 0:
            tickers = tickers[: args.limit]
    else:
        tickers = [t.strip().upper() for t in args.tickers if t.strip()]

    logger.info("Starting historical backtest for %d tickers...", len(tickers))
    connector = DataConnector()
    hist_data: Dict[str, pd.DataFrame] = {}

    for sym in tickers:
        try:
            mdata = connector.fetch_market_data(sym)
            if mdata.historical_bars is not None and len(mdata.historical_bars) >= 60:
                hist_data[sym] = mdata.historical_bars
                logger.info("Loaded %d bars for %s", len(mdata.historical_bars), sym)
        except Exception as exc:
            logger.warning("Could not load data for %s: %s", sym, exc)

    if not hist_data:
        logger.error("No historical market data retrieved. Aborting backtest.")
        sys.exit(1)

    config = BacktestConfig(
        initial_capital=args.capital,
        risk_per_trade_pct=args.risk_pct,
        trailing_stop_pct=args.trailing_stop,
        max_holding_days=args.max_holding_days,
    )

    engine = BacktestEngine(config=config)
    result: BacktestResult = engine.run_portfolio(hist_data)

    # Print summary table
    print("\n" + "=" * 60)
    print("       RISING STAR TREND ENGINE - BACKTEST RESULTS       ")
    print("=" * 60)
    print(f"Initial Capital:       ${result.initial_capital:,.2f}")
    print(f"Final Equity:          ${result.final_equity:,.2f}")
    print(f"Total Return:          {result.total_return_pct:+.2f}%")
    print(f"Annualized Return:     {result.annualized_return_pct:+.2f}%")
    print(f"Total Trades:          {result.total_trades}")
    print(f"Winning Trades:        {result.winning_trades} ({result.win_rate_pct:.1f}%)")
    print(f"Losing Trades:         {result.losing_trades}")
    print(f"Profit Factor:         {result.profit_factor:.2f}")
    print(f"Annualized Sharpe:     {result.sharpe_ratio:.2f}")
    print(f"Max Drawdown:          {result.max_drawdown_pct:.2f}%")
    print(f"Avg Trade P&L:         {result.avg_trade_pnl_pct:+.2f}%")
    print(f"Avg Holding Days:      {result.avg_holding_days:.1f} days")
    print("=" * 60)

    # Export results
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(mode="json"), f, indent=2)
    logger.info("Saved backtest metrics to %s", args.output_json)

    if result.trades:
        trades_df = pd.DataFrame([t.model_dump() for t in result.trades])
        trades_df.to_csv(args.output_trades_csv, index=False)
        logger.info("Saved %d trades to %s", len(result.trades), args.output_trades_csv)


if __name__ == "__main__":
    main()
