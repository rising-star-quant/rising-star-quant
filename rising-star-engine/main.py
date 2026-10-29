"""
Rising Star Trend Engine - Main Orchestration Pipeline
Executes the end-to-end trend discovery scan, applying S&P baseline rules, technical indicators,
scoring models, dynamic risk guards, and Telegram dispatching.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List

from core.dataconnector import DataConnector, MarketData
from core.ruleengine import RuleEngine
from core.indicatorengine import IndicatorEngine
from core.scoringengine import ScoringEngine
from core.riskguard import RiskGuard
from core.notificationhub import NotificationHub

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
            logger.info("Loaded %d tickers from '%s'", len(tickers), filepath)
            return tickers
        except Exception as exc:
            logger.warning("Could not parse watchlist file: %s", exc)

    # Fallback default high-momentum candidates
    defaults = ["NVDA", "PLTR", "ARM", "SMCI", "MSTR", "TSLA", "AMD", "APP"]
    logger.info("Using default watchlist (%d tickers)", len(defaults))
    return defaults


def run_pipeline(
    watchlist_file: str = "watchlist.csv",
    min_score_alert: int = 75,
    send_telegram: bool = True,
    output_json: str = "scan_results.json",
    output_csv: str = "scan_results.csv",
) -> List[Dict[str, Any]]:
    """Runs the full scan pipeline across all tickers."""
    start_time = datetime.utcnow()
    logger.info("==================================================================")
    logger.info("🚀 STARTING RISING STAR TREND ENGINE (UTC: %s)", start_time.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("==================================================================")

    # 1. Initialize Micro-Modules
    connector = DataConnector(max_retries=3, backoff_factor=1.5, lookback_days=120)
    rule_engine = RuleEngine()
    indicator_engine = IndicatorEngine()
    scoring_engine = ScoringEngine()
    risk_guard = RiskGuard(max_stop_loss_pct=7.5, portfolio_risk_budget=1000.0)
    notification_hub = NotificationHub()

    tickers = load_watchlist(watchlist_file)
    results: List[Dict[str, Any]] = []
    alerted_tickers: List[str] = []

    print("\n" + "=" * 90)
    print(f"{'TICKER':<8} {'PRICE':<9} {'20D HIGH':<10} {'SURGE':<8} {'SCORE':<7} {'TIER':<20} {'STOP':<9} {'TARGET (2R)'}")
    print("=" * 90)

    for ticker in tickers:
        logger.debug("Processing ticker %s...", ticker)
        data = connector.fetch_ticker_data(ticker)
        if data is None:
            logger.warning("Skipping %s due to unavailable market data", ticker)
            continue

        # 2. RuleEngine Evaluation
        rule_res = rule_engine.evaluate(data)
        if not rule_res.is_eligible:
            logger.info("Ticker %s failed S&P baseline rules: %s", ticker, ", ".join(rule_res.failed_rules))
            # Track as disqualified
            results.append({
                "ticker": ticker,
                "status": "DISQUALIFIED",
                "latest_close": data.latest_close,
                "failed_rules": rule_res.failed_rules,
                "score": 0,
            })
            continue

        # 3. IndicatorEngine Calculations
        indicators = indicator_engine.calculate(data)

        # 4. ScoringEngine Multi-Factor Evaluation
        score = scoring_engine.calculate_score(data, indicators)

        # 5. RiskGuard Calculation
        risk_plan = risk_guard.create_risk_plan(indicators)

        # Output to console
        print(
            f"{ticker:<8} "
            f"${indicators.latest_close:<8.2f} "
            f"${indicators.high_20d:<9.2f} "
            f"{indicators.volume_surge_10d:<7.1f}x "
            f"{score.total_score:<6} "
            f"{score.tier:<20} "
            f"${risk_plan.stop_loss:<8.2f} "
            f"${risk_plan.target_2r:.2f}"
        )

        record = {
            "ticker": ticker,
            "status": "QUALIFIED",
            "score": score.total_score,
            "tier": score.tier,
            "latest_close": indicators.latest_close,
            "high_20d": indicators.high_20d,
            "distance_to_20d_high_pct": indicators.distance_to_20d_high_pct,
            "is_20d_high_breakout": indicators.is_20d_high_breakout,
            "volume_surge_10d": indicators.volume_surge_10d,
            "ma50": indicators.ma50,
            "stop_loss": risk_plan.stop_loss,
            "risk_pct": risk_plan.risk_pct,
            "target_2r": risk_plan.target_2r,
            "target_3r": risk_plan.target_3r,
            "suggested_shares": risk_plan.suggested_shares_1k_risk,
            "market_cap": data.market_cap,
            "public_float": data.public_float,
            "short_interest_pct": data.short_interest_pct,
            "timestamp": data.timestamp.isoformat(),
        }
        results.append(record)

        # 6. Telegram Alert Dispatching
        if send_telegram and score.total_score >= min_score_alert:
            logger.info("Dispatching Telegram alert for top candidate %s (Score: %d)...", ticker, score.total_score)
            sent = notification_hub.send_alert(score, indicators, risk_plan)
            if sent:
                alerted_tickers.append(ticker)

    print("=" * 90 + "\n")

    # Sort results by score descending
    results.sort(key=lambda x: x.get("score", 0), reverse=True)

    # 7. Export Results
    try:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        logger.info("Saved scan results to '%s'", output_json)

        # Export CSV
        if results:
            keys = [k for k in results[0].keys() if k != "failed_rules"]
            with open(output_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
                writer.writeheader()
                for r in results:
                    writer.writerow(r)
            logger.info("Saved scan CSV to '%s'", output_csv)
    except Exception as io_err:
        logger.warning("Could not write output files: %s", io_err)

    # 8. Send Daily Summary
    if send_telegram and notification_hub.is_configured:
        qualified = [r for r in results if r.get("status") == "QUALIFIED"]
        top_picks = [r["ticker"] for r in qualified[:3]]
        notification_hub.send_daily_summary(
            total_scanned=len(tickers),
            qualified_count=len(qualified),
            top_tickers=top_picks,
        )

    logger.info("Scan completed successfully. Total processed: %d.", len(tickers))
    return results


def main():
    parser = argparse.ArgumentParser(description="Rising Star Trend Engine Runner")
    parser.add_argument("--watchlist", default="watchlist.csv", help="Path to watchlist CSV")
    parser.add_argument("--min-score", type=int, default=75, help="Minimum score to trigger Telegram alert")
    parser.add_argument("--no-telegram", action="store_true", help="Disable Telegram alerts")
    args = parser.parse_args()

    run_pipeline(
        watchlist_file=args.watchlist,
        min_score_alert=args.min_score,
        send_telegram=not args.no_telegram,
    )


if __name__ == "__main__":
    main()
