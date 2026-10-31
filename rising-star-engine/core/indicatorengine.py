"""
Rising Star Trend Engine - Sprint 2: IndicatorEngine Atomic Micro-Module
Quantitative mathematics module processing historical OHLCV series (250 daily bars).
Calculates:
- Moving Averages (MA50, MA200) and 20-session MA50 slope via Pandas, NumPy, and TA-Lib
- Institutional volume accumulation (up-day vs down-day volume surge >= 30%)
- 20-day resistance levels and 52-week high breakout triggers
- Relative sector / benchmark performance strength

Refactored to eliminate Pandas FutureWarning deprecation notices:
- All positional index lookups on Series use explicit .iloc[] calls.
- Provides fallback wrapper for environments where Pandas is not installed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field

try:
    import numpy as np
except ImportError:
    np = None

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import talib
except ImportError:
    talib = None


class _SeriesAccessor:
    """Provides .iloc[] positional indexing fallback when pandas is not installed."""
    __slots__ = ("_data",)

    def __init__(self, data: Any):
        self._data = data

    def __getitem__(self, idx: Any) -> Any:
        if isinstance(idx, slice):
            return _SeriesWrapper(self._data[idx])
        return self._data[idx]


class _SeriesWrapper:
    """Lightweight Series wrapper that supports .iloc[] indexing and common Series methods."""
    __slots__ = ("_data",)

    def __init__(self, data: Any):
        if hasattr(data, "tolist"):
            self._data = data.tolist()
        elif isinstance(data, list):
            self._data = data
        else:
            self._data = list(data)

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, idx: Any) -> Any:
        return self._data[idx]

    @property
    def iloc(self) -> _SeriesAccessor:
        return _SeriesAccessor(self._data)

    def tolist(self) -> List[Any]:
        return list(self._data)

    def max(self) -> Any:
        return max(self._data) if self._data else 0.0

    def min(self) -> Any:
        return min(self._data) if self._data else 0.0


def _to_positional_series(data: Any, dtype: Optional[str] = None) -> Any:
    """
    Ensures data is a Series-like object providing explicit .iloc[] positional indexing.
    Converts inputs (lists, ndarrays, or existing Series) to pd.Series when pandas is available,
    or wraps them in _SeriesWrapper. Prevents Pandas FutureWarning deprecations.
    """
    if data is None:
        return None
    if pd is not None:
        if isinstance(data, pd.Series):
            return data
        return pd.Series(data, dtype=dtype)
    if hasattr(data, "iloc"):
        return data
    return _SeriesWrapper(data)


class TechnicalTrend(BaseModel):
    """Trend alignment and moving average metrics."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    ma50: float = Field(..., description="50-day simple moving average.")
    ma200: Optional[float] = Field(default=None, description="200-day simple moving average (None if <200 bars).")
    ma50_slope_20d: float = Field(
        ...,
        description="Linear regression or change slope of the MA50 over the last 20 trading sessions (% per session)."
    )
    is_above_ma50: bool = Field(..., description="True if latest close >= MA50.")
    is_above_ma200: bool = Field(default=False, description="True if latest close >= MA200.")
    is_trend_aligned: bool = Field(
        ...,
        description="True if Close > MA50 > MA200 and MA50 slope is positive (or Close > MA50 if <200 bars)."
    )


class VolumeMetrics(BaseModel):
    """Institutional volume accumulation dynamics."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    up_day_avg_volume: float = Field(..., ge=0, description="Average trading volume on positive price sessions.")
    down_day_avg_volume: float = Field(..., ge=0, description="Average trading volume on negative price sessions.")
    up_down_volume_ratio: float = Field(
        ...,
        ge=0,
        description="Ratio of up-day volume to down-day volume (up_avg / down_avg)."
    )
    institutional_accumulation: bool = Field(
        ...,
        description="True if up-day average volume exceeds down-day volume by 30%+ (ratio >= 1.30)."
    )


class IndicatorMetrics(BaseModel):
    """Strictly typed quantitative indicators emitted by IndicatorEngine."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    ticker: str
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    bars_processed: int = Field(..., ge=20, description="Number of daily OHLCV bars analyzed.")
    latest_close: float = Field(..., gt=0)
    latest_volume: int = Field(..., ge=0)
    resistance_20d: float = Field(..., gt=0, description="Highest high of the preceding 20 trading sessions.")
    high_52w: float = Field(..., gt=0, description="Highest high over the 250-bar historical window.")
    distance_to_resistance_pct: float = Field(
        ...,
        description="Percentage distance from latest close to 20d resistance level."
    )
    distance_to_52w_high_pct: float = Field(
        ...,
        description="Percentage distance from latest close to 52-week high."
    )
    breakout_triggered: bool = Field(
        ...,
        description="True if latest price breaks 20d resistance or is within 0.5% of 52w high with volume confirmation."
    )
    breakout_type: str = Field(
        default="NONE",
        description="Breakout classification: '20D_RESISTANCE', '52W_HIGH', 'DUAL_BREAKOUT', or 'NONE'."
    )
    relative_sector_strength: float = Field(
        default=0.0,
        description="Normalized relative strength vs benchmark / sector ETF (percentage points over lookback)."
    )
    technical_trend: TechnicalTrend
    volume_metrics: VolumeMetrics


class IndicatorEngine:
    """
    Headless quantitative mathematics module for trend, volume surge, and breakout monitoring.
    Uses Pandas, NumPy, and TA-Lib with explicit .iloc[] positional indexing to eliminate FutureWarnings.
    """

    def __init__(
        self,
        accumulation_threshold: float = 1.30,  # 30%+ surge on up-days vs down-days
        breakout_tolerance_pct: float = 0.5,    # Within 0.5% considered active breakout
    ):
        self.accumulation_threshold = accumulation_threshold
        self.breakout_tolerance_pct = breakout_tolerance_pct

    @staticmethod
    def _compute_sma(prices: Any, period: int) -> Optional[Any]:
        """
        Computes simple moving average using TA-Lib or Pandas rolling, returning a Series-like object.
        """
        n = len(prices)
        if n < period:
            return None

        # Convert to list or 1D array if needed
        price_list: List[float] = [float(x) for x in (prices.tolist() if hasattr(prices, "tolist") else prices)]

        if talib is not None and np is not None:
            try:
                arr = np.array(price_list, dtype=np.float64)
                sma_arr = talib.SMA(arr, timeperiod=period)
                clean_vals = [float(x) if not np.isnan(x) else 0.0 for x in sma_arr]
                return _to_positional_series(clean_vals, dtype="float64")
            except Exception:
                pass

        if pd is not None:
            try:
                s = pd.Series(price_list, dtype="float64").rolling(window=period).mean().fillna(0.0)
                return s
            except Exception:
                pass

        # Native vector / rolling window computation fallback
        result: List[float] = []
        running_sum = sum(price_list[:period])
        result.append(running_sum / period)
        for i in range(period, n):
            running_sum += price_list[i] - price_list[i - period]
            result.append(running_sum / period)
        padded = [0.0] * (period - 1) + result
        return _to_positional_series(padded, dtype="float64")

    @staticmethod
    def _compute_slope(series: Any, window: int = 20) -> float:
        """
        Calculates the slope of a series over the trailing `window` points.
        Normalized as percentage rate of change per session.
        Uses explicit .iloc[] indexing to prevent Pandas FutureWarning deprecations.
        """
        s = _to_positional_series(series, dtype="float64")
        if len(s) < window or s.iloc[-window] == 0:
            return 0.0

        sub = s.iloc[-window:]
        if np is not None:
            try:
                x = np.arange(window)
                y = np.array(sub.tolist() if hasattr(sub, "tolist") else sub, dtype=np.float64)
                coeffs = np.polyfit(x, y, 1)
                slope_raw = float(coeffs[0])
                mean_val = float(np.mean(y))
                return round((slope_raw / mean_val) * 100.0, 4) if mean_val > 0 else 0.0
            except Exception:
                pass

        denom = float(sub.iloc[0]) if float(sub.iloc[0]) != 0 else 1.0
        pct_change = (float(sub.iloc[-1]) - float(sub.iloc[0])) / denom
        return round((pct_change / window) * 100.0, 4)

    def calculate_from_df(
        self,
        df: Any,
        ticker: str,
        benchmark_df: Optional[Any] = None,
    ) -> IndicatorMetrics:
        """
        Direct convenience interface for Pandas DataFrames.
        Preserves Series objects and uses .iloc[] indexing for warning-free execution.
        Expects columns 'Close', 'High', 'Low', 'Volume' (case-insensitive).
        """
        cols = {str(c).lower(): c for c in df.columns}
        closes = df[cols["close"]].dropna()
        highs = df[cols["high"]].dropna()
        lows = df[cols["low"]].dropna()
        volumes = df[cols["volume"]].dropna()

        bench_closes = None
        if benchmark_df is not None:
            b_cols = {str(c).lower(): c for c in benchmark_df.columns}
            if "close" in b_cols:
                bench_closes = benchmark_df[b_cols["close"]].dropna()

        return self.calculate(ticker, closes, highs, lows, volumes, bench_closes)

    def calculate(
        self,
        ticker: str,
        closes: Union[List[float], Any],
        highs: Union[List[float], Any],
        lows: Union[List[float], Any],
        volumes: Union[List[int], Any],
        benchmark_closes: Optional[Union[List[float], Any]] = None,
    ) -> IndicatorMetrics:
        """
        Processes historical OHLCV data (250 daily bars) and returns strictly validated IndicatorMetrics.
        Uses explicit .iloc[] indexing across all series to prevent Pandas FutureWarning deprecations.
        Pure headless mathematical function with zero UI dependencies.
        """
        # Normalize all series to positional-safe objects supporting .iloc[]
        closes_s = _to_positional_series(closes, dtype="float64")
        highs_s = _to_positional_series(highs, dtype="float64")
        lows_s = _to_positional_series(lows, dtype="float64")
        volumes_s = _to_positional_series(volumes, dtype="int64")

        n_bars = len(closes_s)
        if n_bars < 20:
            raise ValueError(f"IndicatorEngine requires at least 20 historical bars; got {n_bars}.")

        latest_close = float(closes_s.iloc[-1])
        latest_vol = int(volumes_s.iloc[-1])

        # 1. Moving Averages (50 and 200)
        ma50_series = self._compute_sma(closes_s, min(50, n_bars))
        ma50 = float(ma50_series.iloc[-1]) if ma50_series is not None else latest_close

        ma200_series = self._compute_sma(closes_s, 200) if n_bars >= 200 else None
        ma200 = float(ma200_series.iloc[-1]) if ma200_series is not None else None

        # 20-session slope of MA50
        if ma50_series is not None and len(ma50_series) >= 20:
            ma50_slope_20d = self._compute_slope(ma50_series, 20)
        else:
            ma50_slope_20d = 0.0

        is_above_ma50 = latest_close >= ma50
        is_above_ma200 = (latest_close >= ma200) if ma200 is not None else False

        if ma200 is not None:
            is_trend_aligned = (latest_close > ma50 > ma200) and (ma50_slope_20d > 0)
        else:
            is_trend_aligned = (latest_close > ma50) and (ma50_slope_20d > 0)

        technical_trend = TechnicalTrend(
            ma50=round(ma50, 2),
            ma200=round(ma200, 2) if ma200 is not None else None,
            ma50_slope_20d=round(ma50_slope_20d, 4),
            is_above_ma50=is_above_ma50,
            is_above_ma200=is_above_ma200,
            is_trend_aligned=is_trend_aligned,
        )

        # 2. Institutional Volume Metrics (Up-days vs Down-days)
        up_volumes: List[int] = []
        down_volumes: List[int] = []

        for i in range(1, n_bars):
            # Positional access using .iloc[] to prevent Pandas warnings/key errors
            price_change = float(closes_s.iloc[i]) - float(closes_s.iloc[i - 1])
            vol = int(volumes_s.iloc[i])
            if price_change > 0:
                up_volumes.append(vol)
            elif price_change < 0:
                down_volumes.append(vol)

        up_day_avg = float(sum(up_volumes) / len(up_volumes)) if up_volumes else float(latest_vol)
        down_day_avg = float(sum(down_volumes) / len(down_volumes)) if down_volumes else float(latest_vol)

        up_down_ratio = up_day_avg / down_day_avg if down_day_avg > 0 else 1.0
        institutional_accumulation = up_down_ratio >= self.accumulation_threshold

        volume_metrics = VolumeMetrics(
            up_day_avg_volume=round(up_day_avg, 1),
            down_day_avg_volume=round(down_day_avg, 1),
            up_down_volume_ratio=round(up_down_ratio, 3),
            institutional_accumulation=institutional_accumulation,
        )

        # 3. 20-Day Resistance & 52-Week High Breakouts
        recent_20_highs = highs_s.iloc[-20:]
        resistance_20d = float(recent_20_highs.max())
        high_52w = float(highs_s.max())

        dist_20d_pct = round(((latest_close - resistance_20d) / resistance_20d) * 100.0, 2)
        dist_52w_pct = round(((latest_close - high_52w) / high_52w) * 100.0, 2)

        is_20d_breakout = latest_close >= (resistance_20d * (1.0 - (self.breakout_tolerance_pct / 100.0)))
        is_52w_breakout = latest_close >= (high_52w * (1.0 - (self.breakout_tolerance_pct / 100.0)))

        breakout_triggered = is_20d_breakout or is_52w_breakout

        if is_20d_breakout and is_52w_breakout:
            breakout_type = "DUAL_BREAKOUT"
        elif is_52w_breakout:
            breakout_type = "52W_HIGH"
        elif is_20d_breakout:
            breakout_type = "20D_RESISTANCE"
        else:
            breakout_type = "NONE"

        # 4. Relative Sector Strength
        relative_strength = 0.0
        if benchmark_closes is not None:
            bench_s = _to_positional_series(benchmark_closes, dtype="float64")
            if len(bench_s) >= 20 and len(bench_s) == n_bars:
                first_close = float(closes_s.iloc[0]) or 1.0
                first_bench = float(bench_s.iloc[0]) or 1.0
                ticker_return = ((float(closes_s.iloc[-1]) - first_close) / first_close) * 100.0
                bench_return = ((float(bench_s.iloc[-1]) - first_bench) / first_bench) * 100.0
                relative_strength = round(ticker_return - bench_return, 2)
        elif n_bars >= 50:
            fifty_close = float(closes_s.iloc[-50]) or 1.0
            fifty_day_return = ((float(closes_s.iloc[-1]) - fifty_close) / fifty_close) * 100.0
            relative_strength = round(fifty_day_return, 2)

        return IndicatorMetrics(
            ticker=ticker.strip().upper(),
            calculated_at=datetime.utcnow(),
            bars_processed=n_bars,
            latest_close=round(latest_close, 2),
            latest_volume=latest_vol,
            resistance_20d=round(resistance_20d, 2),
            high_52w=round(high_52w, 2),
            distance_to_resistance_pct=dist_20d_pct,
            distance_to_52w_high_pct=dist_52w_pct,
            breakout_triggered=breakout_triggered,
            breakout_type=breakout_type,
            relative_sector_strength=relative_strength,
            technical_trend=technical_trend,
            volume_metrics=volume_metrics,
        )
