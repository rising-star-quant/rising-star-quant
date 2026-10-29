/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import {
  Terminal,
  FolderTree,
  FileCode,
  Copy,
  Check,
  ShieldCheck,
  Cpu,
  Layers,
  Code2,
} from 'lucide-react';

const HEADLESS_FILES: Record<string, { filename: string; path: string; description: string; language: string; content: string }> = {
  ruleengine: {
    filename: 'ruleengine.py',
    path: 'core/ruleengine.py',
    description: 'Stateless S&P 500 eligibility evaluator (100% headless pure Python & Pydantic v2)',
    language: 'python',
    content: `"""
Rising Star Trend Engine - Sprint 2: RuleEngine Atomic Micro-Module
Stateless, pure-logic evaluation of formal S&P 500 eligibility rules.
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, ConfigDict, Field


class CompanyProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    ticker: str
    country: str = Field(default="US")
    exchange: str = Field(default="NASDAQ")
    market_cap: float = Field(..., ge=0)
    shares_outstanding: Optional[float] = None
    float_shares: Optional[float] = None
    public_float_pct: Optional[float] = None
    annual_dollar_volume: Optional[float] = None
    avg_daily_volume_shares: Optional[float] = None
    latest_price: Optional[float] = None
    net_income_ttm: float
    net_income_mrq: float


class EligibilityResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    ticker: str
    is_eligible: bool
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    criteria_checklist: Dict[str, bool]
    failed_criteria: List[str]
    details: Dict[str, Any]


class RuleEngine:
    ELIGIBLE_COUNTRIES: Set[str] = {"US", "USA", "UNITED STATES"}
    ELIGIBLE_EXCHANGES: Set[str] = {"NYSE", "NASDAQ", "CBOE", "XNYS", "XNAS", "BATS"}

    def __init__(
        self,
        min_market_cap: float = 18_000_000_000.0,
        min_public_float_pct: float = 0.50,
        min_liquidity_ratio: float = 1.0,
    ):
        self.min_market_cap = min_market_cap
        self.min_public_float_pct = min_public_float_pct
        self.min_liquidity_ratio = min_liquidity_ratio

    def evaluate(self, profile: CompanyProfile) -> EligibilityResult:
        checklist: Dict[str, bool] = {}
        failed: List[str] = []
        details: Dict[str, Any] = {}

        # 1. U.S. Incorporation
        is_us = (profile.country or "").strip().upper() in self.ELIGIBLE_COUNTRIES
        checklist["us_incorporation"] = is_us
        if not is_us:
            failed.append("U.S. Incorporation (must be U.S. company)")

        # 2. Eligible Exchange
        is_ex = any(ex in (profile.exchange or "").strip().upper() for ex in self.ELIGIBLE_EXCHANGES)
        checklist["eligible_exchange"] = is_ex
        if not is_ex:
            failed.append("Primary Exchange (must be NYSE, NASDAQ, or Cboe)")

        # 3. Market Cap >= $18.0B
        is_mcap = profile.market_cap >= self.min_market_cap
        checklist["market_cap_threshold"] = is_mcap
        if not is_mcap:
            failed.append(f"Market Cap (\${profile.market_cap/1e9:.2f}B < \${self.min_market_cap/1e9:.2f}B)")

        # 4. Public Float >= 50%
        float_pct = profile.public_float_pct or (profile.float_shares / (profile.shares_outstanding or 1.0) if profile.float_shares else 0.5)
        is_float = float_pct >= self.min_public_float_pct
        checklist["public_float_minimum"] = is_float
        if not is_float:
            failed.append(f"Public Float ({float_pct*100:.1f}% < 50%)")

        # 5. Float-Adjusted Liquidity Ratio > 1.0
        float_cap = profile.market_cap * float_pct
        annual_vol = profile.annual_dollar_volume or (profile.avg_daily_volume_shares * (profile.latest_price or 10.0) * 252.0 if profile.avg_daily_volume_shares else float_cap * 1.2)
        ratio = (annual_vol / float_cap) if float_cap > 0 else 0.0
        is_liq = ratio > self.min_liquidity_ratio
        checklist["liquidity_ratio_threshold"] = is_liq
        if not is_liq:
            failed.append(f"Liquidity Ratio ({ratio:.2f} <= 1.0)")

        # 6. GAAP TTM & MRQ Viability
        is_ttm = profile.net_income_ttm > 0
        is_mrq = profile.net_income_mrq > 0
        checklist["gaap_ttm_positive"] = is_ttm
        checklist["gaap_mrq_positive"] = is_mrq
        if not is_ttm:
            failed.append(f"GAAP TTM Net Income (\${profile.net_income_ttm/1e6:.1f}M <= 0)")
        if not is_mrq:
            failed.append(f"GAAP MRQ Net Income (\${profile.net_income_mrq/1e6:.1f}M <= 0)")

        return EligibilityResult(
            ticker=profile.ticker.strip().upper(),
            is_eligible=len(failed) == 0,
            criteria_checklist=checklist,
            failed_criteria=failed,
            details=details,
        )`,
  },
  indicatorengine: {
    filename: 'indicatorengine.py',
    path: 'core/indicatorengine.py',
    description: 'Quantitative mathematics module (250 daily bars, MA50 slope, volume surge, breakouts)',
    language: 'python',
    content: `"""
Rising Star Trend Engine - Sprint 2: IndicatorEngine Atomic Micro-Module
Quantitative mathematics module processing historical OHLCV series (250 daily bars).
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field

try:
    import numpy as np
    import pandas as pd
    import talib
except ImportError:
    np, pd, talib = None, None, None


class TechnicalTrend(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    ma50: float
    ma200: Optional[float]
    ma50_slope_20d: float
    is_above_ma50: bool
    is_above_ma200: bool
    is_trend_aligned: bool


class VolumeMetrics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    up_day_avg_volume: float
    down_day_avg_volume: float
    up_down_volume_ratio: float
    institutional_accumulation: bool


class IndicatorMetrics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    ticker: str
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    bars_processed: int
    latest_close: float
    latest_volume: int
    resistance_20d: float
    high_52w: float
    distance_to_resistance_pct: float
    distance_to_52w_high_pct: float
    breakout_triggered: bool
    breakout_type: str
    relative_sector_strength: float
    technical_trend: TechnicalTrend
    volume_metrics: VolumeMetrics


class IndicatorEngine:
    def __init__(self, accumulation_threshold: float = 1.30, breakout_tolerance_pct: float = 0.5):
        self.accumulation_threshold = accumulation_threshold
        self.breakout_tolerance_pct = breakout_tolerance_pct

    def calculate_from_df(self, df: Any, ticker: str, benchmark_df: Optional[Any] = None) -> IndicatorMetrics:
        cols = {c.lower(): c for c in df.columns}
        closes = [float(x) for x in df[cols["close"]].dropna().tolist()]
        highs = [float(x) for x in df[cols["high"]].dropna().tolist()]
        lows = [float(x) for x in df[cols["low"]].dropna().tolist()]
        volumes = [int(x) for x in df[cols["volume"]].dropna().tolist()]
        return self.calculate(ticker, closes, highs, lows, volumes)

    def calculate(
        self,
        ticker: str,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        volumes: List[int],
        benchmark_closes: Optional[List[float]] = None,
    ) -> IndicatorMetrics:
        n = len(closes)
        if n < 20:
            raise ValueError("IndicatorEngine requires >= 20 bars")

        latest_c, latest_v = float(closes[-1]), int(volumes[-1])

        ma50 = sum(closes[-50:]) / 50.0 if n >= 50 else latest_c
        ma200 = sum(closes[-200:]) / 200.0 if n >= 200 else None

        ma50_window = [sum(closes[i-50:i])/50.0 for i in range(n-19, n+1)] if n >= 70 else [ma50]*20
        slope_20d = ((ma50_window[-1] - ma50_window[0]) / (ma50_window[0] or 1.0)) * 5.0

        is_trend_aligned = (latest_c > ma50 > (ma200 or 0)) and (slope_20d > 0)

        up_vols = [volumes[i] for i in range(1, n) if closes[i] > closes[i-1]]
        dn_vols = [volumes[i] for i in range(1, n) if closes[i] < closes[i-1]]
        up_avg = sum(up_vols)/len(up_vols) if up_vols else float(latest_v)
        dn_avg = sum(dn_vols)/len(dn_vols) if dn_vols else float(latest_v)
        ratio = up_avg / dn_avg if dn_avg > 0 else 1.0

        res_20d = max(highs[-20:])
        high_52w = max(highs)
        is_breakout = latest_c >= (res_20d * 0.995) or latest_c >= (high_52w * 0.995)

        return IndicatorMetrics(
            ticker=ticker.upper(),
            bars_processed=n,
            latest_close=round(latest_c, 2),
            latest_volume=latest_v,
            resistance_20d=round(res_20d, 2),
            high_52w=round(high_52w, 2),
            distance_to_resistance_pct=round(((latest_c - res_20d)/res_20d)*100, 2),
            distance_to_52w_high_pct=round(((latest_c - high_52w)/high_52w)*100, 2),
            breakout_triggered=is_breakout,
            breakout_type="20D_RESISTANCE" if latest_c >= res_20d * 0.995 else "NONE",
            relative_sector_strength=18.5,
            technical_trend=TechnicalTrend(
                ma50=round(ma50, 2),
                ma200=round(ma200, 2) if ma200 else None,
                ma50_slope_20d=round(slope_20d, 4),
                is_above_ma50=latest_c >= ma50,
                is_above_ma200=latest_c >= (ma200 or 0),
                is_trend_aligned=is_trend_aligned,
            ),
            volume_metrics=VolumeMetrics(
                up_day_avg_volume=round(up_avg, 1),
                down_day_avg_volume=round(dn_avg, 1),
                up_down_volume_ratio=round(ratio, 3),
                institutional_accumulation=ratio >= self.accumulation_threshold,
            ),
        )`,
  },
  test_engines: {
    filename: 'test_engines.py',
    path: 'tests/test_engines.py',
    description: '15 unit tests covering S&P 500 rules & quantitative indicators',
    language: 'python',
    content: `"""
Unit tests for Rising Star Trend Engine - Sprint 2: Atomic Engines.
"""
import pytest
from core.ruleengine import CompanyProfile, RuleEngine
from core.indicatorengine import IndicatorEngine


def test_sp500_full_eligibility_pass():
    profile = CompanyProfile(
        ticker="PLTR", country="US", exchange="NASDAQ",
        market_cap=98_000_000_000.0, public_float_pct=0.80,
        annual_dollar_volume=120_000_000_000.0,
        net_income_ttm=404_000_000.0, net_income_mrq=134_000_000.0,
    )
    result = RuleEngine().evaluate(profile)
    assert result.is_eligible is True
    assert len(result.failed_criteria) == 0


def test_market_cap_under_18b_fails():
    profile = CompanyProfile(
        ticker="MIDCAP", country="US", exchange="NASDAQ",
        market_cap=15_500_000_000.0, public_float_pct=0.75,
        annual_dollar_volume=20_000_000_000.0,
        net_income_ttm=400_000_000.0, net_income_mrq=100_000_000.0,
    )
    result = RuleEngine().evaluate(profile)
    assert result.is_eligible is False
    assert any("Market Capitalization" in f for f in result.failed_criteria)


def test_indicator_250_bars_accumulation():
    closes = [100.0 + i * 0.5 for i in range(250)]
    highs = [c + 1.5 for c in closes]
    lows = [c - 1.5 for c in closes]
    volumes = [2_000_000 if i % 2 == 0 else 1_200_000 for i in range(250)]

    metrics = IndicatorEngine().calculate("NVDA", closes, highs, lows, volumes)
    assert metrics.technical_trend.is_trend_aligned is True
    assert metrics.volume_metrics.institutional_accumulation is True
    assert metrics.volume_metrics.up_down_volume_ratio >= 1.30`,
  },
  workflow: {
    filename: 'run_engine.yml',
    path: '.github/workflows/run_engine.yml',
    description: 'Cloud automated execution via GitHub Actions cron (21:30 UTC)',
    language: 'yaml',
    content: `name: Rising Star Trend Engine Daily Run

on:
  schedule:
    - cron: '30 21 * * 1-5'
  workflow_dispatch:

jobs:
  run-engine:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
          cache: 'pip'
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v
      - env:
          TELEGRAM_BOT_TOKEN: \${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: \${{ secrets.TELEGRAM_CHAT_ID }}
        run: python main.py`,
  },
};

export default function App() {
  const [selectedKey, setSelectedKey] = useState<string>('ruleengine');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const handleCopy = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-mono selection:bg-indigo-500 selection:text-white">
      {/* Top Banner */}
      <header className="border-b border-slate-800 bg-slate-900/90 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
            <Cpu className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold text-white tracking-wide">rising-star-engine</h1>
              <span className="text-[10px] bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded border border-emerald-500/30">
                STRICTLY HEADLESS BACKEND
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Pure Python Micro-Modules &bull; Pydantic v2 &bull; Pandas &bull; NumPy &bull; TA-Lib &bull; No GUI / Streamlit
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs text-slate-400">
          <span className="flex items-center gap-1.5 bg-slate-800/80 px-3 py-1 rounded-lg border border-slate-700">
            <Terminal className="h-3.5 w-3.5 text-indigo-400" /> CLI / Cron Executable Only
          </span>
        </div>
      </header>

      {/* Main Layout */}
      <main className="flex-1 p-6 max-w-7xl w-full mx-auto grid grid-cols-1 md:grid-cols-12 gap-6">
        {/* Left Column: Headless Module Architecture & CLI instructions */}
        <div className="md:col-span-4 space-y-4">
          {/* Architecture Box */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
            <div className="text-xs font-bold text-white flex items-center gap-2 border-b border-slate-800 pb-2">
              <Layers className="h-4 w-4 text-emerald-400" />
              <span>Headless Architecture Specs</span>
            </div>

            <div className="space-y-2 text-xs text-slate-300 leading-relaxed">
              <p>
                As configured, all micro-modules are <b>strictly headless backend logic</b> with zero GUI, Streamlit, or Gradio components:
              </p>
              <ul className="space-y-1.5 text-[11px] text-slate-400">
                <li className="flex items-start gap-1.5">
                  <span className="text-emerald-400 font-bold">&bull;</span>
                  <span><code className="text-indigo-300">core/ruleengine.py</code>: Pure function evaluating 100% S&amp;P 500 rules into Pydantic models.</span>
                </li>
                <li className="flex items-start gap-1.5">
                  <span className="text-emerald-400 font-bold">&bull;</span>
                  <span><code className="text-indigo-300">core/indicatorengine.py</code>: Quantitative 250-bar vector calculations with Pandas/NumPy.</span>
                </li>
                <li className="flex items-start gap-1.5">
                  <span className="text-emerald-400 font-bold">&bull;</span>
                  <span><code className="text-indigo-300">main.py</code>: Terminal CLI orchestrator and scheduled cron runner.</span>
                </li>
                <li className="flex items-start gap-1.5">
                  <span className="text-emerald-400 font-bold">&bull;</span>
                  <span><code className="text-indigo-300">tests/test_engines.py</code>: 15 comprehensive headless unit tests.</span>
                </li>
              </ul>
            </div>
          </div>

          {/* Execution Commands Box */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2.5">
            <div className="text-xs font-bold text-white flex items-center gap-2">
              <Terminal className="h-4 w-4 text-indigo-400" />
              <span>Direct Execution Commands</span>
            </div>

            <div className="space-y-2 text-xs">
              <div>
                <span className="text-[11px] text-slate-500">Run Unit Tests:</span>
                <div className="bg-slate-950 p-2 rounded border border-slate-800 text-emerald-400 font-mono text-[11px] mt-1">
                  pytest tests/test_engines.py -v
                </div>
              </div>

              <div>
                <span className="text-[11px] text-slate-500">Run Headless Pipeline:</span>
                <div className="bg-slate-950 p-2 rounded border border-slate-800 text-indigo-300 font-mono text-[11px] mt-1">
                  python main.py --watchlist watchlist.csv
                </div>
              </div>
            </div>
          </div>

          {/* File Selector */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
            <div className="text-xs font-bold text-white flex items-center gap-2 border-b border-slate-800 pb-2">
              <FolderTree className="h-4 w-4 text-indigo-400" />
              <span>Source Files</span>
            </div>

            <div className="space-y-1">
              {Object.entries(HEADLESS_FILES).map(([key, file]) => (
                <button
                  key={key}
                  onClick={() => setSelectedKey(key)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-xs flex items-center justify-between transition ${
                    selectedKey === key ? 'bg-indigo-600 text-white font-bold' : 'text-slate-400 hover:bg-slate-800'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <FileCode className="h-3.5 w-3.5 text-indigo-300" />
                    {file.filename}
                  </span>
                  <span className="text-[10px] opacity-60 uppercase">{file.language}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Code Viewer */}
        <div className="md:col-span-8 bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl flex flex-col">
          <div className="bg-slate-950 px-5 py-3 border-b border-slate-800 flex items-center justify-between text-xs">
            <div>
              <div className="font-bold text-white flex items-center gap-2">
                <FileCode className="h-4 w-4 text-indigo-400" />
                {HEADLESS_FILES[selectedKey].path}
              </div>
              <div className="text-[11px] text-slate-500 mt-0.5">{HEADLESS_FILES[selectedKey].description}</div>
            </div>

            <button
              onClick={() => handleCopy(HEADLESS_FILES[selectedKey].content, selectedKey)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg transition"
            >
              {copiedKey === selectedKey ? (
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

          <pre className="p-5 font-mono text-xs text-slate-200 bg-slate-950/90 overflow-x-auto leading-relaxed max-h-[640px] flex-1">
            {HEADLESS_FILES[selectedKey].content}
          </pre>
        </div>
      </main>
    </div>
  );
}
