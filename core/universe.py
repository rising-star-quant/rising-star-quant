"""
Rising Star Trend Engine - Sprint 4: Universe & Watchlist Integration Module
Automated S&P 500 constituent retrieval, local caching, and resilient batch processing.
Handles rate-limits, missing data, and delisted tickers gracefully without breaking execution loops.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from typing import Callable, Dict, Generator, List, Optional, Tuple, TypeVar

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)
T = TypeVar("T")

# Core fallback S&P 500 constituents (curated top representatives across sectors)
FALLBACK_SP500_TICKERS: List[str] = [
    "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "AVGO", "JPM",
    "LLY", "V", "UNH", "XOM", "MA", "COST", "HD", "PG", "NFLX", "JNJ",
    "ABBV", "CRM", "BAC", "WMT", "CVX", "MRK", "KO", "AMD", "PLTR", "PEP",
    "ADBE", "ORCL", "LIN", "MCD", "ACN", "CSCO", "TMO", "ABT", "WFC", "IBM",
    "GE", "PM", "CAT", "TXN", "NOW", "QCOM", "ISRG", "AMAT", "VZ", "SPGI",
    "INTU", "DIS", "BKNG", "GS", "MS", "RTX", "UBER", "AXP", "HON", "PFE",
    "LOW", "SYK", "COP", "BLK", "AMGN", "TJX", "VRTX", "PANW", "DE", "LRCX",
    "FI", "ETN", "BSX", "CB", "MDT", "PGR", "CI", "MU", "SCHW", "ADI",
    "KLAC", "BMY", "SBUX", "C", "GILD", "SNPS", "MMC", "CDNS", "MDLZ", "ANET",
    "CRWD", "APP", "ARM", "SMCI", "MSTR", "DELL", "CEG", "VST", "COHR", "FTNT",
]

DEFAULT_CACHE_FILE = "sp500_tickers_cache.json"
CACHE_EXPIRY_DAYS = 7


def fetch_sp500_tickers(
    cache_path: str = DEFAULT_CACHE_FILE,
    force_refresh: bool = False,
    max_tickers: Optional[int] = None,
) -> List[str]:
    """
    Fetches the full S&P 500 constituent list.
    1. Checks local cache file if fresh (< 7 days).
    2. If stale or force_refresh, fetches from Wikipedia S&P 500 table.
    3. Normalizes tickers (e.g. replaces '.' with '-' like BRK.B -> BRK-B).
    4. Falls back to curated fallback universe if remote request fails or is rate-limited.
    """
    # 1. Check local cache
    if not force_refresh and os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                cached_at_str = data.get("cached_at")
                tickers = data.get("tickers", [])
                if cached_at_str and tickers:
                    cached_at = datetime.fromisoformat(cached_at_str)
                    if datetime.utcnow() - cached_at < timedelta(days=CACHE_EXPIRY_DAYS):
                        logger.info("Loaded %d S&P 500 tickers from local cache ('%s')", len(tickers), cache_path)
                        return tickers[:max_tickers] if max_tickers else tickers
        except Exception as exc:
            logger.warning("Could not read S&P 500 cache ('%s'): %s", cache_path, exc)

    # 2. Fetch from Wikipedia S&P 500 List
    tickers: List[str] = []
    if requests is not None:
        try:
            url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                html = resp.text
                # Extract ticker symbols from table: href="/wiki/..." or <td><a rel="nofollow" class="external text" ...>SYMBOL</a>
                # Wikipedia table column 1 has ticker in pattern: <td><a ...>XYZ</a></td> or similar
                matches = re.findall(r'<td><a\s+[^>]*class="external text"[^>]*>([A-Za-z0-9\.\-]+)</a></td>', html)
                if not matches:
                    # Alternative regex for wiki links
                    matches = re.findall(r'<tr>\s*<td><a\s+[^>]*href="[^"]*"[^>]*>([A-Z0-9\.\-]+)</a>\s*</td>', html)

                if matches and len(matches) >= 400:
                    cleaned_tickers = []
                    seen = set()
                    for m in matches:
                        clean = m.strip().replace(".", "-").upper()
                        if clean and clean not in seen and len(clean) <= 6:
                            seen.add(clean)
                            cleaned_tickers.append(clean)

                    if len(cleaned_tickers) >= 450:
                        tickers = cleaned_tickers
                        logger.info("Fetched %d S&P 500 constituents from Wikipedia.", len(tickers))
                        # Save to cache
                        try:
                            with open(cache_path, "w", encoding="utf-8") as f:
                                json.dump({
                                    "cached_at": datetime.utcnow().isoformat(),
                                    "tickers": tickers,
                                    "count": len(tickers)
                                }, f, indent=2)
                        except Exception as cache_err:
                            logger.warning("Could not cache S&P 500 tickers: %s", cache_err)
        except Exception as req_err:
            logger.warning("Failed to fetch S&P 500 constituents remotely: %s. Using fallback list.", req_err)

    if not tickers:
        logger.info("Using curated fallback S&P 500 constituent list (%d tickers).", len(FALLBACK_SP500_TICKERS))
        tickers = list(FALLBACK_SP500_TICKERS)

    return tickers[:max_tickers] if max_tickers else tickers


def chunk_list(items: List[T], chunk_size: int = 25) -> Generator[List[T], None, None]:
    """Splits a list into manageable sequential batches."""
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


class BatchMarketScanner:
    """
    Executes resilient batch scanning across equity universes with throttling,
    isolated error handling, and runtime execution metrics.
    """

    def __init__(
        self,
        batch_size: int = 20,
        batch_delay_seconds: float = 0.5,
        max_errors_per_batch: int = 10,
    ):
        self.batch_size = max(1, batch_size)
        self.batch_delay = max(0.0, batch_delay_seconds)
        self.max_errors = max_errors_per_batch

    def process_universe(
        self,
        tickers: List[str],
        processor_fn: Callable[[str], Optional[T]],
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> Tuple[List[T], Dict[str, Any]]:
        """
        Processes a list of tickers sequentially in batches.
        - Isolates errors per ticker so a single failed or delisted symbol never breaks the run.
        - Injects polite pacing delays between batches to mitigate API rate limiting.
        - Returns list of successful results and execution statistics.
        """
        results: List[T] = []
        skipped_or_failed: List[str] = []
        total = len(tickers)
        start_time = time.time()

        logger.info("Starting batch market scan for %d tickers (Batch size: %d, Delay: %.1fs)", total, self.batch_size, self.batch_delay)

        processed_count = 0
        batches = list(chunk_list(tickers, self.batch_size))

        for batch_idx, batch in enumerate(batches, start=1):
            batch_failures = 0
            for ticker in batch:
                processed_count += 1
                if on_progress:
                    on_progress(processed_count, total, ticker)

                try:
                    res = processor_fn(ticker)
                    if res is not None:
                        results.append(res)
                    else:
                        skipped_or_failed.append(ticker)
                        batch_failures += 1
                except Exception as exc:
                    logger.warning("Error processing ticker %s: %s", ticker, exc)
                    skipped_or_failed.append(ticker)
                    batch_failures += 1

            # Polite throttle between batches if more batches remain
            if batch_idx < len(batches) and self.batch_delay > 0:
                time.sleep(self.batch_delay)

        elapsed = round(time.time() - start_time, 2)
        stats = {
            "total_submitted": total,
            "successful_processed": len(results),
            "skipped_or_failed_count": len(skipped_or_failed),
            "skipped_or_failed_tickers": skipped_or_failed,
            "elapsed_seconds": elapsed,
            "throughput_tickers_per_sec": round(total / (elapsed or 1.0), 2),
        }

        logger.info(
            "Batch scan completed: %d successful, %d skipped/failed in %.2fs (%.1f tickers/sec)",
            len(results),
            len(skipped_or_failed),
            elapsed,
            stats["throughput_tickers_per_sec"],
        )
        return results, stats
