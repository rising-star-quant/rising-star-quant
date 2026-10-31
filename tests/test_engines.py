"""
Unit tests for Rising Star Trend Engine - Sprint 2: Atomic Engines.
Covers 100% of S&P 500 RuleEngine criteria and quantitative IndicatorEngine mathematics.
"""

from datetime import datetime
import pytest

from core.ruleengine import (
    CompanyProfile,
    EligibilityResult,
    RuleEngine,
    build_profile_from_market_data,
    compute_annual_dollar_volume,
    normalize_exchange_code,
)
from core.indicatorengine import IndicatorEngine, IndicatorMetrics, TechnicalTrend, VolumeMetrics


# =====================================================================
# Fixtures for RuleEngine
# =====================================================================

@pytest.fixture
def qualifying_company_profile() -> CompanyProfile:
    """Mock company profile passing 100% of formal S&P 500 inclusion rules."""
    return CompanyProfile(
        ticker="PLTR",
        country="US",
        exchange="NASDAQ",
        market_cap=98_000_000_000.0,       # $98B >> $18B
        shares_outstanding=2_200_000_000.0,
        float_shares=1_760_000_000.0,       # 80% float >> 50%
        public_float_pct=0.80,
        annual_dollar_volume=120_000_000_000.0, # Liquidity ratio = 120 / (98 * 0.8) = 1.53 > 1.0
        avg_daily_volume_shares=45_000_000.0,
        latest_price=44.50,
        net_income_ttm=404_000_000.0,       # Positive GAAP TTM
        net_income_mrq=134_000_000.0,       # Positive GAAP MRQ
    )


# =====================================================================
# Test Suite 1: RuleEngine (Formal S&P 500 Criteria)
# =====================================================================

class TestRuleEngine:
    def test_sp500_full_eligibility_pass(self, qualifying_company_profile):
        engine = RuleEngine()
        result = engine.evaluate(qualifying_company_profile)

        assert isinstance(result, EligibilityResult)
        assert result.is_eligible is True
        assert len(result.failed_criteria) == 0
        assert result.criteria_checklist["us_incorporation"] is True
        assert result.criteria_checklist["eligible_exchange"] is True
        assert result.criteria_checklist["market_cap_threshold"] is True
        assert result.criteria_checklist["public_float_minimum"] is True
        assert result.criteria_checklist["liquidity_ratio_threshold"] is True
        assert result.criteria_checklist["gaap_ttm_positive"] is True
        assert result.criteria_checklist["gaap_mrq_positive"] is True

    def test_non_us_incorporation_fails(self, qualifying_company_profile):
        # Change country to Ireland / Cayman Islands
        foreign_company = CompanyProfile(
            ticker="CRH",
            country="IE", # Ireland
            exchange="NYSE",
            market_cap=60_000_000_000.0,
            public_float_pct=0.85,
            annual_dollar_volume=80_000_000_000.0,
            net_income_ttm=3_000_000_000.0,
            net_income_mrq=800_000_000.0,
        )
        engine = RuleEngine()
        res = engine.evaluate(foreign_company)

        assert res.is_eligible is False
        assert res.criteria_checklist["us_incorporation"] is False
        assert any("U.S. Incorporation" in f for f in res.failed_criteria)

    def test_ineligible_exchange_fails(self, qualifying_company_profile):
        # Primary listing on Pink Sheets / OTC / TSX
        otc_company = CompanyProfile(
            ticker="OTCPK",
            country="US",
            exchange="OTC_MARKETS",
            market_cap=25_000_000_000.0,
            public_float_pct=0.70,
            annual_dollar_volume=30_000_000_000.0,
            net_income_ttm=500_000_000.0,
            net_income_mrq=120_000_000.0,
        )
        engine = RuleEngine()
        res = engine.evaluate(otc_company)

        assert res.is_eligible is False
        assert res.criteria_checklist["eligible_exchange"] is False
        assert any("Primary Exchange" in f for f in res.failed_criteria)

    def test_market_cap_under_18b_fails(self, qualifying_company_profile):
        small_cap = CompanyProfile(
            ticker="MIDCAP",
            country="US",
            exchange="NASDAQ",
            market_cap=15_500_000_000.0, # $15.5B < $18.0B threshold
            public_float_pct=0.75,
            annual_dollar_volume=20_000_000_000.0,
            net_income_ttm=400_000_000.0,
            net_income_mrq=100_000_000.0,
        )
        engine = RuleEngine(min_market_cap=18_000_000_000.0)
        res = engine.evaluate(small_cap)

        assert res.is_eligible is False
        assert res.criteria_checklist["market_cap_threshold"] is False
        assert any("Market Capitalization" in f for f in res.failed_criteria)

    def test_public_float_under_50pct_fails(self, qualifying_company_profile):
        tight_float = CompanyProfile(
            ticker="INSIDER",
            country="US",
            exchange="NYSE",
            market_cap=30_000_000_000.0,
            public_float_pct=0.35, # 35% float < 50%
            annual_dollar_volume=35_000_000_000.0,
            net_income_ttm=600_000_000.0,
            net_income_mrq=150_000_000.0,
        )
        engine = RuleEngine()
        res = engine.evaluate(tight_float)

        assert res.is_eligible is False
        assert res.criteria_checklist["public_float_minimum"] is False
        assert any("Public Float" in f for f in res.failed_criteria)

    def test_liquidity_ratio_under_1_fails(self):
        # Annual volume $10B on $20B float cap -> ratio = 0.5 <= 1.0
        illiquid_stock = CompanyProfile(
            ticker="STALE",
            country="US",
            exchange="NYSE",
            market_cap=25_000_000_000.0,
            public_float_pct=0.80, # Float cap = $20B
            annual_dollar_volume=10_000_000_000.0, # $10B / $20B = 0.5
            net_income_ttm=500_000_000.0,
            net_income_mrq=120_000_000.0,
        )
        engine = RuleEngine()
        res = engine.evaluate(illiquid_stock)

        assert res.is_eligible is False
        assert res.criteria_checklist["liquidity_ratio_threshold"] is False
        assert any("Float-Adjusted Liquidity Ratio" in f for f in res.failed_criteria)

    def test_negative_ttm_net_income_fails(self, qualifying_company_profile):
        unprofitable_ttm = CompanyProfile(
            ticker="BURN",
            country="US",
            exchange="NASDAQ",
            market_cap=22_000_000_000.0,
            public_float_pct=0.60,
            annual_dollar_volume=30_000_000_000.0,
            net_income_ttm=-150_000_000.0, # Negative TTM
            net_income_mrq=20_000_000.0,   # Positive MRQ
        )
        engine = RuleEngine()
        res = engine.evaluate(unprofitable_ttm)

        assert res.is_eligible is False
        assert res.criteria_checklist["gaap_ttm_positive"] is False
        assert any("GAAP TTM Net Income" in f for f in res.failed_criteria)

    def test_negative_mrq_net_income_fails(self):
        unprofitable_mrq = CompanyProfile(
            ticker="DIP",
            country="US",
            exchange="NYSE",
            market_cap=24_000_000_000.0,
            public_float_pct=0.70,
            annual_dollar_volume=35_000_000_000.0,
            net_income_ttm=300_000_000.0,  # Positive TTM
            net_income_mrq=-45_000_000.0,  # Negative MRQ
        )
        engine = RuleEngine()
        res = engine.evaluate(unprofitable_mrq)

        assert res.is_eligible is False
        assert res.criteria_checklist["gaap_mrq_positive"] is False
        assert any("Most Recent Quarter" in f for f in res.failed_criteria)

    def test_yahoo_exchange_codes_standardized_to_nasdaq_and_nyse(self):
        # Yahoo Finance returns codes like NMS, NGM, NCM, and NYQ
        engine = RuleEngine()
        for yf_code, expected_mapped in [("NMS", "NASDAQ"), ("NGM", "NASDAQ"), ("NCM", "NASDAQ"), ("NYQ", "NYSE")]:
            profile = CompanyProfile(
                ticker="TEST",
                country="US",
                exchange=yf_code,
                market_cap=25_000_000_000.0,
                public_float_pct=0.75,
                annual_dollar_volume=30_000_000_000.0,
                net_income_ttm=500_000_000.0,
                net_income_mrq=120_000_000.0,
            )
            assert profile.exchange == expected_mapped
            res = engine.evaluate(profile)
            assert res.criteria_checklist["eligible_exchange"] is True
            assert res.is_eligible is True

    def test_public_float_pct_normalization(self):
        # Given a float passed as percentage (e.g. 75.0 instead of 0.75)
        p1 = CompanyProfile(
            ticker="FLOAT75",
            country="US",
            exchange="NASDAQ",
            market_cap=20_000_000_000.0,
            public_float_pct=75.0,  # 75% passed as 75.0
            annual_dollar_volume=25_000_000_000.0,
            net_income_ttm=100_000_000.0,
            net_income_mrq=25_000_000.0,
        )
        assert p1.public_float_pct == 0.75
        assert p1.public_float_pct <= 1.0

        p2 = CompanyProfile(
            ticker="FLOAT_RATIO",
            country="US",
            exchange="NYSE",
            market_cap=20_000_000_000.0,
            public_float_pct=0.68,
            annual_dollar_volume=25_000_000_000.0,
            net_income_ttm=100_000_000.0,
            net_income_mrq=25_000_000.0,
        )
        assert p2.public_float_pct == 0.68

    def test_automated_annual_dollar_volume_calculation(self):
        # 252 bars with price=100.0 and volume=1,000,000 => daily dollar volume = 100M
        # Annual dollar volume = 252 * 100M = 25,200,000,000
        closes = [100.0] * 252
        volumes = [1_000_000] * 252

        dollar_vol = compute_annual_dollar_volume(closes, volumes, lookback_bars=252)
        expected = 252 * 100.0 * 1_000_000.0
        assert dollar_vol == expected

        # Test build_profile_from_market_data factory helper
        profile = build_profile_from_market_data(
            ticker="AUTODOL",
            market_cap=20_000_000_000.0,
            net_income_ttm=200_000_000.0,
            net_income_mrq=50_000_000.0,
            exchange="NMS", # Yahoo code
            public_float_pct=80.0, # Percentage input
            closes=closes,
            volumes=volumes,
            latest_price=100.0,
        )
        assert profile.exchange == "NASDAQ"
        assert profile.public_float_pct == 0.80
        assert profile.annual_dollar_volume == expected

        engine = RuleEngine()
        res = engine.evaluate(profile)
        assert res.is_eligible is True
        assert res.criteria_checklist["liquidity_ratio_threshold"] is True



# =====================================================================
# Fixtures for IndicatorEngine (250 daily bars)
# =====================================================================

@pytest.fixture
def series_250_bars():
    """Generates 250 daily bars with trend alignment and institutional volume accumulation."""
    closes = []
    highs = []
    lows = []
    volumes = []

    base_price = 100.0
    for i in range(250):
        # General uptrend from 100 to 220
        c = base_price + (i * 0.48) + ((i % 5) * 0.3)
        h = c + 1.5
        l = c - 1.5
        closes.append(round(c, 2))
        highs.append(round(h, 2))
        lows.append(round(l, 2))

        # On up-days (when i%2 == 0 or overall trend), assign heavy volume
        if i > 0 and closes[i] > closes[i - 1]:
            volumes.append(2_000_000 + (i * 5_000)) # Heavy volume on up days
        else:
            volumes.append(1_200_000) # Lighter volume on pullbacks

    return {
        "closes": closes,
        "highs": highs,
        "lows": lows,
        "volumes": volumes,
    }


# =====================================================================
# Test Suite 2: IndicatorEngine (Quantitative Mathematics)
# =====================================================================

class TestIndicatorEngine:
    def test_indicator_250_bars_trend_aligned(self, series_250_bars):
        engine = IndicatorEngine()
        metrics = engine.calculate(
            ticker="NVDA",
            closes=series_250_bars["closes"],
            highs=series_250_bars["highs"],
            lows=series_250_bars["lows"],
            volumes=series_250_bars["volumes"],
        )

        assert isinstance(metrics, IndicatorMetrics)
        assert metrics.ticker == "NVDA"
        assert metrics.bars_processed == 250

        # Technical trend checks
        trend = metrics.technical_trend
        assert trend.ma50 > 0
        assert trend.ma200 is not None and trend.ma200 > 0
        assert trend.is_above_ma50 is True
        assert trend.is_above_ma200 is True
        assert trend.ma50_slope_20d > 0 # Slope should be positive in an uptrend
        assert trend.is_trend_aligned is True

    def test_institutional_volume_accumulation_surge_30pct(self, series_250_bars):
        engine = IndicatorEngine(accumulation_threshold=1.30)
        metrics = engine.calculate(
            ticker="NVDA",
            closes=series_250_bars["closes"],
            highs=series_250_bars["highs"],
            lows=series_250_bars["lows"],
            volumes=series_250_bars["volumes"],
        )

        vol = metrics.volume_metrics
        assert vol.up_day_avg_volume > vol.down_day_avg_volume
        assert vol.up_down_volume_ratio >= 1.30
        assert vol.institutional_accumulation is True

    def test_no_volume_accumulation_ratio_under_threshold(self):
        # Generate series where down days have heavier volume than up days
        closes = [100.0 + (i * 0.1) for i in range(50)]
        highs = [c + 1.0 for c in closes]
        lows = [c - 1.0 for c in closes]
        volumes = []
        for i in range(50):
            if i % 2 == 0:
                closes[i] = closes[i - 1] + 0.5 if i > 0 else 100.0
                volumes.append(800_000) # Low volume on up day
            else:
                closes[i] = closes[i - 1] - 0.2
                volumes.append(1_600_000) # Heavy volume on down day

        engine = IndicatorEngine(accumulation_threshold=1.30)
        metrics = engine.calculate("DISTRIBUTION_STOCK", closes, highs, lows, volumes)

        assert metrics.volume_metrics.institutional_accumulation is False
        assert metrics.volume_metrics.up_down_volume_ratio < 1.30

    def test_20d_resistance_breakout_trigger(self, series_250_bars):
        # Create a clean breakout: latest close exceeds highest high of prior 20 bars
        highs = list(series_250_bars["highs"])
        closes = list(series_250_bars["closes"])

        # Prior 20 highs peak at 215.0
        for i in range(230, 249):
            highs[i] = 215.0

        # Latest bar breaks through to 218.0
        closes[-1] = 218.0
        highs[-1] = 219.0

        engine = IndicatorEngine()
        metrics = engine.calculate(
            "BREAKOUT",
            closes=closes,
            highs=highs,
            lows=series_250_bars["lows"],
            volumes=series_250_bars["volumes"],
        )

        assert metrics.breakout_triggered is True
        assert metrics.latest_close >= metrics.resistance_20d
        assert metrics.distance_to_resistance_pct >= 0.0

    def test_52w_high_breakout_trigger(self, series_250_bars):
        closes = list(series_250_bars["closes"])
        highs = list(series_250_bars["highs"])

        # Make current close equal to historical maximum high
        max_h = max(highs)
        closes[-1] = max_h

        engine = IndicatorEngine()
        metrics = engine.calculate(
            "ALL_TIME_HIGH",
            closes=closes,
            highs=highs,
            lows=series_250_bars["lows"],
            volumes=series_250_bars["volumes"],
        )

        assert metrics.breakout_triggered is True
        assert metrics.distance_to_52w_high_pct >= -0.5

    def test_relative_sector_strength_calculation(self, series_250_bars):
        # Stock gained +120%, benchmark gained +20%
        n = 250
        bench_closes = [100.0 + (i * 0.08) for i in range(n)] # Gained ~20%

        engine = IndicatorEngine()
        metrics = engine.calculate(
            "OUTPERFORMER",
            closes=series_250_bars["closes"],
            highs=series_250_bars["highs"],
            lows=series_250_bars["lows"],
            volumes=series_250_bars["volumes"],
            benchmark_closes=bench_closes,
        )

        assert metrics.relative_sector_strength > 0
        assert metrics.relative_sector_strength > 50.0 # Outperformed by a wide margin

    def test_insufficient_bars_raises_value_error(self):
        engine = IndicatorEngine()
        with pytest.raises(ValueError, match="at least 20 historical bars"):
            engine.calculate(
                ticker="SHORT",
                closes=[100.0] * 12,
                highs=[101.0] * 12,
                lows=[99.0] * 12,
                volumes=[500_000] * 12,
            )

    def test_indicatorengine_iloc_indexing_no_future_warnings(self, series_250_bars):
        import warnings
        engine = IndicatorEngine()

        # Catch all warnings during calculation to verify zero FutureWarnings emitted
        with warnings.catch_warnings(record=True) as recorded_warnings:
            warnings.simplefilter("always")
            metrics = engine.calculate(
                ticker="CLEAN_INDEXING",
                closes=series_250_bars["closes"],
                highs=series_250_bars["highs"],
                lows=series_250_bars["lows"],
                volumes=series_250_bars["volumes"],
            )

            # Filter for any FutureWarnings related to series positional indexing
            future_warnings = [
                w for w in recorded_warnings
                if issubclass(w.category, FutureWarning) and "position" in str(w.message).lower()
            ]
            assert len(future_warnings) == 0, f"FutureWarning detected: {future_warnings}"
            assert metrics.latest_close == series_250_bars["closes"][-1]
            assert metrics.latest_volume == series_250_bars["volumes"][-1]

    def test_indicatorengine_with_series_and_dict_mock(self, series_250_bars):
        engine = IndicatorEngine()

        # Test calculate_from_df mock
        class MockDataFrame:
            def __init__(self, data_dict):
                self.data = data_dict
                self.columns = list(data_dict.keys())
            def __getitem__(self, col):
                class MockCol:
                    def __init__(self, vals):
                        self.vals = vals
                    def dropna(self):
                        return self.vals
                return MockCol(self.data[col])

        mock_df = MockDataFrame({
            "Close": series_250_bars["closes"],
            "High": series_250_bars["highs"],
            "Low": series_250_bars["lows"],
            "Volume": series_250_bars["volumes"],
        })

        metrics = engine.calculate_from_df(mock_df, ticker="DF_TEST")
        assert metrics.ticker == "DF_TEST"
        assert metrics.bars_processed == 250
        assert metrics.latest_close > 0

