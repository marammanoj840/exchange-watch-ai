"""
Telegram notification module for ExchangeWatch AI.

Supports:
  - Private bot chat (development/personal alerts)
  - Telegram Channel (public ExchangeWatch alert feed)

Both use the same bot token. The bot must be an administrator of the channel
to post messages there.

Message format follows the ExchangeWatch AI professional layout (Section G).
"""
import time
import json
import requests
from typing import Dict, Any, Optional, List
from app.config.settings import settings
from app.core.logger import logger


# Priority display mapping
PRIORITY_HEADER = {
    "CRITICAL": "🔴 CRITICAL ALERT",
    "HIGH":     "🟠 HIGH PRIORITY",
    "MEDIUM":   "🟡 MEDIUM PRIORITY",
    "LOW":      "🔵 INFORMATIONAL",
}

PRIORITY_EMOJI = {
    "CRITICAL": "🔴",
    "HIGH":     "🟠",
    "MEDIUM":   "🟡",
    "LOW":      "🔵",
}

# Human-readable category labels
CATEGORY_LABELS: Dict[str, str] = {
    "MANAGEMENT_CHANGE":      "Management Change",
    "AUDITOR_CHANGE":         "Auditor Change",
    "FINANCIAL_RESULTS":      "Financial Results",
    "MAJOR_ORDER_CONTRACT":   "Major Order / Contract",
    "BULK_BLOCK_DEAL":        "Bulk / Block Deal",
    "PROMOTER_SHAREHOLDING":  "Promoter Shareholding",
    "PLEDGE_ENCUMBRANCE":     "Pledge / Encumbrance",
    "DEBT_CREDIT_DEFAULT":    "Debt / Credit / Default",
    "REGULATORY_LEGAL":       "Regulatory / Legal",
    "M_AND_A_RESTRUCTURING":  "M&A / Restructuring",
    "CORPORATE_ACTION":       "Corporate Action",
    "BUSINESS_OPERATIONS":    "Business / Operations",
    "TRADING_EXCHANGE_CHANGE": "Trading / Exchange",
    "MATERIAL_DISCLOSURE":    "Material Disclosure",
    "ROUTINE_LOW_PRIORITY":   "Routine / Administrative",
    # Legacy types
    "BUYBACK": "Buyback",
    "MERGER": "Merger",
    "ACQUISITION": "Acquisition",
    "LISTING": "Listing",
    "TRADING_HALT": "Trading Halt",
    "SURVEILLANCE": "Surveillance",
    "REGULATORY": "Regulatory",
    "RESULTS": "Financial Results",
    "OTHER": "General Notice",
}

# Telegram message length limit (4096 chars); we cap at 3900 for safety
TELEGRAM_MAX_LEN = 3900


def _safe_text(value: str) -> str:
    """Strip or truncate a text value. Returns empty string for None."""
    if not value:
        return ""
    return str(value).strip()


def _build_highlights(
    key_facts: List[str],
    key_changes: List[str],
) -> List[str]:
    """Merge key_facts and key_changes into deduplicated highlights list."""
    seen = set()
    combined = []
    for item in (key_facts or []) + (key_changes or []):
        s = _safe_text(str(item))
        if s and s.lower() not in seen:
            seen.add(s.lower())
            combined.append(s)
    return combined[:6]


def _format_alert_message(doc_data: Dict[str, Any]) -> str:
    """
    Build the structured Telegram alert message.

    Layout (Section G):
    🏢 COMPANY NAME (SYMBOL)
    📊 CATEGORY · SOURCE DATE/TIME
    🔴/🟠/🟡 PRIORITY
    ⚡ Key Highlights
    🧠 ExchangeWatch AI analysis
    🎯 What Matters
    📅 Important Dates
    🔗 Official Filing
    ⚠️ Disclaimer

    Empty fields are hidden.
    """
    priority = _safe_text(doc_data.get("priority", "MEDIUM")).upper()
    if priority not in PRIORITY_HEADER:
        priority = "MEDIUM"

    exchange = _safe_text(doc_data.get("exchange", ""))
    event_type = _safe_text(doc_data.get("event_type", "OTHER"))
    category_label = CATEGORY_LABELS.get(event_type, event_type.replace("_", " ")).upper()

    company = _safe_text(doc_data.get("company_name", ""))
    symbol = doc_data.get("symbol")
    title = _safe_text(doc_data.get("title", ""))
    subject = _safe_text(doc_data.get("subject", "")) or title

    pub_date = _safe_text(
        doc_data.get("pub_date", "") or doc_data.get("publication_date", "")
    )
    eff_date = _safe_text(doc_data.get("effective_date", ""))
    start_date = _safe_text(doc_data.get("start_date", ""))
    end_date = _safe_text(doc_data.get("end_date", ""))
    deadline = _safe_text(doc_data.get("deadline", ""))
    summary = _safe_text(doc_data.get("summary", ""))

    key_facts = doc_data.get("key_facts", []) or []
    if isinstance(key_facts, str):
        try:
            key_facts = json.loads(key_facts)
        except Exception:
            key_facts = [key_facts]
    key_changes = doc_data.get("key_changes", []) or []
    if isinstance(key_changes, str):
        try:
            key_changes = json.loads(key_changes)
        except Exception:
            key_changes = [key_changes]
    highlights = _build_highlights(key_facts, key_changes)

    reason = _safe_text(doc_data.get("reason_for_priority", ""))
    action_req = _safe_text(doc_data.get("action_required", ""))
    uncertainties = doc_data.get("uncertainties", []) or []
    if isinstance(uncertainties, str):
        try:
            uncertainties = json.loads(uncertainties)
        except Exception:
            uncertainties = [uncertainties]

    doc_url = _safe_text(
        doc_data.get("official_source_url", "") or doc_data.get("doc_url", "")
    )
    doc_id = _safe_text(
        doc_data.get("doc_id", "") or doc_data.get("reference_number", "")
    )

    # Cross-exchange sources
    nse_url = _safe_text(doc_data.get("nse_source_url", ""))
    bse_url = _safe_text(doc_data.get("bse_source_url", ""))

    priority_emoji = PRIORITY_EMOJI.get(priority, "📢")
    priority_label = PRIORITY_HEADER.get(priority, f"📢 {priority}")

    lines = []

    # ── Header ──────────────────────────────────────────────────────────────
    if company:
        if symbol:
            lines.append(f"🏢 {company} ({symbol})")
        else:
            lines.append(f"🏢 {company}")
    elif subject:
        lines.append(f"🏢 {subject[:80]}")

    # Category · source date
    source_line = f"📊 {category_label}"
    if exchange:
        source_line += f" · {exchange}"
    if pub_date:
        source_line += f" · {pub_date}"
    lines.append(source_line)

    # Priority
    lines.append(priority_label)
    lines.append("")

    # ── Key Highlights ───────────────────────────────────────────────────────
    if highlights:
        lines.append("⚡ Key Highlights")
        for h in highlights:
            lines.append(f"▸ {h}")
        lines.append("")

    # ── AI Analysis block ────────────────────────────────────────────────────
    analysis_mode = _safe_text(doc_data.get("analysis_mode", ""))
    mode_label = "Document-Based Analysis"
    if analysis_mode == "FAST_NLP":
        mode_label = "Rule-Based Analysis (AI Unavailable)"
    elif analysis_mode == "LLM":
        mode_label = "AI-Assisted Analysis"

    lines.append(f"🧠 ExchangeWatch AI • {mode_label}")
    if summary:
        lines.append(summary)
    lines.append("")

    # ── What Matters ─────────────────────────────────────────────────────────
    what_matters: List[str] = []
    if reason:
        what_matters.append(reason)
    for u in uncertainties[:2]:
        u_s = _safe_text(str(u))
        if u_s and "full llm" not in u_s.lower():
            what_matters.append(u_s)
    if action_req and action_req not in ("Not stated in document.", ""):
        what_matters.append(f"Action required: {action_req}")

    if what_matters:
        lines.append("🎯 What Matters")
        for wm in what_matters[:3]:
            lines.append(f"▸ {wm}")
        lines.append("")

    # ── Important Dates ───────────────────────────────────────────────────────
    date_lines: List[str] = []
    if pub_date:
        date_lines.append(f"▸ Published: {pub_date}")
    if eff_date and eff_date not in ("Not stated in document.", ""):
        date_lines.append(f"▸ Effective: {eff_date}")
    if start_date and end_date:
        date_lines.append(f"▸ Period: {start_date} → {end_date}")
    elif start_date:
        date_lines.append(f"▸ From: {start_date}")
    if deadline and deadline not in ("Not stated in document.", ""):
        date_lines.append(f"▸ Deadline: {deadline}")

    if date_lines:
        lines.append("📅 Important Dates")
        lines.extend(date_lines)
        lines.append("")

    # ── Official Source Links ─────────────────────────────────────────────────
    if nse_url and bse_url:
        lines.append("🔗 Official Filings")
        lines.append(f"▸ NSE: {nse_url}")
        lines.append(f"▸ BSE: {bse_url}")
    elif doc_url:
        if doc_id:
            lines.append(f"🔗 Official {exchange} Filing ({doc_id})")
        else:
            lines.append(f"🔗 Official {exchange} Filing")
        lines.append(doc_url)
    elif doc_id:
        lines.append(f"🔖 Reference: {doc_id}")

    lines.append("")
    lines.append("⚠️ Informational update. Not investment advice.")

    message = "\n".join(lines)

    # Truncate safely at Telegram limit
    if len(message) > TELEGRAM_MAX_LEN:
        message = message[:TELEGRAM_MAX_LEN - 20] + "\n… [truncated]"

    return message


class TelegramNotifier:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.channel_enabled = settings.TELEGRAM_CHANNEL_ENABLED
        self.channel_id = settings.TELEGRAM_CHANNEL_ID

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def is_channel_configured(self) -> bool:
        return bool(self.bot_token and self.channel_enabled and self.channel_id)

    def _send_to_target(self, target_id: str, message: str, label: str) -> bool:
        """Send a message to a specific chat/channel ID with retry on transient network drops."""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": target_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                res = requests.post(url, json=payload, timeout=12)
                if res.status_code == 200:
                    logger.info(f"✅ Telegram {label} delivered successfully.")
                    return True
                else:
                    # Retry once without parse_mode if entity parsing failed
                    if "can't parse entities" in res.text or "Bad Request" in res.text:
                        payload.pop("parse_mode", None)
                        res2 = requests.post(url, json=payload, timeout=12)
                        if res2.status_code == 200:
                            logger.info(f"✅ Telegram {label} delivered (plain text fallback).")
                            return True
                        error_text = res2.text
                    else:
                        error_text = res.text
                    # Redact token from logged error
                    if self.bot_token and self.bot_token in error_text:
                        error_text = error_text.replace(self.bot_token, "[REDACTED_BOT_TOKEN]")
                    logger.error(f"Telegram API error for {label} — HTTP {res.status_code}: {error_text}")
                    return False
            except Exception as e:
                err_msg = str(e)
                if self.bot_token and self.bot_token in err_msg:
                    err_msg = err_msg.replace(self.bot_token, "[REDACTED_BOT_TOKEN]")
                if attempt < max_attempts:
                    logger.warning(f"⚠️ Telegram {label} delivery attempt {attempt} failed ({err_msg}). Retrying in 1.5s...")
                    time.sleep(1.5)
                    continue
                logger.error(f"Failed to send Telegram {label}: {err_msg}")
                return False
        return False

    def send_alert(self, doc_data: Dict[str, Any]) -> bool:
        """
        Send alert to private chat and/or channel.
        Returns True only if configured destination delivery succeeded (or was simulated).
        Never marks a failed delivery as successful.
        """
        message = _format_alert_message(doc_data)

        has_private = self.is_configured()
        has_channel = self.is_channel_configured()

        # Local simulation when no credentials configured
        if not has_private and not has_channel:
            logger.info("=" * 54)
            logger.info("TELEGRAM ALERT (Console simulation — not configured):")
            logger.info(message)
            logger.info("=" * 54)
            return True

        private_ok = False
        if has_private:
            private_ok = self._send_to_target(self.chat_id, message, "private chat")

        channel_ok = False
        if has_channel:
            channel_ok = self._send_to_target(self.channel_id, message, f"channel {self.channel_id}")
            if channel_ok:
                logger.info(f"📣 Alert also posted to Telegram Channel {self.channel_id}")
            else:
                logger.warning(
                    f"⚠️ Channel delivery failed for {doc_data.get('doc_id', '')}. "
                    "Daemon continues."
                )
        else:
            if self.channel_enabled and not self.channel_id:
                logger.warning(
                    "TELEGRAM_CHANNEL_ENABLED=true but TELEGRAM_CHANNEL_ID is not set. "
                    "Channel posting skipped."
                )

        if has_private:
            return private_ok
        return channel_ok

    def test_channel(self) -> bool:
        """
        Test channel posting with a real delivery attempt.
        Returns True on success, False with CHANNEL NOT CONFIGURED log if not set up.
        """
        if not self.is_channel_configured():
            logger.warning(
                "CHANNEL NOT CONFIGURED. To enable:\n"
                "1. Add the bot as administrator to your channel with 'Post Messages' permission.\n"
                "2. Set TELEGRAM_CHANNEL_ID=@yourchannel (or the numeric channel ID) in .env\n"
                "3. Set TELEGRAM_CHANNEL_ENABLED=true in .env"
            )
            return False

        test_msg = (
            "✅ ExchangeWatch AI — Channel Test\n"
            "This is a connectivity test message.\n"
            "If you see this, the channel is correctly configured."
        )
        return self._send_to_target(self.channel_id, test_msg, "channel test")


telegram_notifier = TelegramNotifier()
