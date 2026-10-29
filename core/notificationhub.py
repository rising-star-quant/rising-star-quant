"""
Rising Star Trend Engine - NotificationHub Micro-Module
Dispatches real-time structured Telegram alerts and scan summaries.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None

from core.indicatorengine import TechnicalIndicators
from core.riskguard import RiskPlan
from core.scoringengine import ScoreResult

logger = logging.getLogger(__name__)


class NotificationHub:
    """
    Formats and broadcasts rich trading alerts to Telegram channels or private chats.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Sends a raw text message to the configured Telegram chat.
        """
        if not self.is_configured:
            logger.info("Telegram not configured (missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID). Simulating message:\n%s", text)
            return False

        if requests is None:
            logger.warning("requests library is not installed. Cannot send Telegram alert.")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info("Successfully dispatched Telegram alert.")
                return True
            else:
                logger.warning("Telegram API error (%d): %s", resp.status_code, resp.text)
                return False
        except Exception as exc:
            logger.warning("Failed to dispatch Telegram message: %s", exc)
            return False

    def send_alert(
        self,
        score: ScoreResult,
        indicators: TechnicalIndicators,
        risk: RiskPlan,
    ) -> bool:
        """
        Formats a structured alert card for a top-scoring momentum breakout candidate.
        """
        badge = "🔥 <b>RISING STAR BREAKOUT ALERT</b>" if score.tier == "STRONG_RISING_STAR" else "⚡ <b>MOMENTUM CANDIDATE</b>"

        message = (
            f"{badge}\n\n"
            f"<b>Symbol:</b> #{score.ticker}\n"
            f"<b>Score:</b> <code>{score.total_score}/100</code> ({score.tier})\n"
            f"<b>Current Price:</b> <code>${indicators.latest_close:.2f}</code>\n"
            f"<b>20-Day High:</b> <code>${indicators.high_20d:.2f}</code> "
            f"({'🔥 BREAKOUT' if indicators.is_20d_high_breakout else f'{indicators.distance_to_20d_high_pct}%'})\n"
            f"<b>Volume Surge:</b> <code>{indicators.volume_surge_10d}x</code> 10d avg\n"
            f"<b>MA50 Support:</b> <code>${indicators.ma50:.2f}</code>\n\n"
            f"🛡 <b><u>RISK GUARD EXECUTION PLAN</u></b>\n"
            f"• <b>Entry:</b> ${risk.entry_price:.2f}\n"
            f"• <b>Stop Loss:</b> <b>${risk.stop_loss:.2f}</b> (-{risk.risk_pct}%)\n"
            f"• <b>Target 1 (2R):</b> ${risk.target_2r:.2f}\n"
            f"• <b>Target 2 (3R):</b> ${risk.target_3r:.2f}\n"
            f"• <b>Target 3 (5R):</b> ${risk.target_5r:.2f}\n"
            f"• <b>Suggested Size:</b> {risk.suggested_shares_1k_risk} shares ($1k risk)\n\n"
            f"<i>{score.summary}</i>"
        )
        return self.send_message(message)

    def send_daily_summary(self, total_scanned: int, qualified_count: int, top_tickers: List[str]) -> bool:
        """Dispatches an end-of-scan summary report."""
        top_str = ", ".join([f"#{t}" for t in top_tickers]) if top_tickers else "None"
        text = (
            f"📊 <b>Rising Star Trend Engine - Scan Complete</b>\n\n"
            f"• <b>Total Tickers Evaluated:</b> {total_scanned}\n"
            f"• <b>Qualified Breakouts:</b> {qualified_count}\n"
            f"• <b>Top Candidates:</b> {top_str}\n\n"
            f"<i>Execution finished at market close.</i>"
        )
        return self.send_message(text)
