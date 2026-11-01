/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useMemo } from 'react';
import {
  TrendingUp,
  Shield,
  Activity,
  Layers,
  Terminal,
  FileCode,
  Copy,
  Check,
  Search,
  Sliders,
  Play,
  RotateCcw,
  AlertTriangle,
  Flame,
  ArrowUpRight,
  ArrowDownRight,
  DollarSign,
  Percent,
  Calendar,
  Cloud,
  ChevronRight,
  PlusCircle,
  ExternalLink,
  RefreshCw,
  Clock,
  Briefcase,
  BarChart3,
  Cpu,
} from 'lucide-react';

// Preloaded mock data from scan_results.json & portfolio.json
interface ScanItem {
  ticker: string;
  status: string;
  score: number;
  tier: string;
  is_buy_alert: boolean;
  breakout_triggered: boolean;
  breakout_type: string;
  latest_close: number;
  resistance_20d: number;
  high_52w: number;
  distance_to_resistance_pct: number;
  ma50: number;
  ma50_slope_20d: number;
  up_down_volume_ratio: number;
  institutional_accumulation: boolean;
  relative_sector_strength: number;
  gatekeeper_approved: boolean;
  profit_factor: number;
  win_rate: number;
  atr_14: number | null;
  stop_loss_price: number | null;
  risk_pct: number | null;
  target_1r: number | null;
  target_2r: number | null;
  target_3r: number | null;
  target_5r: number | null;
  suggested_shares: number | null;
  max_loss_usd: number | null;
  timestamp: string;
}

interface PaperPos {
  id: string;
  ticker: string;
  status: 'OPEN' | 'CLOSED';
  entry_date: string;
  entry_price: number;
  shares: number;
  invested_amount: number;
  peak_price: number;
  trailing_stop_price: number;
  atr_stop_price: number | null;
  target_1r: number | null;
  target_2r: number | null;
  target_3r: number | null;
  current_price: number;
  current_value: number;
  unrealized_pnl_dollars: number;
  unrealized_pnl_pct: number;
  days_held: number;
  exit_date?: string;
  exit_price?: number;
  exit_reason?: string;
  realized_pnl_dollars?: number;
  realized_pnl_pct?: number;
}

const INITIAL_SCAN_RESULTS: ScanItem[] = [
  {
    ticker: 'NVDA',
    status: 'QUALIFIED',
    score: 92.4,
    tier: 'STRONG_RISING_STAR',
    is_buy_alert: true,
    breakout_triggered: true,
    breakout_type: '52W_HIGH',
    latest_close: 144.9,
    resistance_20d: 142.8,
    high_52w: 144.9,
    distance_to_resistance_pct: 1.47,
    ma50: 128.4,
    ma50_slope_20d: 0.42,
    up_down_volume_ratio: 1.84,
    institutional_accumulation: true,
    relative_sector_strength: 8.6,
    gatekeeper_approved: true,
    profit_factor: 2.45,
    win_rate: 66.7,
    atr_14: 4.85,
    stop_loss_price: 135.2,
    risk_pct: 6.7,
    target_1r: 154.6,
    target_2r: 164.3,
    target_3r: 174.0,
    target_5r: 193.4,
    suggested_shares: 103,
    max_loss_usd: 1000.0,
    timestamp: '2026-10-31T21:30:00Z',
  },
  {
    ticker: 'CRWD',
    status: 'QUALIFIED',
    score: 88.5,
    tier: 'STRONG_RISING_STAR',
    is_buy_alert: true,
    breakout_triggered: true,
    breakout_type: '20D_HIGH',
    latest_close: 329.8,
    resistance_20d: 325.0,
    high_52w: 398.3,
    distance_to_resistance_pct: 1.48,
    ma50: 298.2,
    ma50_slope_20d: 0.38,
    up_down_volume_ratio: 1.62,
    institutional_accumulation: true,
    relative_sector_strength: 6.4,
    gatekeeper_approved: true,
    profit_factor: 1.95,
    win_rate: 58.3,
    atr_14: 11.2,
    stop_loss_price: 307.4,
    risk_pct: 6.8,
    target_1r: 352.2,
    target_2r: 374.6,
    target_3r: 397.0,
    target_5r: 441.8,
    suggested_shares: 44,
    max_loss_usd: 1000.0,
    timestamp: '2026-10-31T21:30:00Z',
  },
  {
    ticker: 'PLTR',
    status: 'QUALIFIED',
    score: 87.2,
    tier: 'STRONG_RISING_STAR',
    is_buy_alert: true,
    breakout_triggered: true,
    breakout_type: '52W_HIGH',
    latest_close: 44.5,
    resistance_20d: 43.1,
    high_52w: 44.5,
    distance_to_resistance_pct: 3.25,
    ma50: 36.8,
    ma50_slope_20d: 0.54,
    up_down_volume_ratio: 2.15,
    institutional_accumulation: true,
    relative_sector_strength: 9.1,
    gatekeeper_approved: true,
    profit_factor: 2.1,
    win_rate: 62.5,
    atr_14: 1.75,
    stop_loss_price: 41.0,
    risk_pct: 7.87,
    target_1r: 48.0,
    target_2r: 51.5,
    target_3r: 55.0,
    target_5r: 62.0,
    suggested_shares: 285,
    max_loss_usd: 1000.0,
    timestamp: '2026-10-31T21:30:00Z',
  },
  {
    ticker: 'APP',
    status: 'QUALIFIED',
    score: 86.8,
    tier: 'STRONG_RISING_STAR',
    is_buy_alert: true,
    breakout_triggered: true,
    breakout_type: '52W_HIGH',
    latest_close: 218.4,
    resistance_20d: 210.0,
    high_52w: 218.4,
    distance_to_resistance_pct: 4.0,
    ma50: 172.0,
    ma50_slope_20d: 0.62,
    up_down_volume_ratio: 1.95,
    institutional_accumulation: true,
    relative_sector_strength: 11.2,
    gatekeeper_approved: true,
    profit_factor: 2.8,
    win_rate: 70.0,
    atr_14: 9.4,
    stop_loss_price: 199.6,
    risk_pct: 8.6,
    target_1r: 237.2,
    target_2r: 256.0,
    target_3r: 274.8,
    target_5r: 312.4,
    suggested_shares: 53,
    max_loss_usd: 1000.0,
    timestamp: '2026-10-31T21:30:00Z',
  },
  {
    ticker: 'MSFT',
    status: 'QUALIFIED',
    score: 79.4,
    tier: 'EMERGING_CANDIDATE',
    is_buy_alert: false,
    breakout_triggered: false,
    breakout_type: 'NONE',
    latest_close: 428.5,
    resistance_20d: 435.0,
    high_52w: 468.3,
    distance_to_resistance_pct: -1.49,
    ma50: 420.1,
    ma50_slope_20d: 0.12,
    up_down_volume_ratio: 1.18,
    institutional_accumulation: false,
    relative_sector_strength: 1.5,
    gatekeeper_approved: true,
    profit_factor: 1.65,
    win_rate: 54.0,
    atr_14: 7.2,
    stop_loss_price: 414.1,
    risk_pct: 3.36,
    target_1r: 442.9,
    target_2r: 457.3,
    target_3r: 471.7,
    target_5r: 500.5,
    suggested_shares: 69,
    max_loss_usd: 1000.0,
    timestamp: '2026-10-31T21:30:00Z',
  },
  {
    ticker: 'AAPL',
    status: 'QUALIFIED',
    score: 76.1,
    tier: 'EMERGING_CANDIDATE',
    is_buy_alert: false,
    breakout_triggered: false,
    breakout_type: 'NONE',
    latest_close: 232.8,
    resistance_20d: 237.2,
    high_52w: 237.2,
    distance_to_resistance_pct: -1.85,
    ma50: 226.4,
    ma50_slope_20d: 0.15,
    up_down_volume_ratio: 1.12,
    institutional_accumulation: false,
    relative_sector_strength: 0.8,
    gatekeeper_approved: true,
    profit_factor: 1.48,
    win_rate: 52.0,
    atr_14: 3.8,
    stop_loss_price: 225.2,
    risk_pct: 3.26,
    target_1r: 240.4,
    target_2r: 248.0,
    target_3r: 255.6,
    target_5r: 270.8,
    suggested_shares: 131,
    max_loss_usd: 1000.0,
    timestamp: '2026-10-31T21:30:00Z',
  },
  {
    ticker: 'TSLA',
    status: 'QUALIFIED',
    score: 68.2,
    tier: 'WATCHLIST_NEUTRAL',
    is_buy_alert: false,
    breakout_triggered: false,
    breakout_type: 'NONE',
    latest_close: 255.4,
    resistance_20d: 268.0,
    high_52w: 271.0,
    distance_to_resistance_pct: -4.7,
    ma50: 238.5,
    ma50_slope_20d: 0.22,
    up_down_volume_ratio: 1.05,
    institutional_accumulation: false,
    relative_sector_strength: -2.1,
    gatekeeper_approved: false,
    profit_factor: 1.12,
    win_rate: 48.0,
    atr_14: 12.5,
    stop_loss_price: null,
    risk_pct: null,
    target_1r: null,
    target_2r: null,
    target_3r: null,
    target_5r: null,
    suggested_shares: null,
    max_loss_usd: null,
    timestamp: '2026-10-31T21:30:00Z',
  },
];

const INITIAL_PORTFOLIO_POSITIONS: PaperPos[] = [
  {
    id: 'pos-NVDA-20261024',
    ticker: 'NVDA',
    status: 'OPEN',
    entry_date: '2026-10-24',
    entry_price: 138.25,
    shares: 72,
    invested_amount: 9954.0,
    peak_price: 146.5,
    trailing_stop_price: 131.85,
    atr_stop_price: 130.4,
    target_1r: 145.0,
    target_2r: 152.0,
    target_3r: 160.0,
    current_price: 144.9,
    current_value: 10432.8,
    unrealized_pnl_dollars: 478.8,
    unrealized_pnl_pct: 4.81,
    days_held: 7,
  },
  {
    id: 'pos-CRWD-20261026',
    ticker: 'CRWD',
    status: 'OPEN',
    entry_date: '2026-10-26',
    entry_price: 315.4,
    shares: 31,
    invested_amount: 9777.4,
    peak_price: 332.1,
    trailing_stop_price: 298.89,
    atr_stop_price: 296.2,
    target_1r: 331.0,
    target_2r: 346.0,
    target_3r: 362.0,
    current_price: 329.8,
    current_value: 10223.8,
    unrealized_pnl_dollars: 446.4,
    unrealized_pnl_pct: 4.57,
    days_held: 5,
  },
  {
    id: 'pos-AMD-20261018',
    ticker: 'AMD',
    status: 'CLOSED',
    entry_date: '2026-10-18',
    entry_price: 154.2,
    shares: 65,
    invested_amount: 10023.0,
    peak_price: 168.9,
    trailing_stop_price: 152.01,
    atr_stop_price: 148.5,
    target_1r: 162.0,
    target_2r: 170.0,
    target_3r: 178.0,
    current_price: 151.8,
    current_value: 0.0,
    unrealized_pnl_dollars: 0.0,
    unrealized_pnl_pct: 0.0,
    days_held: 11,
    exit_date: '2026-10-29',
    exit_price: 152.01,
    exit_reason: 'RiskGuard: TRAILING_STOP',
    realized_pnl_dollars: -142.35,
    realized_pnl_pct: -1.42,
  },
  {
    id: 'pos-LLY-20261005',
    ticker: 'LLY',
    status: 'CLOSED',
    entry_date: '2026-10-05',
    entry_price: 890.0,
    shares: 11,
    invested_amount: 9790.0,
    peak_price: 965.0,
    trailing_stop_price: 868.5,
    atr_stop_price: 850.0,
    target_1r: 935.0,
    target_2r: 978.0,
    target_3r: 1020.0,
    current_price: 952.0,
    current_value: 0.0,
    unrealized_pnl_dollars: 0.0,
    unrealized_pnl_pct: 0.0,
    days_held: 18,
    exit_date: '2026-10-23',
    exit_price: 958.0,
    exit_reason: 'RiskGuard: TARGET_2R_HIT',
    realized_pnl_dollars: 748.0,
    realized_pnl_pct: 7.64,
  },
];

const BACKTEST_METRICS = {
  initialCapital: 100000,
  finalEquity: 248620,
  totalReturnPct: 148.6,
  annualizedReturnPct: 35.4,
  totalTrades: 58,
  winRatePct: 65.5,
  profitFactor: 2.24,
  sharpeRatio: 1.88,
  maxDrawdownPct: 10.4,
  avgHoldingDays: 24.2,
  trades: [
    { ticker: 'NVDA', entry: '2025-02-14', exit: '2025-04-10', entryPrice: 104.5, exitPrice: 132.8, pnlPct: 27.1, reason: 'TARGET_3R_HIT' },
    { ticker: 'CRWD', entry: '2025-03-01', exit: '2025-04-18', entryPrice: 280.0, exitPrice: 334.5, pnlPct: 19.5, reason: 'TRAILING_STOP' },
    { ticker: 'SMCI', entry: '2025-01-10', exit: '2025-02-28', entryPrice: 42.0, exitPrice: 58.4, pnlPct: 39.0, reason: 'TARGET_3R_HIT' },
    { ticker: 'MSFT', entry: '2025-05-12', exit: '2025-07-10', entryPrice: 412.0, exitPrice: 436.0, pnlPct: 5.8, reason: 'MAX_HOLDING_DAYS' },
    { ticker: 'AAPL', entry: '2025-06-02', exit: '2025-06-20', entryPrice: 215.0, exitPrice: 204.2, pnlPct: -5.0, reason: 'ATR_STOP' },
    { ticker: 'AMD', entry: '2025-07-15', exit: '2025-08-04', entryPrice: 165.0, exitPrice: 153.5, pnlPct: -7.0, reason: 'MA50_BREAKDOWN' },
    { ticker: 'PLTR', entry: '2025-08-10', exit: '2025-10-15', entryPrice: 28.5, exitPrice: 41.2, pnlPct: 44.6, reason: 'TARGET_3R_HIT' },
  ],
  equityCurve: [
    { month: 'Jan 24', equity: 100000, sp500: 100000 },
    { month: 'Apr 24', equity: 114500, sp500: 105200 },
    { month: 'Jul 24', equity: 132000, sp500: 112000 },
    { month: 'Oct 24', equity: 151200, sp500: 118400 },
    { month: 'Jan 25', equity: 174000, sp500: 124000 },
    { month: 'Apr 25', equity: 198500, sp500: 129500 },
    { month: 'Jul 25', equity: 221000, sp500: 135000 },
    { month: 'Oct 25', equity: 248620, sp500: 141200 },
  ],
};

const CODE_MODULES: Record<string, { filename: string; path: string; desc: string; content: string }> = {
  backtester: {
    filename: 'backtester.py',
    path: 'core/backtester.py',
    desc: 'Historical multi-year simulation engine calculating Win Rate, Sharpe, Max Drawdown & Profit Factor',
    content: `# core/backtester.py (Sprint 5)
class BacktestEngine:
    """Simulates Rising Star Trend strategy across historical price bars."""
    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
        self.indicator_engine = IndicatorEngine()
        self.scoring_engine = ScoringEngine()
        self.risk_guard = RiskGuard(
            trailing_stop_pct=self.config.trailing_stop_pct,
            ma_breakdown_volume_multiplier=self.config.ma_breakdown_vol_mult,
            max_holding_days=self.config.max_holding_days
        )

    def run_portfolio(self, historical_data: Dict[str, pd.DataFrame]) -> BacktestResult:
        # Event-driven daily simulation over multi-year lookback
        # Calculates annualized Sharpe, Max Drawdown, and rolling equity...
        ...`,
  },
  portfoliotracker: {
    filename: 'portfoliotracker.py',
    path: 'core/portfoliotracker.py',
    desc: 'Simulated paper trading book manager with automated RiskGuard audits and JSON persistence',
    content: `# core/portfoliotracker.py (Sprint 5)
class PortfolioTracker:
    """Manages simulated active positions and RiskGuard exits."""
    def open_position(self, ticker: str, entry_price: float, shares: int, risk_plan=None):
        ...
    def audit_positions(self, latest_quotes: Dict[str, Dict[str, Any]]):
        # Checks high/low against Trailing Stop and MA50 Breakdown
        # Automatically closes breached positions...
        ...`,
  },
  github_workflow: {
    filename: 'quant_scan.yml',
    path: '.github/workflows/quant_scan.yml',
    desc: 'GitHub Actions scheduled workflow running nightly at 21:30 UTC post US market close',
    content: `name: Nightly Quant Scan & Risk Audit
on:
  schedule:
    - cron: '30 21 * * 1-5' # 21:30 UTC = 4:30 PM EST post US close
  workflow_dispatch:
jobs:
  quant_scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.10' }
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v
      - run: python main.py --sp500 --equity 100000 --risk-pct 1.0`,
  },
  run_nightly: {
    filename: 'run_nightly_scan.sh',
    path: 'scripts/run_nightly_scan.sh',
    desc: 'Autonomous bash execution script for cloud cron or terminal runners',
    content: `#!/usr/bin/env bash
set -e
echo "Starting Rising Star Nightly Quant Scan..."
python3 -m pytest tests/ -q
python3 main.py --sp500 --equity 100000 --risk-pct 1.0
echo "Scan complete. Generated scan_results.json and portfolio.json"`,
  },
  ruleengine: {
    filename: 'ruleengine.py',
    path: 'core/ruleengine.py',
    desc: 'Stateless formal S&P 500 eligibility evaluator (market cap, exchange, liquidity, GAAP viability)',
    content: `# core/ruleengine.py (Sprint 2 & 4)
class RuleEngine:
    @staticmethod
    def evaluate(profile: CompanyProfile) -> EligibilityResult:
        # 100% formal S&P criteria: US, NYSE/NASDAQ, Market Cap >= $18B, GAAP Net Income > 0
        ...`,
  },
  indicatorengine: {
    filename: 'indicatorengine.py',
    path: 'core/indicatorengine.py',
    desc: '250-bar quantitative mathematics module (MA50 slope, volume surge, 20d/52w breakouts)',
    content: `# core/indicatorengine.py (Sprint 2 & 4)
class IndicatorEngine:
    def calculate(self, ticker: str, close_prices, high_prices, low_prices, volumes):
        # Uses explicit .iloc[] positional indexing eliminating Pandas FutureWarnings
        ...`,
  },
  scoringengine: {
    filename: 'scoringengine.py',
    path: 'core/scoringengine.py',
    desc: '40/30/20/10 multi-factor ranking model with Buy Alert validation and Backtest Gatekeeper',
    content: `# core/scoringengine.py (Sprint 3)
class ScoringEngine:
    def calculate_score(self, indicators, rule_result, short_interest_pct):
        # Computes 0-100 Rising Star Score
        # Signals Buy Alert if Score >= 85 AND breakout_triggered == True
        ...`,
  },
  riskguard: {
    filename: 'riskguard.py',
    path: 'core/riskguard.py',
    desc: 'Dynamic 14-day ATR stops, 1R/2R/3R/5R profit targets, and trailing stop risk management',
    content: `# core/riskguard.py (Sprint 3 & 4)
class RiskGuard:
    def compute_position_sizing(self, ticker, entry_price, highs, lows, closes, account_equity, risk_per_trade_pct):
        # Computes volatility position sizing and multi-tiered profit targets
        ...`,
  },
};

export default function App() {
  const [activeTab, setActiveTab] = useState<'scan' | 'portfolio' | 'backtest' | 'code'>('scan');
  const [searchQuery, setSearchQuery] = useState('');
  const [filterTier, setFilterTier] = useState<string>('ALL');
  const [filterBuyAlertOnly, setFilterBuyAlertOnly] = useState(false);
  const [selectedScanItem, setSelectedScanItem] = useState<ScanItem | null>(null);

  // Paper portfolio state
  const [portfolioPositions, setPortfolioPositions] = useState<PaperPos[]>(INITIAL_PORTFOLIO_POSITIONS);
  const [cashBalance, setCashBalance] = useState<number>(73840.0);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [activeCodeKey, setActiveCodeKey] = useState<string>('backtester');

  // Backtester interactive params
  const [backtestCapital, setBacktestCapital] = useState<number>(100000);
  const [backtestTrailingStop, setBacktestTrailingStop] = useState<number>(10);
  const [backtestMaxHoldingDays, setBacktestMaxHoldingDays] = useState<number>(60);
  const [backtestAtrMultiplier, setBacktestAtrMultiplier] = useState<number>(2.0);
  const [isSimulatingBacktest, setIsSimulatingBacktest] = useState(false);

  // Copy code helper
  const handleCopyCode = (key: string, content: string) => {
    navigator.clipboard.writeText(content);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  // Filter scan items
  const filteredScanItems = useMemo(() => {
    return INITIAL_SCAN_RESULTS.filter((item) => {
      const matchSearch =
        item.ticker.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.tier.toLowerCase().includes(searchQuery.toLowerCase());
      const matchTier = filterTier === 'ALL' || item.tier === filterTier;
      const matchBuyAlert = !filterBuyAlertOnly || item.is_buy_alert;
      return matchSearch && matchTier && matchBuyAlert;
    });
  }, [searchQuery, filterTier, filterBuyAlertOnly]);

  // Portfolio calculations
  const openPositions = useMemo(
    () => portfolioPositions.filter((p) => p.status === 'OPEN'),
    [portfolioPositions]
  );
  const closedPositions = useMemo(
    () => portfolioPositions.filter((p) => p.status === 'CLOSED'),
    [portfolioPositions]
  );
  const investedCapital = useMemo(
    () => openPositions.reduce((acc, p) => acc + p.current_value, 0),
    [openPositions]
  );
  const totalUnrealizedPnl = useMemo(
    () => openPositions.reduce((acc, p) => acc + p.unrealized_pnl_dollars, 0),
    [openPositions]
  );
  const totalRealizedPnl = useMemo(
    () => closedPositions.reduce((acc, p) => acc + (p.realized_pnl_dollars || 0), 0),
    [closedPositions]
  );
  const totalAccountValue = cashBalance + investedCapital;
  const winRate = closedPositions.length
    ? ((closedPositions.filter((p) => (p.realized_pnl_dollars || 0) > 0).length / closedPositions.length) * 100).toFixed(1)
    : '0.0';

  // Interactive Paper Trading: Simulate Risk Audit
  const handleSimulateRiskAudit = () => {
    const updated = portfolioPositions.map((pos) => {
      if (pos.status !== 'OPEN') return pos;
      // random micro market drift
      const drift = (Math.random() - 0.45) * 0.03;
      const newPrice = Math.max(10, +(pos.current_price * (1 + drift)).toFixed(2));
      const newPeak = Math.max(pos.peak_price, newPrice);
      const newTrailing = +(newPeak * 0.9).toFixed(2);
      const newUnrealized = +((newPrice - pos.entry_price) * pos.shares).toFixed(2);
      const newPct = +(((newPrice - pos.entry_price) / pos.entry_price) * 100).toFixed(2);

      // Check if price dipped below trailing stop
      if (newPrice <= pos.trailing_stop_price) {
        return {
          ...pos,
          status: 'CLOSED' as const,
          exit_price: pos.trailing_stop_price,
          exit_date: new Date().toISOString().slice(0, 10),
          exit_reason: 'RiskGuard: TRAILING_STOP',
          realized_pnl_dollars: +((pos.trailing_stop_price - pos.entry_price) * pos.shares).toFixed(2),
          realized_pnl_pct: +(((pos.trailing_stop_price - pos.entry_price) / pos.entry_price) * 100).toFixed(2),
          current_value: 0,
        };
      }

      return {
        ...pos,
        current_price: newPrice,
        peak_price: newPeak,
        trailing_stop_price: newTrailing,
        current_value: +(pos.shares * newPrice).toFixed(2),
        unrealized_pnl_dollars: newUnrealized,
        unrealized_pnl_pct: newPct,
        days_held: pos.days_held + 1,
      };
    });

    setPortfolioPositions(updated);
  };

  // Interactive Paper Trading: Simulate Quick Buy
  const handleQuickPaperBuy = (item: ScanItem) => {
    if (!item.suggested_shares || item.suggested_shares <= 0) return;
    const cost = item.latest_close * item.suggested_shares;
    if (cost > cashBalance) {
      alert(`Insufficient cash balance ($${cashBalance.toFixed(2)}) for order ($${cost.toFixed(2)})`);
      return;
    }

    const newPos: PaperPos = {
      id: `pos-${item.ticker}-${Date.now()}`,
      ticker: item.ticker,
      status: 'OPEN',
      entry_date: new Date().toISOString().slice(0, 10),
      entry_price: item.latest_close,
      shares: item.suggested_shares,
      invested_amount: +cost.toFixed(2),
      peak_price: item.latest_close,
      trailing_stop_price: +(item.latest_close * 0.9).toFixed(2),
      atr_stop_price: item.stop_loss_price,
      target_1r: item.target_1r,
      target_2r: item.target_2r,
      target_3r: item.target_3r,
      current_price: item.latest_close,
      current_value: +cost.toFixed(2),
      unrealized_pnl_dollars: 0,
      unrealized_pnl_pct: 0,
      days_held: 1,
    };

    setCashBalance((prev) => +(prev - cost).toFixed(2));
    setPortfolioPositions((prev) => [newPos, ...prev]);
    setActiveTab('portfolio');
  };

  // Re-run backtest simulation animation
  const handleRunBacktest = () => {
    setIsSimulatingBacktest(true);
    setTimeout(() => {
      setIsSimulatingBacktest(false);
    }, 600);
  };

  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100 font-sans flex flex-col selection:bg-cyan-500/30 selection:text-cyan-200">
      {/* Top Institutional Header */}
      <header className="border-b border-slate-800/80 bg-[#0a0f1d]/90 backdrop-blur sticky top-0 z-40 px-5 py-3">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-gradient-to-tr from-cyan-600 to-emerald-500 shadow-lg shadow-cyan-500/20">
              <TrendingUp className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                  RISING STAR TREND ENGINE
                  <span className="text-xs px-2 py-0.5 rounded font-mono font-medium bg-cyan-950 text-cyan-400 border border-cyan-800/60">
                    SPRINT 5 PRO
                  </span>
                </h1>
              </div>
              <p className="text-xs text-slate-400 font-mono">
                Automated S&P 500 Trend Scanning • Volatility RiskGuard • Backtesting • Paper Portfolio
              </p>
            </div>
          </div>

          {/* System Pulse Badges */}
          <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-slate-300">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Cron: 21:30 UTC</span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-slate-300">
              <Cloud className="w-3.5 h-3.5 text-cyan-400" />
              <span>GitHub Actions Active</span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-slate-300">
              <Shield className="w-3.5 h-3.5 text-emerald-400" />
              <span>RiskGuard 14d ATR</span>
            </div>
          </div>
        </div>
      </header>

      {/* Primary Navigation Tabs */}
      <nav className="border-b border-slate-800/80 bg-[#080d19] px-5">
        <div className="max-w-7xl mx-auto flex gap-1 overflow-x-auto py-2">
          <button
            onClick={() => setActiveTab('scan')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
              activeTab === 'scan'
                ? 'bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            }`}
          >
            <Activity className="w-4 h-4" />
            Market Scanner (S&P 500)
            <span className="ml-1 text-xs px-1.5 py-0.2 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-800/40">
              {INITIAL_SCAN_RESULTS.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('portfolio')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
              activeTab === 'portfolio'
                ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            }`}
          >
            <Briefcase className="w-4 h-4" />
            Paper Portfolio Tracker
            <span className="ml-1 text-xs px-1.5 py-0.2 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800/40">
              {openPositions.length} Open
            </span>
          </button>

          <button
            onClick={() => setActiveTab('backtest')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
              activeTab === 'backtest'
                ? 'bg-amber-500/10 text-amber-300 border border-amber-500/30 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            }`}
          >
            <BarChart3 className="w-4 h-4" />
            Historical Backtesting Lab
            <span className="ml-1 text-xs px-1.5 py-0.2 rounded-full bg-amber-950 text-amber-300 border border-amber-800/40">
              Sharpe 1.88
            </span>
          </button>

          <button
            onClick={() => setActiveTab('code')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
              activeTab === 'code'
                ? 'bg-purple-500/10 text-purple-300 border border-purple-500/30 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            }`}
          >
            <Terminal className="w-4 h-4" />
            Headless Architecture & Cloud Ops
            <span className="ml-1 text-xs px-1.5 py-0.2 rounded-full bg-purple-950 text-purple-300 border border-purple-800/40">
              8 Modules
            </span>
          </button>
        </div>
      </nav>

      {/* Main Content Body */}
      <main className="flex-1 max-w-7xl mx-auto w-full p-4 md:p-6 space-y-6">
        {/* TAB 1: MARKET SCANNER */}
        {activeTab === 'scan' && (
          <div className="space-y-6">
            {/* Top Stat Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 shadow-sm">
                <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
                  <span>UNIVERSE SCANNED</span>
                  <Activity className="w-4 h-4 text-cyan-400" />
                </div>
                <div className="text-2xl font-bold text-white mt-2 font-mono">503 / 503</div>
                <div className="text-xs text-emerald-400 mt-1 flex items-center gap-1 font-mono">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> 489 Qualified S&P 500
                </div>
              </div>

              <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 shadow-sm">
                <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
                  <span>BUY ALERTS GENERATED</span>
                  <Flame className="w-4 h-4 text-amber-400" />
                </div>
                <div className="text-2xl font-bold text-amber-400 mt-2 font-mono">
                  {INITIAL_SCAN_RESULTS.filter((i) => i.is_buy_alert).length} Stocks
                </div>
                <div className="text-xs text-slate-400 mt-1 font-mono">Score ≥ 85.0 & Breakout</div>
              </div>

              <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 shadow-sm">
                <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
                  <span>RISK BUDGET PER TRADE</span>
                  <Shield className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="text-2xl font-bold text-white mt-2 font-mono">$1,000.00</div>
                <div className="text-xs text-slate-400 mt-1 font-mono">1.0% of $100k Account</div>
              </div>

              <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 shadow-sm">
                <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
                  <span>NIGHTLY RUN DURATION</span>
                  <Clock className="w-4 h-4 text-purple-400" />
                </div>
                <div className="text-2xl font-bold text-white mt-2 font-mono">18.4s</div>
                <div className="text-xs text-purple-400 mt-1 font-mono">Async batching (25/batch)</div>
              </div>
            </div>

            {/* Filter and Search Bar */}
            <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 bg-[#0b1220] border border-slate-800 p-3 rounded-xl">
              <div className="flex items-center gap-2 flex-1 relative">
                <Search className="w-4 h-4 text-slate-400 absolute left-3" />
                <input
                  type="text"
                  placeholder="Filter by ticker (NVDA, CRWD) or tier..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={() => setFilterBuyAlertOnly(!filterBuyAlertOnly)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono transition-colors ${
                    filterBuyAlertOnly
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                      : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-slate-200'
                  }`}
                >
                  <Flame className="w-3.5 h-3.5" />
                  Buy Alerts Only
                </button>

                <select
                  value={filterTier}
                  onChange={(e) => setFilterTier(e.target.value)}
                  className="bg-slate-900 border border-slate-800 rounded-lg text-xs font-mono text-slate-300 px-3 py-1.5 focus:outline-none focus:border-cyan-500"
                >
                  <option value="ALL">All Tiers</option>
                  <option value="STRONG_RISING_STAR">Strong Rising Star</option>
                  <option value="EMERGING_CANDIDATE">Emerging Candidate</option>
                  <option value="WATCHLIST_NEUTRAL">Watchlist Neutral</option>
                </select>
              </div>
            </div>

            {/* Scanner Data Table */}
            <div className="bg-[#0b1220] border border-slate-800 rounded-xl overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono border-collapse">
                  <thead>
                    <tr className="bg-slate-900/80 border-b border-slate-800 text-slate-400 uppercase tracking-wider">
                      <th className="py-3 px-4">Ticker</th>
                      <th className="py-3 px-4">Close</th>
                      <th className="py-3 px-4">Score</th>
                      <th className="py-3 px-4">Tier</th>
                      <th className="py-3 px-4">Breakout</th>
                      <th className="py-3 px-4">Vol Ratio</th>
                      <th className="py-3 px-4">14d ATR</th>
                      <th className="py-3 px-4">Stop Loss</th>
                      <th className="py-3 px-4">Position Sizing</th>
                      <th className="py-3 px-4">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {filteredScanItems.map((item) => (
                      <tr
                        key={item.ticker}
                        className="hover:bg-slate-800/30 transition-colors group"
                      >
                        <td className="py-3 px-4 font-bold text-white flex items-center gap-2">
                          <span className="text-cyan-400 font-mono text-sm">{item.ticker}</span>
                          {item.is_buy_alert && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-0.5">
                              <Flame className="w-3 h-3" /> BUY
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-slate-200">${item.latest_close.toFixed(2)}</td>
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            <span
                              className={`font-bold ${
                                item.score >= 85
                                  ? 'text-emerald-400'
                                  : item.score >= 70
                                  ? 'text-cyan-400'
                                  : 'text-slate-400'
                              }`}
                            >
                              {item.score.toFixed(1)}
                            </span>
                            <div className="w-12 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  item.score >= 85
                                    ? 'bg-emerald-400'
                                    : item.score >= 70
                                    ? 'bg-cyan-400'
                                    : 'bg-slate-600'
                                }`}
                                style={{ width: `${item.score}%` }}
                              />
                            </div>
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] border ${
                              item.tier === 'STRONG_RISING_STAR'
                                ? 'bg-emerald-950/60 text-emerald-300 border-emerald-800/60'
                                : item.tier === 'EMERGING_CANDIDATE'
                                ? 'bg-cyan-950/60 text-cyan-300 border-cyan-800/60'
                                : 'bg-slate-900 text-slate-400 border-slate-800'
                            }`}
                          >
                            {item.tier.replace(/_/g, ' ')}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          {item.breakout_triggered ? (
                            <span className="text-emerald-400 flex items-center gap-1 font-semibold">
                              <ArrowUpRight className="w-3.5 h-3.5" />
                              {item.breakout_type}
                            </span>
                          ) : (
                            <span className="text-slate-500">-</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-slate-300">
                          <span
                            className={
                              item.up_down_volume_ratio >= 1.3 ? 'text-emerald-400 font-bold' : ''
                            }
                          >
                            {item.up_down_volume_ratio.toFixed(2)}x
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-300">
                          {item.atr_14 ? `$${item.atr_14.toFixed(2)}` : '-'}
                        </td>
                        <td className="py-3 px-4">
                          {item.stop_loss_price ? (
                            <span className="text-rose-400 font-medium">
                              ${item.stop_loss_price.toFixed(2)}
                            </span>
                          ) : (
                            <span className="text-slate-500">-</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-slate-300">
                          {item.suggested_shares ? (
                            <div>
                              <span className="text-white font-bold">{item.suggested_shares} shs</span>
                              <span className="text-slate-500 ml-1">
                                (~${(item.suggested_shares * item.latest_close).toFixed(0)})
                              </span>
                            </div>
                          ) : (
                            <span className="text-slate-500">-</span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => setSelectedScanItem(item)}
                              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] transition-colors"
                            >
                              Inspect
                            </button>
                            {item.is_buy_alert && (
                              <button
                                onClick={() => handleQuickPaperBuy(item)}
                                className="px-2 py-1 rounded bg-emerald-600/30 hover:bg-emerald-600 text-emerald-300 hover:text-white border border-emerald-500/40 text-[11px] font-bold transition-all flex items-center gap-1"
                              >
                                <PlusCircle className="w-3 h-3" />
                                Paper Buy
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Selected Scan Item Detail Modal/Drawer */}
            {selectedScanItem && (
              <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                <div className="bg-[#0b1220] border border-slate-700 rounded-2xl max-w-2xl w-full p-6 space-y-5 shadow-2xl">
                  <div className="flex items-start justify-between border-b border-slate-800 pb-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-2xl font-bold font-mono text-white">
                          {selectedScanItem.ticker}
                        </h2>
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-mono ${
                            selectedScanItem.is_buy_alert
                              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                              : 'bg-slate-800 text-slate-300'
                          }`}
                        >
                          Score: {selectedScanItem.score.toFixed(1)}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 mt-1 font-mono">
                        S&P 500 Constituent • Evaluated via RuleEngine & IndicatorEngine
                      </p>
                    </div>
                    <button
                      onClick={() => setSelectedScanItem(null)}
                      className="text-slate-400 hover:text-white p-1 rounded-lg bg-slate-900 border border-slate-800"
                    >
                      ✕
                    </button>
                  </div>

                  {/* Quantitative Metrics Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs font-mono">
                    <div className="bg-slate-900 p-3 rounded-lg border border-slate-800">
                      <span className="text-slate-400">Latest Close</span>
                      <div className="text-base font-bold text-white mt-1">
                        ${selectedScanItem.latest_close.toFixed(2)}
                      </div>
                    </div>
                    <div className="bg-slate-900 p-3 rounded-lg border border-slate-800">
                      <span className="text-slate-400">20d Resistance</span>
                      <div className="text-base font-bold text-cyan-400 mt-1">
                        ${selectedScanItem.resistance_20d.toFixed(2)}
                      </div>
                    </div>
                    <div className="bg-slate-900 p-3 rounded-lg border border-slate-800">
                      <span className="text-slate-400">52-Week High</span>
                      <div className="text-base font-bold text-slate-200 mt-1">
                        ${selectedScanItem.high_52w.toFixed(2)}
                      </div>
                    </div>
                    <div className="bg-slate-900 p-3 rounded-lg border border-slate-800">
                      <span className="text-slate-400">50-Day MA</span>
                      <div className="text-base font-bold text-slate-200 mt-1">
                        ${selectedScanItem.ma50.toFixed(2)} (Slope +{selectedScanItem.ma50_slope_20d}%)
                      </div>
                    </div>
                    <div className="bg-slate-900 p-3 rounded-lg border border-slate-800">
                      <span className="text-slate-400">Up/Down Vol Ratio</span>
                      <div className="text-base font-bold text-emerald-400 mt-1">
                        {selectedScanItem.up_down_volume_ratio.toFixed(2)}x
                      </div>
                    </div>
                    <div className="bg-slate-900 p-3 rounded-lg border border-slate-800">
                      <span className="text-slate-400">14-Day ATR</span>
                      <div className="text-base font-bold text-amber-400 mt-1">
                        {selectedScanItem.atr_14 ? `$${selectedScanItem.atr_14.toFixed(2)}` : '-'}
                      </div>
                    </div>
                  </div>

                  {/* RiskGuard Targets Card */}
                  {selectedScanItem.stop_loss_price && (
                    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-3 font-mono text-xs">
                      <div className="flex items-center justify-between text-slate-300 font-bold">
                        <span className="flex items-center gap-1.5 text-emerald-400">
                          <Shield className="w-4 h-4" /> RiskGuard Position Sizing & Targets
                        </span>
                        <span>Max Risk: $1,000 (1%)</span>
                      </div>
                      <div className="grid grid-cols-4 gap-2 text-center">
                        <div className="bg-rose-950/40 border border-rose-800/40 p-2 rounded">
                          <div className="text-slate-400 text-[10px]">Stop Loss (2.0 ATR)</div>
                          <div className="text-rose-400 font-bold mt-0.5">
                            ${selectedScanItem.stop_loss_price.toFixed(2)}
                          </div>
                        </div>
                        <div className="bg-slate-800/60 border border-slate-700/40 p-2 rounded">
                          <div className="text-slate-400 text-[10px]">Target 1R (1:1)</div>
                          <div className="text-slate-200 font-bold mt-0.5">
                            ${selectedScanItem.target_1r?.toFixed(2)}
                          </div>
                        </div>
                        <div className="bg-slate-800/60 border border-slate-700/40 p-2 rounded">
                          <div className="text-slate-400 text-[10px]">Target 2R (1:2)</div>
                          <div className="text-emerald-400 font-bold mt-0.5">
                            ${selectedScanItem.target_2r?.toFixed(2)}
                          </div>
                        </div>
                        <div className="bg-slate-800/60 border border-slate-700/40 p-2 rounded">
                          <div className="text-slate-400 text-[10px]">Target 3R (1:3)</div>
                          <div className="text-emerald-300 font-bold mt-0.5">
                            ${selectedScanItem.target_3r?.toFixed(2)}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                    <button
                      onClick={() => setSelectedScanItem(null)}
                      className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-mono"
                    >
                      Close
                    </button>
                    {selectedScanItem.is_buy_alert && (
                      <button
                        onClick={() => {
                          handleQuickPaperBuy(selectedScanItem);
                          setSelectedScanItem(null);
                        }}
                        className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold flex items-center gap-1.5"
                      >
                        <PlusCircle className="w-4 h-4" />
                        Execute Paper Buy ({selectedScanItem.suggested_shares} Shares)
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: PAPER PORTFOLIO TRACKER */}
        {activeTab === 'portfolio' && (
          <div className="space-y-6">
            {/* Portfolio Summary Header */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 shadow-sm">
                <span className="text-slate-400 text-xs font-mono">TOTAL ACCOUNT VALUE</span>
                <div className="text-2xl font-bold text-white mt-1 font-mono">
                  ${totalAccountValue.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </div>
                <div className="text-xs text-emerald-400 mt-1 font-mono">
                  Initial: $100,000.00 ({(((totalAccountValue - 100000) / 100000) * 100).toFixed(2)}%)
                </div>
              </div>

              <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 shadow-sm">
                <span className="text-slate-400 text-xs font-mono">CASH AVAILABLE</span>
                <div className="text-2xl font-bold text-cyan-400 mt-1 font-mono">
                  ${cashBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </div>
                <div className="text-xs text-slate-400 mt-1 font-mono">
                  Invested: ${investedCapital.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </div>
              </div>

              <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 shadow-sm">
                <span className="text-slate-400 text-xs font-mono">UNREALIZED P&L</span>
                <div
                  className={`text-2xl font-bold mt-1 font-mono ${
                    totalUnrealizedPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {totalUnrealizedPnl >= 0 ? '+' : ''}${totalUnrealizedPnl.toFixed(2)}
                </div>
                <div className="text-xs text-slate-400 mt-1 font-mono">
                  {openPositions.length} active positions open
                </div>
              </div>

              <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 shadow-sm">
                <span className="text-slate-400 text-xs font-mono">REALIZED WIN RATE</span>
                <div className="text-2xl font-bold text-amber-400 mt-1 font-mono">{winRate}%</div>
                <div className="text-xs text-slate-400 mt-1 font-mono">
                  Realized P&L: {totalRealizedPnl >= 0 ? '+' : ''}${totalRealizedPnl.toFixed(2)}
                </div>
              </div>
            </div>

            {/* Audit Action Bar */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[#0b1220] border border-slate-800 p-4 rounded-xl">
              <div>
                <h3 className="text-sm font-bold text-white font-mono flex items-center gap-2">
                  <Shield className="w-4 h-4 text-emerald-400" />
                  RiskGuard Autonomous Surveillance Active
                </h3>
                <p className="text-xs text-slate-400 font-mono mt-0.5">
                  Positions are continuously evaluated against -10% trailing stops, ATR breaches, and 60-day limits.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={handleSimulateRiskAudit}
                  className="px-3.5 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-mono font-bold flex items-center gap-2 shadow-sm transition-all"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Run Live Risk Audit
                </button>
              </div>
            </div>

            {/* Active Open Positions Table */}
            <div className="bg-[#0b1220] border border-slate-800 rounded-xl overflow-hidden shadow-sm space-y-2">
              <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                <h3 className="text-sm font-bold text-white font-mono flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
                  Active Simulated Positions ({openPositions.length})
                </h3>
                <span className="text-xs text-slate-400 font-mono">Trailing Stop Buffer: 10.0%</span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono border-collapse">
                  <thead>
                    <tr className="bg-slate-900/80 border-b border-slate-800 text-slate-400 uppercase">
                      <th className="py-3 px-4">Ticker</th>
                      <th className="py-3 px-4">Entry Date</th>
                      <th className="py-3 px-4">Entry / Current</th>
                      <th className="py-3 px-4">Shares</th>
                      <th className="py-3 px-4">Peak High</th>
                      <th className="py-3 px-4">Trailing Stop</th>
                      <th className="py-3 px-4">Unrealized P&L</th>
                      <th className="py-3 px-4">Days Held</th>
                      <th className="py-3 px-4">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {openPositions.length === 0 ? (
                      <tr>
                        <td colSpan={9} className="py-6 text-center text-slate-500">
                          No open paper positions. Generate buy alerts from the Market Scanner tab.
                        </td>
                      </tr>
                    ) : (
                      openPositions.map((pos) => (
                        <tr key={pos.id} className="hover:bg-slate-800/30">
                          <td className="py-3 px-4 font-bold text-cyan-400 text-sm">{pos.ticker}</td>
                          <td className="py-3 px-4 text-slate-400">{pos.entry_date}</td>
                          <td className="py-3 px-4 text-slate-200">
                            ${pos.entry_price.toFixed(2)} →{' '}
                            <span className="font-bold text-white">${pos.current_price.toFixed(2)}</span>
                          </td>
                          <td className="py-3 px-4 text-slate-300">
                            {pos.shares} shs (${pos.current_value.toFixed(0)})
                          </td>
                          <td className="py-3 px-4 text-emerald-400 font-medium">
                            ${pos.peak_price.toFixed(2)}
                          </td>
                          <td className="py-3 px-4 text-rose-400 font-medium">
                            ${pos.trailing_stop_price.toFixed(2)}
                          </td>
                          <td className="py-3 px-4">
                            <span
                              className={`font-bold ${
                                pos.unrealized_pnl_dollars >= 0
                                  ? 'text-emerald-400'
                                  : 'text-rose-400'
                              }`}
                            >
                              {pos.unrealized_pnl_dollars >= 0 ? '+' : ''}$
                              {pos.unrealized_pnl_dollars.toFixed(2)} ({pos.unrealized_pnl_pct >= 0 ? '+' : ''}
                              {pos.unrealized_pnl_pct}%)
                            </span>
                          </td>
                          <td className="py-3 px-4 text-slate-300">{pos.days_held}d / 60d</td>
                          <td className="py-3 px-4">
                            <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800/60 font-semibold">
                              TRACKING
                            </span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Closed Positions History */}
            <div className="bg-[#0b1220] border border-slate-800 rounded-xl overflow-hidden shadow-sm">
              <div className="p-4 border-b border-slate-800">
                <h3 className="text-sm font-bold text-white font-mono flex items-center gap-2">
                  <Check className="w-4 h-4 text-cyan-400" />
                  Closed Historical Trades ({closedPositions.length})
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono border-collapse">
                  <thead>
                    <tr className="bg-slate-900/80 border-b border-slate-800 text-slate-400 uppercase">
                      <th className="py-3 px-4">Ticker</th>
                      <th className="py-3 px-4">Entry</th>
                      <th className="py-3 px-4">Exit Date</th>
                      <th className="py-3 px-4">Exit Price</th>
                      <th className="py-3 px-4">Exit Reason</th>
                      <th className="py-3 px-4">Realized P&L</th>
                      <th className="py-3 px-4">Holding Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {closedPositions.map((pos) => (
                      <tr key={pos.id} className="hover:bg-slate-800/30">
                        <td className="py-3 px-4 font-bold text-white">{pos.ticker}</td>
                        <td className="py-3 px-4 text-slate-400">${pos.entry_price.toFixed(2)}</td>
                        <td className="py-3 px-4 text-slate-400">{pos.exit_date}</td>
                        <td className="py-3 px-4 text-slate-200">${pos.exit_price?.toFixed(2)}</td>
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded text-[10px] bg-slate-900 border border-slate-800 text-amber-300">
                            {pos.exit_reason}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`font-bold ${
                              (pos.realized_pnl_dollars || 0) >= 0
                                ? 'text-emerald-400'
                                : 'text-rose-400'
                            }`}
                          >
                            {(pos.realized_pnl_dollars || 0) >= 0 ? '+' : ''}$
                            {pos.realized_pnl_dollars?.toFixed(2)} (
                            {(pos.realized_pnl_pct || 0) >= 0 ? '+' : ''}
                            {pos.realized_pnl_pct}%)
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-400">{pos.days_held} days</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: BACKTESTING LAB */}
        {activeTab === 'backtest' && (
          <div className="space-y-6">
            {/* Top KPI Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
              <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-3.5 shadow-sm">
                <span className="text-slate-400 text-[11px] font-mono">TOTAL RETURN</span>
                <div className="text-xl font-bold text-emerald-400 mt-1 font-mono">
                  +{BACKTEST_METRICS.totalReturnPct}%
                </div>
                <div className="text-[10px] text-slate-400 font-mono">Ann: +{BACKTEST_METRICS.annualizedReturnPct}%</div>
              </div>

              <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-3.5 shadow-sm">
                <span className="text-slate-400 text-[11px] font-mono">WIN RATE</span>
                <div className="text-xl font-bold text-cyan-400 mt-1 font-mono">
                  {BACKTEST_METRICS.winRatePct}%
                </div>
                <div className="text-[10px] text-slate-400 font-mono">{BACKTEST_METRICS.totalTrades} Closed Trades</div>
              </div>

              <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-3.5 shadow-sm">
                <span className="text-slate-400 text-[11px] font-mono">PROFIT FACTOR</span>
                <div className="text-xl font-bold text-amber-400 mt-1 font-mono">
                  {BACKTEST_METRICS.profitFactor}x
                </div>
                <div className="text-[10px] text-slate-400 font-mono">Gross Gain / Loss</div>
              </div>

              <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-3.5 shadow-sm">
                <span className="text-slate-400 text-[11px] font-mono">ANNUALIZED SHARPE</span>
                <div className="text-xl font-bold text-purple-400 mt-1 font-mono">
                  {BACKTEST_METRICS.sharpeRatio}
                </div>
                <div className="text-[10px] text-slate-400 font-mono">Risk-Adjusted</div>
              </div>

              <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-3.5 shadow-sm">
                <span className="text-slate-400 text-[11px] font-mono">MAX DRAWDOWN</span>
                <div className="text-xl font-bold text-rose-400 mt-1 font-mono">
                  -{BACKTEST_METRICS.maxDrawdownPct}%
                </div>
                <div className="text-[10px] text-slate-400 font-mono">Peak-to-Trough</div>
              </div>

              <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-3.5 shadow-sm">
                <span className="text-slate-400 text-[11px] font-mono">AVG HOLDING TIME</span>
                <div className="text-xl font-bold text-white mt-1 font-mono">
                  {BACKTEST_METRICS.avgHoldingDays}d
                </div>
                <div className="text-[10px] text-slate-400 font-mono">Max limit: 60d</div>
              </div>
            </div>

            {/* Strategy Equity Curve Chart (SVG) */}
            <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                <div>
                  <h3 className="text-sm font-bold text-white font-mono flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-emerald-400" />
                    Strategy Cumulative Equity Curve vs S&P 500 Benchmark (2024–2026)
                  </h3>
                  <p className="text-xs text-slate-400 font-mono mt-0.5">
                    Starting Capital: $100,000 • S&P 500 Eligible Equities • 14d ATR & Trailing Stop Exit Rules
                  </p>
                </div>
                <div className="flex items-center gap-4 text-xs font-mono">
                  <div className="flex items-center gap-1.5 text-emerald-400">
                    <span className="w-3 h-1 bg-emerald-400 rounded-full" />
                    Rising Star Engine (+148.6%)
                  </div>
                  <div className="flex items-center gap-1.5 text-slate-400">
                    <span className="w-3 h-1 bg-slate-500 rounded-full" />
                    S&P 500 Index (+41.2%)
                  </div>
                </div>
              </div>

              {/* Chart Visualizer */}
              <div className="h-64 w-full relative flex items-end pt-4 pb-6 px-2">
                <svg className="w-full h-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 700 200">
                  <defs>
                    <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#10b981" stopOpacity="0.3" />
                      <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
                    </linearGradient>
                  </defs>

                  {/* Horizontal Gridlines */}
                  <line x1="0" y1="0" x2="700" y2="0" stroke="#1e293b" strokeDasharray="3 3" />
                  <line x1="0" y1="50" x2="700" y2="50" stroke="#1e293b" strokeDasharray="3 3" />
                  <line x1="0" y1="100" x2="700" y2="100" stroke="#1e293b" strokeDasharray="3 3" />
                  <line x1="0" y1="150" x2="700" y2="150" stroke="#1e293b" strokeDasharray="3 3" />
                  <line x1="0" y1="200" x2="700" y2="200" stroke="#334155" />

                  {/* Benchmark S&P 500 Line (Gray) */}
                  <polyline
                    fill="none"
                    stroke="#64748b"
                    strokeWidth="2"
                    points="0,200 100,192 200,183 300,174 400,165 500,157 600,150 700,140"
                  />

                  {/* Strategy Area Fill */}
                  <polygon
                    fill="url(#equityGrad)"
                    points="0,200 0,200 100,178 200,154 300,128 400,98 500,66 600,34 700,5 700,200"
                  />

                  {/* Strategy Curve Line (Emerald) */}
                  <polyline
                    fill="none"
                    stroke="#10b981"
                    strokeWidth="3"
                    points="0,200 100,178 200,154 300,128 400,98 500,66 600,34 700,5"
                  />

                  {/* Nodes */}
                  {[
                    [0, 200],
                    [100, 178],
                    [200, 154],
                    [300, 128],
                    [400, 98],
                    [500, 66],
                    [600, 34],
                    [700, 5],
                  ].map(([x, y], idx) => (
                    <circle key={idx} cx={x} cy={y} r="4" fill="#070b12" stroke="#10b981" strokeWidth="2" />
                  ))}
                </svg>
              </div>

              {/* X-Axis Labels */}
              <div className="flex justify-between text-[11px] font-mono text-slate-400 px-1 pt-1 border-t border-slate-800">
                {BACKTEST_METRICS.equityCurve.map((pt, i) => (
                  <span key={i}>{pt.month}</span>
                ))}
              </div>
            </div>

            {/* Interactive Simulation Parameter Tuning */}
            <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <h3 className="text-sm font-bold text-white font-mono flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-cyan-400" />
                  Quantitative Parameter Optimization Console
                </h3>
                <button
                  onClick={handleRunBacktest}
                  disabled={isSimulatingBacktest}
                  className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold flex items-center gap-2 transition-all disabled:opacity-50"
                >
                  <Play className={`w-3.5 h-3.5 ${isSimulatingBacktest ? 'animate-spin' : ''}`} />
                  {isSimulatingBacktest ? 'Simulating...' : 'Re-Run Backtest'}
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs font-mono">
                <div>
                  <label className="text-slate-400 block mb-1">
                    Initial Capital: ${backtestCapital.toLocaleString()}
                  </label>
                  <input
                    type="range"
                    min="25000"
                    max="500000"
                    step="25000"
                    value={backtestCapital}
                    onChange={(e) => setBacktestCapital(+e.target.value)}
                    className="w-full accent-cyan-500 cursor-pointer"
                  />
                </div>

                <div>
                  <label className="text-slate-400 block mb-1">
                    Trailing Stop: {backtestTrailingStop}% from Peak
                  </label>
                  <input
                    type="range"
                    min="5"
                    max="20"
                    step="1"
                    value={backtestTrailingStop}
                    onChange={(e) => setBacktestTrailingStop(+e.target.value)}
                    className="w-full accent-cyan-500 cursor-pointer"
                  />
                </div>

                <div>
                  <label className="text-slate-400 block mb-1">
                    14d ATR Multiplier: {backtestAtrMultiplier.toFixed(1)}x
                  </label>
                  <input
                    type="range"
                    min="1.0"
                    max="4.0"
                    step="0.5"
                    value={backtestAtrMultiplier}
                    onChange={(e) => setBacktestAtrMultiplier(+e.target.value)}
                    className="w-full accent-cyan-500 cursor-pointer"
                  />
                </div>

                <div>
                  <label className="text-slate-400 block mb-1">
                    Max Holding Days: {backtestMaxHoldingDays} Days
                  </label>
                  <input
                    type="range"
                    min="20"
                    max="120"
                    step="5"
                    value={backtestMaxHoldingDays}
                    onChange={(e) => setBacktestMaxHoldingDays(+e.target.value)}
                    className="w-full accent-cyan-500 cursor-pointer"
                  />
                </div>
              </div>
            </div>

            {/* Backtest Sample Trade Log */}
            <div className="bg-[#0b1220] border border-slate-800 rounded-xl overflow-hidden shadow-sm">
              <div className="p-4 border-b border-slate-800">
                <h3 className="text-sm font-bold text-white font-mono flex items-center gap-2">
                  <Activity className="w-4 h-4 text-amber-400" />
                  Historical Trade Log (Sample Signals)
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono border-collapse">
                  <thead>
                    <tr className="bg-slate-900/80 border-b border-slate-800 text-slate-400 uppercase">
                      <th className="py-3 px-4">Ticker</th>
                      <th className="py-3 px-4">Entry Date</th>
                      <th className="py-3 px-4">Entry Price</th>
                      <th className="py-3 px-4">Exit Date</th>
                      <th className="py-3 px-4">Exit Price</th>
                      <th className="py-3 px-4">Exit Reason</th>
                      <th className="py-3 px-4">P&L %</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {BACKTEST_METRICS.trades.map((t, idx) => (
                      <tr key={idx} className="hover:bg-slate-800/30">
                        <td className="py-3 px-4 font-bold text-cyan-400">{t.ticker}</td>
                        <td className="py-3 px-4 text-slate-400">{t.entry}</td>
                        <td className="py-3 px-4 text-slate-200">${t.entryPrice.toFixed(2)}</td>
                        <td className="py-3 px-4 text-slate-400">{t.exit}</td>
                        <td className="py-3 px-4 text-slate-200">${t.exitPrice.toFixed(2)}</td>
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded text-[10px] bg-slate-900 border border-slate-800 text-amber-300">
                            {t.reason}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`font-bold ${
                              t.pnlPct >= 0 ? 'text-emerald-400' : 'text-rose-400'
                            }`}
                          >
                            {t.pnlPct >= 0 ? '+' : ''}
                            {t.pnlPct}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: HEADLESS ARCHITECTURE & CLOUD OPS */}
        {activeTab === 'code' && (
          <div className="space-y-6">
            {/* Architectural Overview */}
            <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
              <div>
                <h3 className="text-sm font-bold text-white font-mono flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-purple-400" />
                  Headless Micro-Module Architecture & Execution Engine
                </h3>
                <p className="text-xs text-slate-400 font-mono mt-1">
                  100% headless, pure Python backend modules designed for independent testability and automated GitHub Actions orchestration.
                </p>
              </div>

              {/* Module Selector Chips */}
              <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-800">
                {Object.entries(CODE_MODULES).map(([key, item]) => (
                  <button
                    key={key}
                    onClick={() => setActiveCodeKey(key)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono transition-colors ${
                      activeCodeKey === key
                        ? 'bg-purple-600/20 text-purple-300 border border-purple-500/50 shadow-sm'
                        : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-slate-200'
                    }`}
                  >
                    <FileCode className="w-3.5 h-3.5" />
                    {item.filename}
                  </button>
                ))}
              </div>
            </div>

            {/* Code Viewer Panel */}
            <div className="bg-[#090d16] border border-slate-800 rounded-xl overflow-hidden shadow-sm">
              <div className="bg-slate-900/90 border-b border-slate-800 px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-2 font-mono text-xs">
                  <Terminal className="w-4 h-4 text-purple-400" />
                  <span className="text-white font-bold">{CODE_MODULES[activeCodeKey].path}</span>
                  <span className="text-slate-500 hidden sm:inline">— {CODE_MODULES[activeCodeKey].desc}</span>
                </div>
                <button
                  onClick={() =>
                    handleCopyCode(activeCodeKey, CODE_MODULES[activeCodeKey].content)
                  }
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-mono transition-colors"
                >
                  {copiedKey === activeCodeKey ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>Copy</span>
                    </>
                  )}
                </button>
              </div>

              <div className="p-4 overflow-x-auto text-xs font-mono leading-relaxed bg-[#060910]">
                <pre className="text-slate-300">
                  <code>{CODE_MODULES[activeCodeKey].content}</code>
                </pre>
              </div>
            </div>

            {/* CLI & Cloud Automation Instructions */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 space-y-3 font-mono text-xs">
                <div className="flex items-center gap-2 text-cyan-400 font-bold">
                  <Terminal className="w-4 h-4" /> Standalone CLI Execution
                </div>
                <div className="bg-slate-950 p-3 rounded border border-slate-800 text-slate-300 space-y-1">
                  <p className="text-slate-500"># Run full S&P 500 nightly scan with RiskGuard & Paper Portfolio</p>
                  <p className="text-emerald-400">python main.py --sp500 --equity 100000 --risk-pct 1.0</p>
                  <p className="text-slate-500 pt-2"># Run 5-year historical backtest</p>
                  <p className="text-cyan-400">python backtest.py --tickers NVDA CRWD PLTR --capital 100000</p>
                  <p className="text-slate-500 pt-2"># Execute unit test suite</p>
                  <p className="text-purple-400">pytest tests/ -v</p>
                </div>
              </div>

              <div className="bg-[#0b1220] border border-slate-800 rounded-xl p-4 space-y-3 font-mono text-xs">
                <div className="flex items-center gap-2 text-emerald-400 font-bold">
                  <Cloud className="w-4 h-4" /> Cloud Automation (GitHub Actions)
                </div>
                <div className="bg-slate-950 p-3 rounded border border-slate-800 text-slate-300 space-y-1">
                  <p className="text-slate-500"># Triggers nightly after US close (21:30 UTC):</p>
                  <p className="text-slate-300">1. Checkout & Ubuntu Python 3.10 setup</p>
                  <p className="text-slate-300">2. TA-Lib C-Library & dependencies install</p>
                  <p className="text-slate-300">3. Runs unit test suite (`pytest tests/`)</p>
                  <p className="text-slate-300">4. Executes batch scanner across S&P 500</p>
                  <p className="text-slate-300">5. Dispatches Telegram alerts & saves artifacts</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-[#080d19] py-4 px-6 text-center text-xs font-mono text-slate-500">
        Rising Star Trend Engine • Pure Headless Micro-Module Architecture • Pydantic v2 • Pandas • TA-Lib
      </footer>
    </div>
  );
}
