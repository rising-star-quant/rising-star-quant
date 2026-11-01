"""
Rising Star Trend Engine - Main Headless Orchestration Pipeline (Sprint 5: Backtesting, Automation & Portfolio)
Executes end-to-end institutional scanning:
1. Full S&P 500 / Watchlist Universe Management & Batch Ingestion
2. S&P 500 RuleEngine evaluation (100% formal criteria)
3. IndicatorEngine (250 daily bars, MA50 slope, volume surge, 20d/52w breakouts)
4. ScoringEngine (40/30/20/10 multi-factor weighting, BUY ALERT, Backtest Gatekeeper)
5. Enhanced RiskGuard (14d ATR stops, 1R/2R/3R/5R profit targets, volatility position sizing)
6. Automated NotificationHub (Actionable Buy Alert cards and Nightly Daily Summary Digest)
7. Paper Trading & PortfolioTracker (Automated position opening on Buy Alerts & RiskGuard audits)
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.dataconnector import DataConnector, MarketData
from core.ruleengine import (
    CompanyProfile,
    EligibilityResult,
    RuleEngine,
    build_profile_from_market_data,
    compute_annual_dollar_volume,
)
from core.indicatorengine import IndicatorEngine, IndicatorMetrics
from core.scoringengine import HistoricalSignal, ScorePayload, ScoringEngine
from core.riskguard import PositionState, RiskGuard, RiskPlan, RiskStatusPayload
from core.notificationhub import NotificationHub
from core.universe import BatchMarketScanner, fetch_sp500_tickers, FALLBACK_SP500_TICKERS
from core.portfoliotracker import PortfolioTracker, PaperPosition

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("RisingStarEngine")


def load_watchlist(filepath: str = "watchlist.csv") -> List[str]:
    """Reads ticker symbols from CSV file or falls back to defaults."""
    tickers: List[str] = []
    if os.path.exists(filepath):
        try:
            with open(filepath, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sym = row.get("ticker", "").strip().upper()
                    if sym:
                        tickers.append(sym)
            if tickers:
                logger.info("Loaded %d tickers from '%s'", len(tickers), filepath)
                return tickers
        except Exception as exc:
            logger.warning("Could not parse watchlist file: %s", exc)

    defaults = list(FALLBACK_SP500_TICKERS[:15])
    logger.info("Using default watchlist (%d tickers)", len(defaults))
    return defaults


def run_pipeline(
    use_sp500: bool = False,
    watchlist_file: str = "watchlist.csv",
    ticker_limit: Optional[int] = None,
    min_score_alert: float = 85.0,
    account_equity: float = 100_000.0,
    risk_per_trade_pct: float = 1.0,
    batch_size: int = 25,
    send_telegram: bool = True,
    enable_paper_trading: bool = True,
    portfolio_file: str = "portfolio.json",
    output_json: str = "scan_results.json",
    output_csv: str = "scan_results.csv",
) -> List[Dict[str, Any]]:
    """
    Executes resilient headless batch scan across S&P 500 or custom watchlist with RiskGuard and PortfolioTracker.
    """
    start_ts = time.time()
    logger.info("======================================================================")
    logger.info("  RISING STAR TREND ENGINE - HEADLESS INSTITUTIONAL SCANNER (SPRINT 5)")
    logger.info("======================================================================")

    # 1. Resolve Target Universe
    if use_sp500:
        logger.info("Mode: Full S&P 500 Index Universe")
        tickers = fetch_sp500_tickers()
    else:
        logger.info("Mode: Custom Watchlist ('%s')", watchlist_file)
        tickers = load_watchlist(watchlist_file)

    if ticker_limit and ticker_limit > 0:
        tickers = tickers[:ticker_limit]
        logger.info("Universe capped to first %d tickers by limit flag", len(tickers))

    logger.info("Total assets queued for analysis: %d", len(tickers))

    # Initialize micro-modules
    connector = DataConnector()
    indicator_engine = IndicatorEngine()
    scoring_engine = ScoringEngine()
    risk_guard = RiskGuard()
    notification_hub = NotificationHub()
    batch_scanner = BatchMarketScanner(batch_size=batch_size, delay_between_batches=1.0)
    
    portfolio_tracker: Optional[PortfolioTracker] = None
    if enable_paper_trading:
        portfolio_tracker = PortfolioTracker(
            initial_cash=account_equity,
            storage_file=portfolio_file,
        )

    print("\n" + "=" * 115)
    print(
        f"{'TICKER':<8} {'PRICE':<8} {'RESIST':<9} {'VOL_RAT':<8} {'SCORE':<7} "
        f"{'TIER':<20} {'BUY_ALERT':<11} {'ATR14':<8} {'STOP':<8} {'SIZING'}"
    )
    print("=" * 115)

    buy_alerts: List[Dict[str, Any]] = []
    qualified_count = 0
    latest_quotes: Dict[str, Dict[str, Any]] = {}

    def process_ticker(ticker: str) -> Optional[Dict[str, Any]]:
        nonlocal qualified_count

        # 1. Ingest Market Data
        data: MarketData = connector.fetch_market_data(ticker)

        # 2. RuleEngine S&P 500 Eligibility Verification
        profile = build_profile_from_market_data(data)
        rule_res: EligibilityResult = RuleEngine.evaluate(profile)

        if rule_res.is_eligible:
            qualified_count += 1

        # 3. IndicatorEngine 250-bar calculations
        indicators: IndicatorMetrics = indicator_engine.calculate(
            ticker=ticker,
            close_prices=data.close_prices,
            high_prices=data.high_prices,
            low_prices=data.low_prices,
            volumes=data.volumes,
        )

        # Store latest quote for portfolio tracking & audit
        latest_quotes[ticker] = {
            "current_price": indicators.latest_close,
            "close": indicators.latest_close,
            "high": indicators.high_52w,
            "low": indicators.latest_close * 0.98,
            "volume": indicators.volume_metrics.avg_volume_50d,
            "ma50": indicators.technical_trend.ma50,
            "avg_volume_50d": indicators.volume_metrics.avg_volume_50d,
        }

        # 4. ScoringEngine Multi-Factor Evaluation & Gatekeeper
        score_payload = scoring_engine.calculate_score(
            indicators=indicators,
            rule_result=rule_res,
            short_interest_pct=data.short_interest_pct,
        )

        # 5. Enhanced Risk Guard & Volatility Position Sizing
        risk_plan: Optional[RiskPlan] = None
        if score_payload.tier in ["STRONG_RISING_STAR", "EMERGING_CANDIDATE"] or score_payload.is_buy_alert:
            risk_plan = risk_guard.compute_position_sizing(
                ticker=ticker,
                entry_price=indicators.latest_close,
                highs=data.high_prices,
                lows=data.low_prices,
                closes=data.close_prices,
                account_equity=account_equity,
                risk_per_trade_pct=risk_per_trade_pct,
            )

        buy_str = "🔥 YES" if score_payload.is_buy_alert else "NO"
        atr_str = f"${risk_plan.atr_14:.2f}" if risk_plan else "-"
        stop_str = f"${risk_plan.stop_loss_price:.2f}" if risk_plan else "-"
        shares_str = f"{risk_plan.suggested_shares} shs" if risk_plan else "-"

        print(
            f"{ticker:<8} "
            f"${indicators.latest_close:<8.2f} "
            f"${indicators.resistance_20d:<9.2f} "
            f"{indicators.volume_metrics.up_down_volume_ratio:<7.2f}x "
            f"{score_payload.rising_star_score:<6.1f} "
            f"{score_payload.tier:<20} "
            f"{buy_str:<11} "
            f"{atr_str:<8} "
            f"{stop_str:<8} "
            f"{shares_str}"
        )

        record = {
            "ticker": ticker,
            "status": "QUALIFIED" if rule_res.is_eligible else "DISQUALIFIED",
            "score": score_payload.rising_star_score,
            "tier": score_payload.tier,
            "is_buy_alert": score_payload.is_buy_alert,
            "breakout_triggered": indicators.breakout_triggered,
            "breakout_type": indicators.breakout_type,
            "latest_close": indicators.latest_close,
            "resistance_20d": indicators.resistance_20d,
            "high_52w": indicators.high_52w,
            "distance_to_resistance_pct": indicators.distance_to_resistance_pct,
            "ma50": indicators.technical_trend.ma50,
            "ma50_slope_20d": indicators.technical_trend.ma50_slope_20d,
            "up_down_volume_ratio": indicators.volume_metrics.up_down_volume_ratio,
            "institutional_accumulation": indicators.volume_metrics.institutional_accumulation,
            "relative_sector_strength": indicators.relative_sector_strength,
            "gatekeeper_approved": score_payload.gatekeeper.gatekeeper_approved,
            "profit_factor": score_payload.gatekeeper.profit_factor,
            "win_rate": score_payload.gatekeeper.win_rate,
            "atr_14": risk_plan.atr_14 if risk_plan else None,
            "stop_loss_price": risk_plan.stop_loss_price if risk_plan else None,
            "risk_pct": risk_plan.risk_pct if risk_plan else None,
            "target_1r": risk_plan.target_1r if risk_plan else None,
            "target_2r": risk_plan.target_2r if risk_plan else None,
            "target_3r": risk_plan.target_3r if risk_plan else None,
            "target_5r": risk_plan.target_5r if risk_plan else None,
            "suggested_shares": risk_plan.suggested_shares if risk_plan else None,
            "max_loss_usd": risk_plan.max_loss_usd if risk_plan else None,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # 6. Telegram Alert Dispatching on Confirmed BUY ALERT
        if send_telegram and score_payload.is_buy_alert:
            buy_alerts.append(record)
            notification_hub.send_buy_alert(
                ticker=ticker,
                score=score_payload,
                indicators=indicators,
                risk=risk_plan,
            )

        # 7. Paper Trading Execution
        if portfolio_tracker and score_payload.is_buy_alert and risk_plan:
            # Check if position already open for ticker
            already_open = any(
                p.ticker == ticker and p.status == "OPEN" for p in portfolio_tracker.positions.values()
            )
            if not already_open and risk_plan.suggested_shares > 0:
                portfolio_tracker.open_position(
                    ticker=ticker,
                    entry_price=indicators.latest_close,
                    shares=risk_plan.suggested_shares,
                    risk_plan=risk_plan,
                )

        return record

    # Execute resilient batch market scan
    results, stats = batch_scanner.process_universe(
        tickers=tickers,
        processor_fn=process_ticker,
    )

    print("=" * 115 + "\n")

    # Sort results descending by score
    results.sort(key=lambda x: x.get("score", 0), reverse=True)

    elapsed_total = round(time.time() - start_ts, 2)

    # 8. Audit Active Paper Portfolio
    if portfolio_tracker:
        logger.info("Auditing active paper portfolio positions against latest quotes...")
        audit_events = portfolio_tracker.audit_positions(latest_quotes)
        summary = portfolio_tracker.get_summary()
        print("\n" + "=" * 80)
        print("          SIMULATED PAPER TRADING PORTFOLIO SUMMARY          ")
        print("=" * 80)
        print(f"Total Account Value:  ${summary.total_account_value:,.2f}")
        print(f"Cash Available:       ${summary.cash:,.2f}")
        print(f"Invested Capital:     ${summary.invested_capital:,.2f}")
        print(f"Unrealized P&L:       ${summary.total_unrealized_pnl_dollars:+,.2f}")
        print(f"Realized P&L:         ${summary.total_realized_pnl_dollars:+,.2f}")
        print(f"Open Positions:       {summary.open_positions_count}")
        print(f"Closed Positions:     {summary.closed_positions_count} (Win Rate: {summary.win_rate_pct:.1f}%)")
        print("=" * 80 + "\n")

    # 9. Telegram End-of-Run Daily Summary Digest
    if send_telegram and results:
        top_cands = results[:10]
        notification_hub.send_daily_digest(
            total_scanned=len(tickers),
            qualified_count=qualified_count,
            buy_alerts_count=len(buy_alerts),
            top_candidates=top_cands,
            elapsed_seconds=elapsed_total,
        )

    # 10. Export scan results
    try:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump({
                "meta": {
                    "scan_time": datetime.utcnow().isoformat(),
                    "total_scanned": len(tickers),
                    "successful": len(results),
                    "qualified_count": qualified_count,
                    "buy_alerts_count": len(buy_alerts),
                    "elapsed_seconds": elapsed_total,
                },
                "results": results,
            }, f, indent=2)
        logger.info("Saved scan results to '%s'", output_json)

        if results:
            keys = list(results[0].keys())
            with open(output_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
                writer.writeheader()
                for r in results:
                    writer.writerow(r)
            logger.info("Saved scan CSV to '%s'", output_csv)
    except Exception as io_err:
        logger.warning("Could not write output files: %s", io_err)

    logger.info(
        "Scan completed in %.1fs. Analyzed %d tickers, %d qualified, %d BUY ALERTS.",
        elapsed_total,
        len(tickers),
        qualified_count,
        len(buy_alerts),
    )
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Headless Rising Star Trend Engine Runner (Sprint 5: Backtesting, Automation & Portfolio)",
    )
    parser.add_argument("--sp500", action="store_true", help="Scan the complete S&P 500 index constituent universe")
    parser.add_argument("--watchlist", default="watchlist.csv", help="Path to custom watchlist CSV")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tickers to analyze")
    parser.add_argument("--min-score", type=float, default=85.0, help="Minimum score for BUY ALERT (default 85.0)")
    parser.add_argument("--equity", type=float, default=100_000.0, help="Portfolio equity for position sizing (default $100,000)")
    parser.add_argument("--risk-pct", type=float, default=1.0, help="Risk percentage per trade (default 1.0%)")
    parser.add_argument("--batch-size", type=int, default=25, help="Batch size for market scanning (default 25)")
    parser.add_argument("--no-telegram", action="store_true", help="Disable Telegram alerts")
    parser.add_argument("--no-paper", action="store_true", help="Disable paper portfolio tracking")
    parser.add_argument("--portfolio-file", default="portfolio.json", help="Path to portfolio JSON file")
    args = parser.parse_args()

    run_pipeline(
        use_sp500=args.sp500,
        watchlist_file=args.watchlist,
        ticker_limit=args.limit,
        min_score_alert=args.min_score,
        account_equity=args.equity,
        risk_per_trade_pct=args.risk_pct,
        batch_size=args.batch_size,
        send_telegram=not args.no_telegram,
        enable_paper_trading=not args.no_paper,
        portfolio_file=args.portfolio_file,
    )


if __name__ == "__main__":
    main()
