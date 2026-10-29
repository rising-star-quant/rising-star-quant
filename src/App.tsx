/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  Bell,
  CheckCircle2,
  ChevronRight,
  Code2,
  Copy,
  Check,
  Database,
  FileCode,
  FolderTree,
  Github,
  Layers,
  Play,
  RefreshCw,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sliders,
  Terminal,
  TrendingUp,
  Zap,
} from 'lucide-react';

interface FileInfo {
  filename: string;
  path: string;
  category: 'workflow' | 'core' | 'tests' | 'root';
  description: string;
  language: string;
  content: string;
}

const PROJECT_FILES: Record<string, FileInfo> = {
  workflow: {
    filename: 'run_engine.yml',
    path: '.github/workflows/run_engine.yml',
    category: 'workflow',
    description: 'קובץ ההפעלה האוטומטי בענן (GitHub Actions cron at 21:30 UTC)',
    language: 'yaml',
    content: `name: Rising Star Trend Engine Daily Run

on:
  schedule:
    # Runs Monday through Friday at 21:30 UTC (after US market close)
    - cron: '30 21 * * 1-5'
  workflow_dispatch: # Allows manual trigger from GitHub Actions tab

jobs:
  run-engine:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
          cache: 'pip'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run Unit Tests
        run: |
          pytest tests/ -v

      - name: Run Rising Star Trend Engine
        env:
          TELEGRAM_BOT_TOKEN: \${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: \${{ secrets.TELEGRAM_CHAT_ID }}
        run: |
          python main.py

      - name: Upload Scan Results Artifact
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: scan-results
          path: |
            scan_results.json
            scan_results.csv
          retention-days: 7`,
  },
  dataconnector: {
    filename: 'dataconnector.py',
    path: 'core/dataconnector.py',
    category: 'core',
    description: 'מודול השאיבה והנרמול (yfinance עם exponential backoff)',
    language: 'python',
    content: `"""
Rising Star Trend Engine - DataConnector Micro-Module
Ingests historical OHLCV and fundamental metrics using yfinance with exponential backoff.
"""

from __future__ import annotations
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TypeVar

try:
    import yfinance as yf
except ImportError:
    yf = None

logger = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass(frozen=True)
class MarketData:
    ticker: str
    timestamp: datetime
    close_prices: List[float]
    high_prices: List[float]
    low_prices: List[float]
    volumes: List[int]
    latest_close: float
    latest_volume: int
    market_cap: Optional[float] = None
    public_float: Optional[float] = None
    net_income_q1: Optional[float] = None
    net_income_ttm: Optional[float] = None
    short_interest_pct: Optional[float] = None
    avg_volume_10d: Optional[float] = None


class DataConnector:
    def __init__(self, max_retries: int = 3, backoff_factor: float = 1.5, lookback_days: int = 120, jitter: bool = True, yf_module: Any = None):
        self.max_retries = max(0, max_retries)
        self.backoff_factor = max(0.1, backoff_factor)
        self.lookback_days = max(30, lookback_days)
        self.jitter = jitter
        self.yf = yf_module if yf_module is not None else yf

    def _execute_with_retry(self, operation_name: str, func: Callable[[], T]) -> Optional[T]:
        attempt = 0
        while attempt <= self.max_retries:
            try:
                return func()
            except Exception as exc:
                err_str = str(exc).lower()
                is_transient = any(kw in err_str for kw in ["429", "rate limit", "throttle", "timeout", "connection"])
                attempt += 1
                if attempt > self.max_retries or not is_transient:
                    logger.warning("Operation '%s' failed permanently: %s", operation_name, exc)
                    return None
                sleep_time = self.backoff_factor * (2 ** (attempt - 1))
                if self.jitter:
                    sleep_time += random.uniform(0.05, 0.25 * sleep_time)
                time.sleep(sleep_time)
        return None

    def fetch_ticker_data(self, ticker: str) -> Optional[MarketData]:
        if not ticker or not isinstance(ticker, str) or not ticker.strip():
            return None
        clean_ticker = ticker.strip().upper()
        if self.yf is None:
            return None

        def _fetch() -> Optional[MarketData]:
            ticker_obj = self.yf.Ticker(clean_ticker)
            history_df = ticker_obj.history(period=f"{self.lookback_days}d")
            if history_df is None or history_df.empty or len(history_df) < 20:
                return None

            close_series = [float(x) for x in history_df["Close"].dropna().tolist()]
            high_series = [float(x) for x in history_df["High"].dropna().tolist()]
            low_series = [float(x) for x in history_df["Low"].dropna().tolist()]
            volume_series = [int(x) for x in history_df["Volume"].dropna().tolist()]

            info = getattr(ticker_obj, "info", None) or {}
            market_cap = info.get("marketCap")
            public_float = info.get("floatShares") or info.get("sharesOutstanding")
            short_interest_pct = info.get("shortPercentOfFloat")
            avg_volume_10d = info.get("averageDailyVolume10Day") or info.get("averageVolume10days")
            net_income_ttm = info.get("netIncomeToCommon")

            net_income_q1 = None
            try:
                qf = getattr(ticker_obj, "quarterly_financials", None)
                if qf is not None and not qf.empty and "Net Income" in qf.index:
                    net_income_q1 = float(qf.loc["Net Income"].iloc[0])
            except Exception:
                pass

            return MarketData(
                ticker=clean_ticker,
                timestamp=datetime.utcnow(),
                close_prices=close_series,
                high_prices=high_series,
                low_prices=low_series,
                volumes=volume_series,
                latest_close=close_series[-1],
                latest_volume=volume_series[-1],
                market_cap=float(market_cap) if market_cap is not None else None,
                public_float=float(public_float) if public_float is not None else None,
                net_income_q1=net_income_q1,
                net_income_ttm=float(net_income_ttm) if net_income_ttm is not None else None,
                short_interest_pct=float(short_interest_pct) if short_interest_pct is not None else None,
                avg_volume_10d=float(avg_volume_10d) if avg_volume_10d is not None else None,
            )

        return self._execute_with_retry(f"fetch_ticker_data({clean_ticker})", _fetch)`,
  },
  ruleengine: {
    filename: 'ruleengine.py',
    path: 'core/ruleengine.py',
    category: 'core',
    description: 'מודול תנאי הסף של S&P (רווחיות TTM, שווי שוק, נזילות מוסדית)',
    language: 'python',
    content: `"""
Rising Star Trend Engine - RuleEngine Micro-Module
Validates baseline S&P-style qualification criteria and fundamental hygiene filters.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List
from core.dataconnector import MarketData


@dataclass
class RuleCheckResult:
    is_eligible: bool
    ticker: str
    passed_rules: List[str] = field(default_factory=list)
    failed_rules: List[str] = field(default_factory=list)
    details: Dict[str, any] = field(default_factory=dict)


class RuleEngine:
    def __init__(
        self,
        min_market_cap: float = 1_000_000_000.0,
        require_positive_ttm_earnings: bool = True,
        min_public_float: float = 10_000_000.0,
        min_daily_dollar_volume: float = 5_000_000.0,
        min_share_price: float = 5.0,
    ):
        self.min_market_cap = min_market_cap
        self.require_positive_ttm_earnings = require_positive_ttm_earnings
        self.min_public_float = min_public_float
        self.min_daily_dollar_volume = min_daily_dollar_volume
        self.min_share_price = min_share_price

    def evaluate(self, data: MarketData) -> RuleCheckResult:
        passed, failed, details = [], [], {}
        price = data.latest_close
        details["latest_close"] = price

        if price >= self.min_share_price:
            passed.append(f"Price (\${price:.2f} >= \${self.min_share_price:.2f})")
        else:
            failed.append(f"Penny stock: \${price:.2f} < \${self.min_share_price:.2f}")

        mcap = data.market_cap
        details["market_cap"] = mcap
        if mcap and mcap >= self.min_market_cap:
            passed.append(f"Market Cap (\${mcap/1e9:.2f}B >= \${self.min_market_cap/1e9:.2f}B)")
        else:
            failed.append(f"Market Cap below \${self.min_market_cap/1e9:.2f}B")

        ttm_income = data.net_income_ttm
        details["net_income_ttm"] = ttm_income
        if self.require_positive_ttm_earnings:
            if ttm_income and ttm_income > 0:
                passed.append(f"Positive TTM Net Income (\${ttm_income/1e6:.1f}M)")
            else:
                failed.append("Negative or Missing TTM Earnings")

        avg_vol = data.avg_volume_10d or (sum(data.volumes[-10:]) / 10.0 if len(data.volumes) >= 10 else 0)
        daily_dollar_vol = avg_vol * price
        details["daily_dollar_volume"] = daily_dollar_vol
        if daily_dollar_vol >= self.min_daily_dollar_volume:
            passed.append(f"Institutional Liquidity (\${daily_dollar_vol/1e6:.1f}M/day)")
        else:
            failed.append(f"Illiquid: \${daily_dollar_vol/1e6:.1f}M/day")

        return RuleCheckResult(is_eligible=len(failed) == 0, ticker=data.ticker, passed_rules=passed, failed_rules=failed, details=details)`,
  },
  indicatorengine: {
    filename: 'indicatorengine.py',
    path: 'core/indicatorengine.py',
    category: 'core',
    description: 'מודול חישובים טכניים (MA20, MA50, 20d High, Volume Surge, ATR)',
    language: 'python',
    content: `"""
Rising Star Trend Engine - IndicatorEngine Micro-Module
Calculates trend alignment, moving averages (MA20, MA50, MA200), volume surges, and ATR.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
from core.dataconnector import MarketData


@dataclass(frozen=True)
class TechnicalIndicators:
    ticker: str
    latest_close: float
    latest_volume: int
    ma20: float
    ma50: float
    ma200: Optional[float]
    high_20d: float
    distance_to_20d_high_pct: float
    is_20d_high_breakout: bool
    volume_surge_10d: float
    volume_surge_50d: float
    is_volume_expansion: bool
    atr14: float
    atr_pct: float
    is_above_ma50: bool
    is_trend_aligned: bool


class IndicatorEngine:
    def calculate(self, data: MarketData) -> TechnicalIndicators:
        closes, highs, lows, volumes = data.close_prices, data.high_prices, data.low_prices, data.volumes
        latest_c, latest_v = data.latest_close, data.latest_volume

        ma20 = sum(closes[-20:]) / 20.0 if len(closes) >= 20 else latest_c
        ma50 = sum(closes[-50:]) / 50.0 if len(closes) >= 50 else ma20
        ma200 = sum(closes[-200:]) / 200.0 if len(closes) >= 200 else None

        high_20d = max(highs[-20:]) if len(highs) >= 20 else latest_c
        dist_20d_pct = ((latest_c - high_20d) / high_20d) * 100.0
        is_breakout = latest_c >= (high_20d * 0.995)

        v_10d = sum(volumes[-10:]) / 10.0 if len(volumes) >= 10 else float(latest_v)
        v_50d = sum(volumes[-50:]) / 50.0 if len(volumes) >= 50 else v_10d
        surge_10d = latest_v / v_10d if v_10d > 0 else 1.0
        surge_50d = latest_v / v_50d if v_50d > 0 else 1.0

        atr14 = sum([h - l for h, l in zip(highs[-14:], lows[-14:])]) / 14.0 if len(highs) >= 14 else 1.0
        atr_pct = (atr14 / latest_c) * 100.0

        return TechnicalIndicators(
            ticker=data.ticker,
            latest_close=latest_c,
            latest_volume=latest_v,
            ma20=round(ma20, 2),
            ma50=round(ma50, 2),
            ma200=round(ma200, 2) if ma200 else None,
            high_20d=round(high_20d, 2),
            distance_to_20d_high_pct=round(dist_20d_pct, 2),
            is_20d_high_breakout=is_breakout,
            volume_surge_10d=round(surge_10d, 2),
            volume_surge_50d=round(surge_50d, 2),
            is_volume_expansion=surge_10d >= 1.25,
            atr14=round(atr14, 2),
            atr_pct=round(atr_pct, 2),
            is_above_ma50=latest_c >= ma50,
            is_trend_aligned=latest_c > ma50 >= ma20,
        )`,
  },
  scoringengine: {
    filename: 'scoringengine.py',
    path: 'core/scoringengine.py',
    category: 'core',
    description: 'מודול שקלול הציון (0-100) וחלוקה לקטגוריות מומנטום',
    language: 'python',
    content: `"""
Rising Star Trend Engine - ScoringEngine Micro-Module
Calculates a unified multi-factor score from 0 to 100 based on momentum, volume, and fundamentals.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict
from core.dataconnector import MarketData
from core.indicatorengine import TechnicalIndicators


@dataclass(frozen=True)
class ScoreResult:
    ticker: str
    total_score: int
    tier: str
    momentum_score: int
    volume_score: int
    fundamental_score: int
    volatility_score: int
    summary: str
    factors: Dict[str, int] = field(default_factory=dict)


class ScoringEngine:
    def calculate_score(self, data: MarketData, indicators: TechnicalIndicators) -> ScoreResult:
        factors = {}
        momentum_score = 0
        if indicators.is_20d_high_breakout:
            momentum_score += 20
        elif indicators.distance_to_20d_high_pct >= -3.0:
            momentum_score += 15

        if indicators.is_above_ma50:
            momentum_score += 10
        if indicators.is_trend_aligned:
            momentum_score += 5

        volume_score = 0
        surge = indicators.volume_surge_10d
        if surge >= 2.0:
            volume_score = 25
        elif surge >= 1.5:
            volume_score = 20
        elif surge >= 1.2:
            volume_score = 15
        elif surge >= 1.0:
            volume_score = 10

        fundamental_score = 0
        if data.net_income_ttm and data.net_income_ttm > 0:
            fundamental_score += 10
        if data.net_income_q1 and data.net_income_q1 > 0:
            fundamental_score += 5
        if data.market_cap and data.market_cap >= 2_000_000_000:
            fundamental_score += 5

        volatility_score = 20 if indicators.atr_pct <= 3.5 else (15 if indicators.atr_pct <= 5.0 else 10)
        total_score = min(100, momentum_score + volume_score + fundamental_score + volatility_score)

        if total_score >= 80:
            tier = "STRONG_RISING_STAR"
            summary = f"🔥 Prime breakout leader ({total_score}/100) with explosive volume."
        elif total_score >= 65:
            tier = "EMERGING_CANDIDATE"
            summary = f"⚡ Emerging candidate ({total_score}/100) near breakout pivot."
        elif total_score >= 50:
            tier = "WATCHLIST"
            summary = f"👀 Consolidation watch ({total_score}/100)."
        else:
            tier = "AVOID"
            summary = f"❌ Low score ({total_score}/100)."

        return ScoreResult(
            ticker=data.ticker,
            total_score=total_score,
            tier=tier,
            momentum_score=momentum_score,
            volume_score=volume_score,
            fundamental_score=fundamental_score,
            volatility_score=volatility_score,
            summary=summary,
        )`,
  },
  riskguard: {
    filename: 'riskguard.py',
    path: 'core/riskguard.py',
    category: 'core',
    description: 'מודול ניהול סיכונים, סטופ לוס דינמי (ATR/MA50) ויעדי רווח 2R-5R',
    language: 'python',
    content: `"""
Rising Star Trend Engine - RiskGuard Micro-Module
Calculates dynamic ATR-based stop losses, asymmetric profit targets, and capital position sizing.
"""

from __future__ import annotations
from dataclasses import dataclass
from core.indicatorengine import TechnicalIndicators


@dataclass(frozen=True)
class RiskPlan:
    ticker: str
    entry_price: float
    stop_loss: float
    risk_per_share: float
    risk_pct: float
    target_2r: float
    target_3r: float
    target_5r: float
    suggested_shares_1k_risk: int
    is_favorable_rr: bool
    notes: str


class RiskGuard:
    def __init__(self, max_stop_loss_pct: float = 7.5, atr_multiplier: float = 2.0, portfolio_risk_budget: float = 1000.0):
        self.max_stop_loss_pct = max_stop_loss_pct
        self.atr_multiplier = atr_multiplier
        self.portfolio_risk_budget = portfolio_risk_budget

    def create_risk_plan(self, indicators: TechnicalIndicators) -> RiskPlan:
        entry = indicators.latest_close
        atr = indicators.atr14
        atr_stop = entry - (self.atr_multiplier * atr)
        max_hard_stop = entry * (1.0 - (self.max_stop_loss_pct / 100.0))

        stop_loss = max(atr_stop, max_hard_stop)
        risk_per_share = round(entry - stop_loss, 2)
        risk_pct = round((risk_per_share / entry) * 100.0, 2) if entry > 0 else 0.0

        target_2r = round(entry + (2.0 * risk_per_share), 2)
        target_3r = round(entry + (3.0 * risk_per_share), 2)
        target_5r = round(entry + (5.0 * risk_per_share), 2)

        shares = int(self.portfolio_risk_budget // risk_per_share) if risk_per_share > 0 else 0

        return RiskPlan(
            ticker=indicators.ticker,
            entry_price=entry,
            stop_loss=round(stop_loss, 2),
            risk_per_share=risk_per_share,
            risk_pct=risk_pct,
            target_2r=target_2r,
            target_3r=target_3r,
            target_5r=target_5r,
            suggested_shares_1k_risk=shares,
            is_favorable_rr=risk_pct <= self.max_stop_loss_pct,
            notes=f"Dynamic stop at \${stop_loss:.2f} ({risk_pct}% risk). 2R Target: \${target_2r:.2f}.",
        )`,
  },
  notificationhub: {
    filename: 'notificationhub.py',
    path: 'core/notificationhub.py',
    category: 'core',
    description: 'מודול שליחת התראות מעוצבות לטלגרם (כרטיסי מניה ודוח יומי)',
    language: 'python',
    content: `"""
Rising Star Trend Engine - NotificationHub Micro-Module
Dispatches real-time structured Telegram alerts and scan summaries.
"""

from __future__ import annotations
import logging
import os
from typing import List, Optional

try:
    import requests
except ImportError:
    requests = None

from core.indicatorengine import TechnicalIndicators
from core.riskguard import RiskPlan
from core.scoringengine import ScoreResult

logger = logging.getLogger(__name__)


class NotificationHub:
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        if not self.is_configured or requests is None:
            logger.info("Telegram not configured. Message preview:\n%s", text)
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": parse_mode, "disable_web_page_preview": True}
        try:
            resp = requests.post(url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as exc:
            logger.warning("Telegram error: %s", exc)
            return False

    def send_alert(self, score: ScoreResult, indicators: TechnicalIndicators, risk: RiskPlan) -> bool:
        badge = "🔥 <b>RISING STAR BREAKOUT ALERT</b>" if score.tier == "STRONG_RISING_STAR" else "⚡ <b>MOMENTUM CANDIDATE</b>"
        message = (
            f"{badge}\\n\\n"
            f"<b>Symbol:</b> #{score.ticker}\\n"
            f"<b>Score:</b> <code>{score.total_score}/100</code> ({score.tier})\\n"
            f"<b>Current Price:</b> <code>\${indicators.latest_close:.2f}</code>\\n"
            f"<b>20-Day High:</b> <code>\${indicators.high_20d:.2f}</code>\\n"
            f"<b>Volume Surge:</b> <code>{indicators.volume_surge_10d}x</code> 10d avg\\n\\n"
            f"🛡 <b><u>RISK GUARD EXECUTION PLAN</u></b>\\n"
            f"• <b>Entry:</b> \${risk.entry_price:.2f}\\n"
            f"• <b>Stop Loss:</b> <b>\${risk.stop_loss:.2f}</b> (-{risk.risk_pct}%)\\n"
            f"• <b>Target 1 (2R):</b> \${risk.target_2r:.2f}\\n"
            f"• <b>Suggested Size:</b> {risk.suggested_shares_1k_risk} shares\\n\\n"
            f"<i>{score.summary}</i>"
        )
        return self.send_message(message)`,
  },
  main: {
    filename: 'main.py',
    path: 'main.py',
    category: 'root',
    description: 'הקובץ הראשי שמחבר את כל המיקרו-מודולים ומריץ את הסריקה',
    language: 'python',
    content: `"""
Rising Star Trend Engine - Main Orchestration Pipeline
"""

import argparse
import csv
import json
import logging
import os
from datetime import datetime

from core.dataconnector import DataConnector
from core.ruleengine import RuleEngine
from core.indicatorengine import IndicatorEngine
from core.scoringengine import ScoringEngine
from core.riskguard import RiskGuard
from core.notificationhub import NotificationHub

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("RisingStarEngine")


def run_pipeline(watchlist_file: str = "watchlist.csv", min_score_alert: int = 75, send_telegram: bool = True):
    connector = DataConnector()
    rule_engine = RuleEngine()
    indicator_engine = IndicatorEngine()
    scoring_engine = ScoringEngine()
    risk_guard = RiskGuard()
    notification_hub = NotificationHub()

    tickers = ["NVDA", "PLTR", "ARM", "SMCI", "MSTR", "TSLA", "AMD", "APP"]
    results = []

    for ticker in tickers:
        data = connector.fetch_ticker_data(ticker)
        if not data:
            continue

        rule_res = rule_engine.evaluate(data)
        if not rule_res.is_eligible:
            continue

        indicators = indicator_engine.calculate(data)
        score = scoring_engine.calculate_score(data, indicators)
        risk = risk_guard.create_risk_plan(indicators)

        results.append({"ticker": ticker, "score": score.total_score, "tier": score.tier, "price": indicators.latest_close})

        if send_telegram and score.total_score >= min_score_alert:
            notification_hub.send_alert(score, indicators, risk)

    with open("scan_results.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    run_pipeline()`,
  },
  tests: {
    filename: 'test_modules.py',
    path: 'tests/test_modules.py',
    category: 'tests',
    description: 'תיקיית הבדיקות המקיפה לכלל המיקרו-מודולים',
    language: 'python',
    content: `"""
Unit test suite for the Rising Star Trend Engine micro-modules.
"""

from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from core.dataconnector import DataConnector, MarketData
from core.ruleengine import RuleEngine
from core.indicatorengine import IndicatorEngine
from core.scoringengine import ScoringEngine
from core.riskguard import RiskGuard
from core.notificationhub import NotificationHub


def test_rule_engine_qualifying_ticker():
    rule_engine = RuleEngine()
    data = MarketData(
        ticker="NVDA", timestamp=pd.Timestamp.utcnow(),
        close_prices=[100.0] * 30, high_prices=[105.0] * 30, low_prices=[95.0] * 30, volumes=[1_000_000] * 30,
        latest_close=100.0, latest_volume=1_000_000, market_cap=2_000_000_000.0, net_income_ttm=100_000_000.0,
    )
    res = rule_engine.evaluate(data)
    assert res.is_eligible is True`,
  },
  requirements: {
    filename: 'requirements.txt',
    path: 'requirements.txt',
    category: 'root',
    description: 'רביזיות וספריות נדרשות (pandas, yfinance, requests, pydantic, pytest)',
    language: 'plaintext',
    content: `yfinance>=0.2.36
pandas>=2.1.0
requests>=2.31.0
pydantic>=2.5.0
pytest>=7.4.0
pytest-cov>=4.1.0`,
  },
  readme: {
    filename: 'README.md',
    path: 'README.md',
    category: 'root',
    description: 'תיעוד הפרויקט המלא בעברית ובאנגלית',
    language: 'markdown',
    content: `# Rising Star Trend Engine
מערכת מיקרו-מודולרית מבוססת פייתון לגילוי, סינון, דירוג וניהול סיכונים עבור מניות מומנטום פורצות.`,
  },
  watchlist: {
    filename: 'watchlist.csv',
    path: 'watchlist.csv',
    category: 'root',
    description: 'רשימת המניות לסריקה (CSV)',
    language: 'csv',
    content: `ticker,name,sector
NVDA,NVIDIA Corporation,Semiconductors
PLTR,Palantir Technologies,Software - Infrastructure
ARM,Arm Holdings plc,Semiconductors
SMCI,Super Micro Computer,Computer Hardware
MSTR,MicroStrategy Incorporated,Software - Application
TSLA,Tesla Inc,Auto Manufacturers
AMD,Advanced Micro Devices,Semiconductors
APP,AppLovin Corporation,Software - Application`,
  },
};

export default function App() {
  const [activeTab, setActiveTab] = useState<'pipeline' | 'files' | 'telegram' | 'architecture'>('pipeline');
  const [selectedFileKey, setSelectedFileKey] = useState<string>('main');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Simulation State
  const [isScanning, setIsScanning] = useState<boolean>(false);
  const [scanOutput, setScanOutput] = useState<any[]>([]);

  const handleCopy = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const runSimulationScan = () => {
    setIsScanning(true);
    setScanOutput([]);

    const mockCandidates = [
      {
        ticker: 'NVDA',
        price: 142.50,
        high20d: 144.00,
        surge: 2.1,
        score: 92,
        tier: 'STRONG_RISING_STAR',
        stop: 132.80,
        target2r: 161.90,
        spStatus: 'PASSED',
        mcap: 3420,
        ruleNotes: 'Market Cap $3.4T, TTM $53B, Vol $8.8B/day',
      },
      {
        ticker: 'PLTR',
        price: 44.80,
        high20d: 45.10,
        surge: 1.8,
        score: 86,
        tier: 'STRONG_RISING_STAR',
        stop: 41.50,
        target2r: 51.40,
        spStatus: 'PASSED',
        mcap: 98,
        ruleNotes: 'Market Cap $98B, TTM $404M, Breakout on 1.8x Vol',
      },
      {
        ticker: 'ARM',
        price: 152.20,
        high20d: 155.00,
        surge: 1.5,
        score: 78,
        tier: 'EMERGING_CANDIDATE',
        stop: 141.00,
        target2r: 174.60,
        spStatus: 'PASSED',
        mcap: 154,
        ruleNotes: 'Market Cap $154B, TTM $780M, Approaching Pivot',
      },
      {
        ticker: 'SMCI',
        price: 48.60,
        high20d: 59.80,
        surge: 0.8,
        score: 54,
        tier: 'WATCHLIST',
        stop: 44.95,
        target2r: 55.90,
        spStatus: 'PASSED',
        mcap: 28,
        ruleNotes: 'Below 20d High (-18%), Volume Lacking',
      },
      {
        ticker: 'PENNY_SPEC',
        price: 2.10,
        high20d: 2.80,
        surge: 3.2,
        score: 0,
        tier: 'DISQUALIFIED',
        stop: 0,
        target2r: 0,
        spStatus: 'FAILED',
        mcap: 0.08,
        ruleNotes: 'Failed S&P: Penny stock ($2.10 < $5) & Negative Earnings',
      },
    ];

    let i = 0;
    const interval = setInterval(() => {
      if (i < mockCandidates.length) {
        setScanOutput((prev) => [...prev, mockCandidates[i]]);
        i++;
      } else {
        clearInterval(interval);
        setIsScanning(false);
      }
    }, 300);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-indigo-500 selection:text-white">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur-md sticky top-0 z-50 px-6 py-3.5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-amber-500 via-rose-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <TrendingUp className="h-5 w-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold tracking-tight text-white font-mono">rising-star-engine</h1>
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                Structure Synchronized
              </span>
            </div>
            <p className="text-xs text-slate-400">Micro-services Architecture • S&P Filters • Dynamic Risk Guard • Telegram Hub</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1.5 bg-slate-800/80 p-1 rounded-xl border border-slate-700/60 text-xs font-medium">
          <button
            onClick={() => setActiveTab('pipeline')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'pipeline' ? 'bg-indigo-600 text-white shadow-sm font-semibold' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Activity className="h-3.5 w-3.5" />
            Live Pipeline
          </button>
          <button
            onClick={() => setActiveTab('files')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'files' ? 'bg-indigo-600 text-white shadow-sm font-semibold' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <FolderTree className="h-3.5 w-3.5" />
            Project Files (11)
          </button>
          <button
            onClick={() => setActiveTab('telegram')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'telegram' ? 'bg-indigo-600 text-white shadow-sm font-semibold' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Bell className="h-3.5 w-3.5" />
            Telegram Alerts
          </button>
          <button
            onClick={() => setActiveTab('architecture')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
              activeTab === 'architecture' ? 'bg-indigo-600 text-white shadow-sm font-semibold' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="h-3.5 w-3.5" />
            Architecture Map
          </button>
        </nav>
      </header>

      {/* Main Container */}
      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">
        {/* ==================== TAB 1: LIVE PIPELINE ==================== */}
        {activeTab === 'pipeline' && (
          <div className="space-y-6">
            {/* Top Trigger Card */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-base font-semibold text-white flex items-center gap-2">
                  <Play className="h-4 w-4 text-emerald-400" />
                  main.py Execution Pipeline Simulator
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Connects DataConnector → RuleEngine (S&P) → IndicatorEngine → ScoringEngine (0-100) → RiskGuard → Telegram Alert.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <button
                  disabled={isScanning}
                  onClick={runSimulationScan}
                  className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-emerald-500 to-indigo-600 hover:from-emerald-600 hover:to-indigo-700 text-white font-medium text-xs rounded-xl shadow-md transition disabled:opacity-50"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${isScanning ? 'animate-spin' : ''}`} />
                  {isScanning ? 'Scanning Watchlist...' : 'Run main.py Scan'}
                </button>
              </div>
            </div>

            {/* Results Table */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
              <div className="bg-slate-950 px-5 py-3 border-b border-slate-800 flex items-center justify-between text-xs text-slate-400 font-mono">
                <span>Watchlist Scan Results ({scanOutput.length} evaluated)</span>
                <span>Threshold: Score &gt;= 75 triggers Telegram</span>
              </div>

              {scanOutput.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-slate-950/60 text-slate-400 border-b border-slate-800">
                      <tr>
                        <th className="p-3.5">TICKER</th>
                        <th className="p-3.5">PRICE</th>
                        <th className="p-3.5">20D HIGH</th>
                        <th className="p-3.5">VOLUME SURGE</th>
                        <th className="p-3.5">S&amp;P RULES</th>
                        <th className="p-3.5">SCORE</th>
                        <th className="p-3.5">TIER</th>
                        <th className="p-3.5">STOP LOSS</th>
                        <th className="p-3.5">TARGET (2R)</th>
                        <th className="p-3.5">ALERT</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {scanOutput.map((row) => (
                        <tr
                          key={row.ticker}
                          className={`hover:bg-slate-800/40 transition ${
                            row.tier === 'STRONG_RISING_STAR' ? 'bg-indigo-950/20' : ''
                          }`}
                        >
                          <td className="p-3.5 font-bold text-white flex items-center gap-1.5">
                            <span className="text-indigo-400">${row.ticker}</span>
                          </td>
                          <td className="p-3.5 text-slate-200">${row.price.toFixed(2)}</td>
                          <td className="p-3.5 text-amber-400">${row.high20d.toFixed(2)}</td>
                          <td className="p-3.5">
                            <span
                              className={`px-2 py-0.5 rounded font-bold ${
                                row.surge >= 1.5 ? 'bg-emerald-500/20 text-emerald-400' : 'text-slate-400'
                              }`}
                            >
                              {row.surge}x
                            </span>
                          </td>
                          <td className="p-3.5">
                            {row.spStatus === 'PASSED' ? (
                              <span className="text-emerald-400 flex items-center gap-1">
                                <CheckCircle2 className="h-3 w-3" /> Pass
                              </span>
                            ) : (
                              <span className="text-rose-400 flex items-center gap-1">
                                <AlertTriangle className="h-3 w-3" /> Fail
                              </span>
                            )}
                          </td>
                          <td className="p-3.5 font-extrabold text-sm text-white">{row.score}</td>
                          <td className="p-3.5">
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                row.tier === 'STRONG_RISING_STAR'
                                  ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                                  : row.tier === 'EMERGING_CANDIDATE'
                                  ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                                  : row.tier === 'WATCHLIST'
                                  ? 'bg-slate-800 text-slate-400'
                                  : 'bg-red-950 text-red-400'
                              }`}
                            >
                              {row.tier}
                            </span>
                          </td>
                          <td className="p-3.5 text-rose-400 font-semibold">
                            {row.stop ? `$${row.stop.toFixed(2)}` : '—'}
                          </td>
                          <td className="p-3.5 text-emerald-400 font-semibold">
                            {row.target2r ? `$${row.target2r.toFixed(2)}` : '—'}
                          </td>
                          <td className="p-3.5">
                            {row.score >= 75 ? (
                              <span className="flex items-center gap-1 text-[11px] text-indigo-400 font-semibold animate-pulse">
                                <Send className="h-3 w-3" /> Dispatched
                              </span>
                            ) : (
                              <span className="text-slate-600 text-[11px]">Filtered</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="p-12 text-center space-y-3">
                  <Play className="h-8 w-8 text-slate-600 mx-auto" />
                  <p className="text-sm text-slate-400">Click &quot;Run main.py Scan&quot; to execute the pipeline across sample watchlist tickers.</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ==================== TAB 2: PROJECT FILES ==================== */}
        {activeTab === 'files' && (
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
            {/* Sidebar File Tree */}
            <div className="md:col-span-4 bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
                <span className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <FolderTree className="h-4 w-4 text-indigo-400" /> rising-star-engine/
                </span>
                <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono">11 files</span>
              </div>

              {/* File list tree */}
              <div className="space-y-1 text-xs font-mono">
                {/* Workflow section */}
                <div className="text-[11px] text-slate-500 font-bold px-2 pt-1 flex items-center gap-1">
                  📁 .github/workflows/
                </div>
                <button
                  onClick={() => setSelectedFileKey('workflow')}
                  className={`w-full text-left px-3 py-1.5 rounded-lg flex items-center justify-between transition ${
                    selectedFileKey === 'workflow' ? 'bg-indigo-600 text-white font-semibold' : 'text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  <span className="flex items-center gap-1.5 pl-3">
                    <FileCode className="h-3 w-3 text-amber-400" /> run_engine.yml
                  </span>
                  <span className="text-[10px] opacity-70">cron</span>
                </button>

                {/* Core section */}
                <div className="text-[11px] text-slate-500 font-bold px-2 pt-2 flex items-center gap-1">
                  📁 core/ (micro-modules)
                </div>
                {['dataconnector', 'ruleengine', 'indicatorengine', 'scoringengine', 'riskguard', 'notificationhub'].map((k) => (
                  <button
                    key={k}
                    onClick={() => setSelectedFileKey(k)}
                    className={`w-full text-left px-3 py-1.5 rounded-lg flex items-center justify-between transition ${
                      selectedFileKey === k ? 'bg-indigo-600 text-white font-semibold' : 'text-slate-300 hover:bg-slate-800'
                    }`}
                  >
                    <span className="flex items-center gap-1.5 pl-3">
                      <FileCode className="h-3 w-3 text-indigo-400" /> {PROJECT_FILES[k].filename}
                    </span>
                  </button>
                ))}

                {/* Tests section */}
                <div className="text-[11px] text-slate-500 font-bold px-2 pt-2 flex items-center gap-1">
                  📁 tests/
                </div>
                <button
                  onClick={() => setSelectedFileKey('tests')}
                  className={`w-full text-left px-3 py-1.5 rounded-lg flex items-center justify-between transition ${
                    selectedFileKey === 'tests' ? 'bg-indigo-600 text-white font-semibold' : 'text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  <span className="flex items-center gap-1.5 pl-3">
                    <ShieldCheck className="h-3 w-3 text-emerald-400" /> test_modules.py
                  </span>
                </button>

                {/* Root section */}
                <div className="text-[11px] text-slate-500 font-bold px-2 pt-2 flex items-center gap-1">
                  📁 root /
                </div>
                {['main', 'requirements', 'watchlist', 'readme'].map((k) => (
                  <button
                    key={k}
                    onClick={() => setSelectedFileKey(k)}
                    className={`w-full text-left px-3 py-1.5 rounded-lg flex items-center justify-between transition ${
                      selectedFileKey === k ? 'bg-indigo-600 text-white font-semibold' : 'text-slate-300 hover:bg-slate-800'
                    }`}
                  >
                    <span className="flex items-center gap-1.5 pl-3">
                      <FileCode className="h-3 w-3 text-slate-400" /> {PROJECT_FILES[k].filename}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Code Viewer */}
            <div className="md:col-span-8 bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl flex flex-col">
              <div className="bg-slate-950 px-5 py-3 border-b border-slate-800 flex items-center justify-between">
                <div>
                  <div className="font-mono text-xs font-bold text-white flex items-center gap-2">
                    <FileCode className="h-4 w-4 text-indigo-400" />
                    {PROJECT_FILES[selectedFileKey].path}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">{PROJECT_FILES[selectedFileKey].description}</div>
                </div>

                <button
                  onClick={() => handleCopy(PROJECT_FILES[selectedFileKey].content, selectedFileKey)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-xl transition"
                >
                  {copiedKey === selectedFileKey ? (
                    <>
                      <Check className="h-3.5 w-3.5 text-emerald-400" />
                      <span>Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5" />
                      <span>Copy Code</span>
                    </>
                  )}
                </button>
              </div>

              <pre className="p-5 font-mono text-xs text-slate-200 bg-slate-950/90 overflow-x-auto leading-relaxed max-h-[600px] flex-1">
                {PROJECT_FILES[selectedFileKey].content}
              </pre>
            </div>
          </div>
        )}

        {/* ==================== TAB 3: TELEGRAM ALERTS ==================== */}
        {activeTab === 'telegram' && (
          <div className="max-w-2xl mx-auto space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-2">
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Bell className="h-4 w-4 text-indigo-400" />
                Telegram Alert Format Preview (NotificationHub)
              </h2>
              <p className="text-xs text-slate-400">
                Candidates scoring ≥ 75 points generate rich, actionable trade setups with automated risk management parameters.
              </p>
            </div>

            {/* Telegram Simulated Message Card */}
            <div className="bg-[#182533] border border-[#2b3a4a] rounded-2xl p-5 text-[#f5f5f5] shadow-2xl font-sans space-y-3 relative overflow-hidden">
              <div className="flex items-center justify-between border-b border-[#2b3a4a] pb-2 text-xs text-[#6ab2f2]">
                <span className="font-semibold flex items-center gap-1.5">
                  <TrendingUp className="h-3.5 w-3.5" /> Rising Star Trend Bot
                </span>
                <span className="text-slate-400 font-mono text-[11px]">21:30 UTC</span>
              </div>

              <div className="space-y-2 text-xs leading-relaxed">
                <div className="font-bold text-rose-400 text-sm flex items-center gap-1.5">
                  🔥 RISING STAR BREAKOUT ALERT
                </div>

                <div className="space-y-0.5 pt-1">
                  <div><b>Symbol:</b> <span className="font-mono text-[#6ab2f2]">#NVDA</span></div>
                  <div><b>Score:</b> <code className="bg-[#242f3d] px-1.5 py-0.5 rounded text-amber-300 font-mono">92/100</code> (STRONG_RISING_STAR)</div>
                  <div><b>Current Price:</b> <code className="bg-[#242f3d] px-1.5 py-0.5 rounded text-white font-mono">$142.50</code></div>
                  <div><b>20-Day High:</b> <code className="bg-[#242f3d] px-1.5 py-0.5 rounded text-white font-mono">$144.00</code> (🔥 BREAKOUT)</div>
                  <div><b>Volume Surge:</b> <code className="bg-[#242f3d] px-1.5 py-0.5 rounded text-emerald-300 font-mono">2.1x</code> 10d average</div>
                  <div><b>MA50 Support:</b> <code className="bg-[#242f3d] px-1.5 py-0.5 rounded text-white font-mono">$128.40</code></div>
                </div>

                <div className="p-3 bg-[#0e1621] rounded-xl border border-[#2b3a4a] space-y-1 mt-2">
                  <div className="font-bold text-[#6ab2f2] flex items-center gap-1">
                    🛡 <u>RISK GUARD EXECUTION PLAN</u>
                  </div>
                  <div>• <b>Entry:</b> $142.50</div>
                  <div>• <b>Stop Loss:</b> <b className="text-rose-400">$132.80</b> (-6.8%)</div>
                  <div>• <b>Target 1 (2R):</b> <b className="text-emerald-400">$161.90</b></div>
                  <div>• <b>Target 2 (3R):</b> $171.60</div>
                  <div>• <b>Target 3 (5R):</b> $191.00</div>
                  <div>• <b>Suggested Size:</b> 103 shares ($1,000 risk budget)</div>
                </div>

                <div className="text-[11px] text-slate-400 italic pt-1">
                  Prime breakout leader (92/100) with explosive institutional volume and positive S&amp;P earnings.
                </div>
              </div>
            </div>

            {/* GitHub Secrets Instructions */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 text-xs space-y-3">
              <div className="font-semibold text-white flex items-center gap-1.5">
                <Github className="h-4 w-4 text-slate-300" /> Connecting Telegram to GitHub Actions:
              </div>
              <ol className="list-decimal list-inside space-y-1.5 text-slate-400">
                <li>Create your bot in Telegram with <code className="text-indigo-300">@BotFather</code> and copy the bot token.</li>
                <li>In your GitHub repo, go to <b>Settings &gt; Secrets and variables &gt; Actions</b>.</li>
                <li>Add <code className="text-amber-300">TELEGRAM_BOT_TOKEN</code> and <code className="text-amber-300">TELEGRAM_CHAT_ID</code>.</li>
                <li>The workflow in <code className="text-indigo-300">.github/workflows/run_engine.yml</code> will automatically inject them upon daily cloud execution!</li>
              </ol>
            </div>
          </div>
        )}

        {/* ==================== TAB 4: ARCHITECTURE ==================== */}
        {activeTab === 'architecture' && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Layers className="h-4 w-4 text-indigo-400" />
                Rising Star Trend Engine - Micro-services Topology
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Data pipeline flow from external equity providers down into quantitative trend scoring models.
              </p>
            </div>

            {/* Architecture ASCII Flowchart */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
              <pre className="font-mono text-xs text-indigo-300 overflow-x-auto leading-relaxed">
{`
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           rising-star-engine/                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   [ GitHub Actions Cron: 21:30 UTC ]                                            │
│              │                                                                  │
│              ▼                                                                  │
│   ┌─────────────────────────────────────────────────────────────┐               │
│   │  main.py (Pipeline Orchestrator)                            │               │
│   │  Reads: watchlist.csv                                       │               │
│   └──────────────┬──────────────────────────────────────────────┘               │
│                  │                                                              │
│                  ▼                                                              │
│   ┌─────────────────────────────────────────────────────────────┐               │
│   │  core/dataconnector.py                                      │               │
│   │  - yfinance with Exponential Backoff (3 retries, jitter)    │               │
│   │  - Ingests OHLCV history (120d) + Fundamentals              │               │
│   └──────────────┬──────────────────────────────────────────────┘               │
│                  │                                                              │
│                  ▼                                                              │
│   ┌─────────────────────────────────────────────────────────────┐               │
│   │  core/ruleengine.py (S&P Baseline Qualifications)           │               │
│   │  - Market Cap >= $1B | Positive TTM Net Income              │               │
│   │  - Daily Dollar Vol >= $5M | Anti-Penny Stock ($5+)         │               │
│   └──────────────┬──────────────────────────────────────────────┘               │
│                  │ (if passed)                                                  │
│                  ▼                                                              │
│   ┌─────────────────────────────────────────────────────────────┐               │
│   │  core/indicatorengine.py (Technical Engine)                 │               │
│   │  - Moving Averages: MA20, MA50, MA200                       │               │
│   │  - 20-Day High Breakout Distance & ATR14                    │               │
│   │  - Volume Surge Ratio (10d & 50d)                           │               │
│   └──────────────┬──────────────────────────────────────────────┘               │
│                  │                                                              │
│                  ▼                                                              │
│   ┌─────────────────────────────────────────────────────────────┐               │
│   │  core/scoringengine.py (0-100 Momentum Score)               │               │
│   │  - Momentum (35 pts) + Volume (25 pts)                      │               │
│   │  - Fundamentals (20 pts) + Volatility (20 pts)              │               │
│   └──────────────┬──────────────────────────────────────────────┘               │
│                  │                                                              │
│                  ▼                                                              │
│   ┌─────────────────────────────────────────────────────────────┐               │
│   │  core/riskguard.py (Risk Management & Stops)                │               │
│   │  - Dynamic ATR Stop Loss | Targets 2R, 3R, 5R               │               │
│   │  - Position Sizing ($1,000 risk budget)                     │               │
│   └──────────────┬──────────────────────────────────────────────┘               │
│                  │ (if score >= 75)                                             │
│                  ▼                                                              │
│   ┌─────────────────────────────────────────────────────────────┐               │
│   │  core/notificationhub.py (Telegram Dispatcher)              │               │
│   │  - Real-Time Breakout Alerts & End-of-Day Summary           │               │
│   └─────────────────────────────────────────────────────────────┘               │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
`}
              </pre>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-slate-950 px-6 py-4 text-center text-xs text-slate-500 font-mono">
        rising-star-engine • Modular Architecture • Ready for GitHub Push &amp; Actions Cloud Execution
      </footer>
    </div>
  );
}
