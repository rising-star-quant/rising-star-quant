"""
Rising Star Trend Engine - IndicatorEngine Micro-Module
Calculates trend alignment, moving averages (MA20, MA50, MA200), volume surges, and ATR.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional
from core.dataconnector import MarketData

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TechnicalIndicators:
    """Quantitative indicator metrics for trend scoring."""
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
    """
    Computes key momentum, moving average, and volume indicators.
    """

    @staticmethod
    def _calculate_sma(series: List[float], period: int) -> Optional[float]:
        if len(series) < period:
            return None
        return sum(series[-period:]) / period

    @staticmethod
    def _calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Calculates Average True Range over `period` bars."""
        if len(closes) < period + 1:
            # Fallback to high-low range average
            ranges = [h - l for h, l in zip(highs[-period:], lows[-period:])]
            return sum(ranges) / len(ranges) if ranges else 1.0

        true_ranges: List[float] = []
        for i in range(len(closes) - period, len(closes)):
            h = highs[i]
            l = lows[i]
            prev_c = closes[i - 1]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            true_ranges.append(tr)

        return sum(true_ranges) / len(true_ranges) if true_ranges else 1.0

    def calculate(self, data: MarketData) -> TechnicalIndicators:
        """
        Derives all technical and trend indicators from the OHLCV bars.
        """
        closes = data.close_prices
        highs = data.high_prices
        lows = data.low_prices
        volumes = data.volumes

        latest_close = data.latest_close
        latest_vol = data.latest_volume

        # 1. Moving Averages
        ma20 = self._calculate_sma(closes, 20) or latest_close
        ma50 = self._calculate_sma(closes, 50) or ma20
        ma200 = self._calculate_sma(closes, 200)

        is_above_ma50 = latest_close >= ma50

        # Trend alignment: Price > MA50 (> MA200 if available)
        if ma200 is not None:
            is_trend_aligned = latest_close > ma50 > ma200
        else:
            is_trend_aligned = latest_close > ma50 >= ma20

        # 2. 20-Day High Breakout
        recent_20_highs = highs[-20:] if len(highs) >= 20 else highs
        high_20d = max(recent_20_highs) if recent_20_highs else latest_close

        # Distance to 20d High in %
        distance_to_20d_high_pct = ((latest_close - high_20d) / high_20d) * 100.0
        # Breakout if within 0.5% or breaking above
        is_20d_high_breakout = latest_close >= (high_20d * 0.995)

        # 3. Volume Surge
        vol_10d_avg = sum(volumes[-10:]) / 10.0 if len(volumes) >= 10 else float(latest_vol)
        vol_50d_avg = sum(volumes[-50:]) / 50.0 if len(volumes) >= 50 else vol_10d_avg

        volume_surge_10d = latest_vol / vol_10d_avg if vol_10d_avg > 0 else 1.0
        volume_surge_50d = latest_vol / vol_50d_avg if vol_50d_avg > 0 else 1.0

        is_volume_expansion = volume_surge_10d >= 1.25

        # 4. Volatility / ATR
        atr14 = self._calculate_atr(highs, lows, closes, period=14)
        atr_pct = (atr14 / latest_close) * 100.0 if latest_close > 0 else 0.0

        return TechnicalIndicators(
            ticker=data.ticker,
            latest_close=latest_close,
            latest_volume=latest_vol,
            ma20=round(ma20, 2),
            ma50=round(ma50, 2),
            ma200=round(ma200, 2) if ma200 is not None else None,
            high_20d=round(high_20d, 2),
            distance_to_20d_high_pct=round(distance_to_20d_high_pct, 2),
            is_20d_high_breakout=is_20d_high_breakout,
            volume_surge_10d=round(volume_surge_10d, 2),
            volume_surge_50d=round(volume_surge_50d, 2),
            is_volume_expansion=is_volume_expansion,
            atr14=round(atr14, 2),
            atr_pct=round(atr_pct, 2),
            is_above_ma50=is_above_ma50,
            is_trend_aligned=is_trend_aligned,
        )
