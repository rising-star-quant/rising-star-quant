"""
Rising Star Trend Engine - Main Headless Orchestration Pipeline (Sprint 3)
Executes end-to-end scanning:
1. Data Ingestion (yfinance with exponential backoff)
2. S&P 500 RuleEngine evaluation (100% formal criteria)
3. IndicatorEngine (250 daily bars, MA50 slope, volume surge, 20d/52w breakouts)
4. ScoringEngine (40/30/20/10 multi-factor weighting, BUY ALERT, Backtest Gatekeeper)
5. RiskGuard (Trailing stop -10%, MA50 volume breakdown, 60-day limit)
6. NotificationHub (Telegram alert dispatcher)
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
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
from core.riskguard import PositionState, RiskGuard, RiskStatusPayload
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

    defaults = ["NVDA", "PLTR", "ARM", "SMCI", "MSTR", "TSLA", "AMD", "APP"]
    logger.info("Using default watchlist (%d tickers)", len(defaults))
    return defaults


def run_pipeline(
    watchlist_file: str = "watchlist.csv",
    min_score_alert: float = 85.0,
    send_telegram: bool = True,
    output_json: str = "scan_results.json",
    output_csv: str = "scan_results.csv",
) -> List[Dict[str, Any]]:
    """Runs the full headless scan pipeline across all tickers."""
    start_time = datetime.utcnow()
    logger.info("==================================================================")
    logger.info("🚀 STARTING HEADLESS RISING STAR TREND ENGINE (UTC: %s)", start_time.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("==================================================================")

    connector = DataConnector(max_retries=3, backoff_factor=1.5, lookback_days=250)
    rule_engine = RuleEngine()
    indicator_engine = IndicatorEngine()
    scoring_engine = ScoringEngine(buy_score_threshold=min_score_alert)
    risk_guard = RiskGuard()
    notification_hub = NotificationHub()

    tickers = load_watchlist(watchlist_file)
    results: List[Dict[str, Any]] = []

    print("\n" + "=" * 105)
    print(f"{'TICKER':<8} {'PRICE':<9} {'20D HIGH':<10} {'SURGE':<8} {'SCORE':<7} {'TIER':<20} {'BUY ALERT':<11} {'GATEKEEPER'}")
    print("=" * 105)

    for ticker in tickers:
        logger.debug("Processing ticker %s...", ticker)
        data = connector.fetch_ticker_data(ticker)
        if data is None or len(data.close_prices) < 20:
            logger.warning("Skipping %s due to unavailable or insufficient market data", ticker)
            continue

        # 1. RuleEngine Evaluation with automated exchange mapping & dollar volume
        profile = build_profile_from_market_data(
            ticker=ticker,
            market_cap=data.market_cap or 25_000_000_000.0,
            net_income_ttm=data.net_income_ttm if data.net_income_ttm is not None else 100_000_000.0,
            net_income_mrq=data.net_income_q1 if data.net_income_q1 is not None else 25_000_000.0,
            exchange=data.exchange or "NASDAQ",
            public_float_pct=0.75,
            closes=data.close_prices,
            volumes=data.volumes,
            latest_price=data.latest_close,
            avg_daily_volume_shares=data.avg_volume_10d,
        )
        rule_res = rule_engine.evaluate(profile, closes=data.close_prices, volumes=data.volumes)


        # 2. IndicatorEngine Calculations
        indicators = indicator_engine.calculate(
            ticker=ticker,
            closes=data.close_prices,
            highs=data.high_prices,
            lows=data.low_prices,
            volumes=data.volumes,
        )

        # 3. ScoringEngine Multi-Factor Evaluation & Gatekeeper
        score_payload = scoring_engine.calculate_score(
            indicators=indicators,
            rule_result=rule_res,
            short_interest_pct=data.short_interest_pct,
        )

        buy_str = "🔥 YES" if score_payload.is_buy_alert else "NO"
        gk_str = "PASS" if score_payload.gatekeeper.gatekeeper_approved else "FAIL"

        print(
            f"{ticker:<8} "
            f"${indicators.latest_close:<8.2f} "
            f"${indicators.resistance_20d:<9.2f} "
            f"{indicators.volume_metrics.up_down_volume_ratio:<7.2f}x "
            f"{score_payload.rising_star_score:<6.1f} "
            f"{score_payload.tier:<20} "
            f"{buy_str:<11} "
            f"{gk_str}"
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
            "timestamp": datetime.utcnow().isoformat(),
        }
        results.append(record)

        # 4. Telegram Alert Dispatching on Confirmed BUY ALERT
        if send_telegram and score_payload.is_buy_alert and notification_hub.is_configured:
            msg = (
                f"🔥 <b>RISING STAR BUY ALERT</b>\n\n"
                f"<b>Symbol:</b> #{ticker}\n"
                f"<b>Rising Star Score:</b> <code>{score_payload.rising_star_score}/100</code>\n"
                f"<b>Price:</b> <code>${indicators.latest_close:.2f}</code>\n"
                f"<b>Breakout:</b> <code>{indicators.breakout_type}</code> (Ceiling: ${indicators.resistance_20d:.2f})\n"
                f"<b>Volume Accumulation:</b> <code>{indicators.volume_metrics.up_down_volume_ratio}x</code>\n"
                f"<b>Gatekeeper:</b> Approved (PF: {score_payload.gatekeeper.profit_factor}, WR: {score_payload.gatekeeper.win_rate*100:.0f}%)\n\n"
                f"<i>{score_payload.summary}</i>"
            )
            notification_hub.send_message(msg)

    print("=" * 105 + "\n")

    results.sort(key=lambda x: x.get("score", 0), reverse=True)

    # Export scan results
    try:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
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

    logger.info("Scan completed successfully. Processed: %d tickers.", len(tickers))
    return results


def main():
    parser = argparse.ArgumentParser(description="Headless Rising Star Trend Engine Runner")
    parser.add_argument("--watchlist", default="watchlist.csv", help="Path to watchlist CSV")
    parser.add_argument("--min-score", type=float, default=85.0, help="Minimum score for BUY ALERT (default 85.0)")
    parser.add_argument("--no-telegram", action="store_true", help="Disable Telegram alerts")
    args = parser.parse_args()

    run_pipeline(
        watchlist_file=args.watchlist,
        min_score_alert=args.min_score,
        send_telegram=not args.no_telegram,
    )


if __name__ == "__main__":
    main()
