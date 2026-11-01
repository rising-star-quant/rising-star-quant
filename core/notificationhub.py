"""
Rising Star Trend Engine - Sprint 3 & 4: NotificationHub Micro-Module
Dispatches rich, actionable real-time Telegram trade alerts and end-of-scan summary digests.
Supports both individual Buy Alert notifications (with ATR stops and position sizing) and daily digests.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None

from core.indicatorengine import IndicatorMetrics
from core.riskguard import RiskPlan
from core.scoringengine import ScorePayload

logger = logging.getLogger(__name__)


class NotificationHub:
    """
    Formats and broadcasts rich, institutional-grade trading alerts to Telegram channels or private chats.
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
        """Returns True if bot token and chat ID are both present."""
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Sends an HTML or Markdown formatted text message to Telegram.
        If credentials are not configured, logs a simulated message cleanly without errors.
        """
        if not self.is_configured:
            logger.info("Telegram notification simulated (TELEGRAM_BOT_TOKEN/CHAT_ID not set):\n%s", text)
            return False

        if requests is None:
            logger.warning("requests library is not installed. Cannot send Telegram message.")
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

    def send_buy_alert(
        self,
        ticker: str,
        score: ScorePayload,
        indicators: IndicatorMetrics,
        risk: Optional[RiskPlan] = None,
    ) -> bool:
        """
        Formats and dispatches a comprehensive BUY ALERT card with execution levels and position sizing.
        """
        badge = "🔥 <b>RISING STAR BUY ALERT</b>" if score.is_buy_alert else "⚡ <b>EMERGING MOMENTUM CANDIDATE</b>"

        # Breakout details
        breakout_label = indicators.breakout_type
        if breakout_label == "DUAL_BREAKOUT":
            bo_str = "🔥 <b>DUAL BREAKOUT</b> (20D Resistance + 52W High)"
        elif breakout_label == "52W_HIGH":
            bo_str = f"🚀 <b>52-WEEK HIGH BREAKOUT</b> (${indicators.high_52w:.2f})"
        elif breakout_label == "20D_RESISTANCE":
            bo_str = f"⚡ <b>20-DAY CEILING BREAKOUT</b> (${indicators.resistance_20d:.2f})"
        else:
            bo_str = f"Consolidating (Ceiling: ${indicators.resistance_20d:.2f})"

        lines = [
            badge,
            "",
            f"<b>Symbol:</b> <code>#{ticker.upper()}</code>",
            f"<b>Rising Star Score:</b> <code>{score.rising_star_score:.1f}/100</code> ({score.tier})",
            f"<b>Current Price:</b> <code>${indicators.latest_close:.2f}</code>",
            f"<b>Breakout Status:</b> {bo_str}",
            f"<b>Institutional Volume:</b> <code>{indicators.volume_metrics.up_down_volume_ratio:.2f}x</code> up/down surge",
            f"<b>MA50 Support:</b> <code>${indicators.technical_trend.ma50:.2f}</code> (Slope: +{indicators.technical_trend.ma50_slope_20d:.2f}%/session)",
        ]

        if indicators.relative_sector_strength != 0:
            lines.append(f"<b>Relative Strength:</b> <code>+{indicators.relative_sector_strength:.1f}%</code> vs Benchmark")

        # Append Risk Guard Execution Plan if available
        if risk is not None:
            lines.extend([
                "",
                "🛡 <b><u>RISK GUARD EXECUTION PLAN</u></b>",
                f"• <b>Entry:</b> <code>${risk.entry_price:.2f}</code>",
                f"• <b>ATR (14d):</b> <code>${risk.atr_14:.2f}</code> ({risk.volatility_tier} volatility)",
                f"• <b>Stop Loss:</b> <b>${risk.stop_loss_price:.2f}</b> (<code>-{risk.risk_pct:.1f}%</code>)",
                f"• <b>Target 1 (1R):</b> <code>${risk.target_1r:.2f}</code>",
                f"• <b>Target 2 (2R):</b> <code>${risk.target_2r:.2f}</code>",
                f"• <b>Target 3 (3R):</b> <code>${risk.target_3r:.2f}</code>",
                f"• <b>Target 5 (5R):</b> <code>${risk.target_5r:.2f}</code> <i>(Runner)</i>",
                f"• <b>Recommended Size:</b> <b>{risk.suggested_shares} shares</b> (~${risk.position_value_usd:,.0f} | {risk.position_pct_of_account:.1f}% port)",
                f"• <b>Max Loss Risk:</b> <code>${risk.max_loss_usd:,.2f}</code>",
            ])

        # Append Gatekeeper audit info
        gk = score.gatekeeper
        lines.extend([
            "",
            f"<b>Gatekeeper Audit:</b> {'✅ Approved' if gk.gatekeeper_approved else '⚠️ Pending'}"
            f" (PF: {gk.profit_factor:.2f} | Win Rate: {gk.win_rate*100:.0f}%)",
            "",
            f"<i>{score.summary}</i>",
        ])

        message = "\n".join(lines)
        return self.send_message(message)

    def send_alert(
        self,
        score: Any,
        indicators: Any,
        risk: Optional[Any] = None,
    ) -> bool:
        """
        Universal adapter interface accepting both ScorePayload and legacy ScoreResult models.
        """
        ticker = getattr(score, "ticker", "UNKNOWN")
        if isinstance(score, ScorePayload) and isinstance(indicators, IndicatorMetrics):
            risk_plan = risk if isinstance(risk, RiskPlan) else None
            return self.send_buy_alert(ticker, score, indicators, risk_plan)

        # Legacy fallback
        total_score = getattr(score, "rising_star_score", getattr(score, "total_score", 0.0))
        tier = getattr(score, "tier", "WATCHLIST")
        close_p = getattr(indicators, "latest_close", 0.0)

        text = (
            f"🔥 <b>RISING STAR ALERT: #{ticker}</b>\n\n"
            f"<b>Score:</b> {total_score}/100 ({tier})\n"
            f"<b>Price:</b> ${close_p:.2f}\n"
        )
        if risk is not None:
            stop = getattr(risk, "stop_loss_price", getattr(risk, "stop_loss", 0.0))
            shares = getattr(risk, "suggested_shares", 100)
            text += f"<b>Stop Loss:</b> ${stop:.2f}\n<b>Shares:</b> {shares}\n"

        return self.send_message(text)

    def send_daily_digest(
        self,
        total_scanned: int,
        qualified_count: int,
        buy_alerts_count: int,
        top_candidates: List[Dict[str, Any]],
        elapsed_seconds: float = 0.0,
    ) -> bool:
        """
        Dispatches an end-of-run daily digest report summarizing market scan results.
        """
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        lines = [
            "📊 <b><u>RISING STAR TREND ENGINE - NIGHTLY SCAN DIGEST</u></b>",
            f"<i>Execution Date: {now_str}</i>",
            "",
            f"• <b>Total Equities Analyzed:</b> <code>{total_scanned:,}</code>",
            f"• <b>S&P 500 Eligible Qualified:</b> <code>{qualified_count:,}</code>",
            f"• <b>Confirmed BUY ALERTS Triggered:</b> <b>{buy_alerts_count}</b>",
            f"• <b>Execution Time:</b> <code>{elapsed_seconds:.1f}s</code>",
            "",
        ]

        if top_candidates:
            lines.append("🏆 <b>Top Ranked Momentum Candidates:</b>")
            for idx, cand in enumerate(top_candidates[:8], start=1):
                sym = cand.get("ticker", "N/A")
                score_val = cand.get("score", 0.0)
                price_val = cand.get("latest_close", 0.0)
                is_alert = cand.get("is_buy_alert", False)
                alert_icon = "🔥 BUY ALERT" if is_alert else cand.get("tier", "WATCHLIST")
                lines.append(f"  {idx}. <b>#{sym}</b> — ${price_val:.2f} | <code>{score_val:.1f}/100</code> ({alert_icon})")
        else:
            lines.append("<i>No actionable breakout setups detected in this cycle.</i>")

        lines.extend([
            "",
            "⚙️ <i>Autonomous quantitative scan completed via GitHub Actions runner.</i>",
        ])

        return self.send_message("\n".join(lines))

    def send_daily_summary(
        self,
        total_scanned: int,
        qualified_count: int,
        top_tickers: List[str],
    ) -> bool:
        """Backward compatibility helper."""
        dummy_cands = [{"ticker": t, "score": 90.0, "latest_close": 100.0, "is_buy_alert": True} for t in top_tickers]
        return self.send_daily_digest(
            total_scanned=total_scanned,
            qualified_count=qualified_count,
            buy_alerts_count=len(top_tickers),
            top_candidates=dummy_cands,
        )
