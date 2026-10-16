"""
Phase 6 Live Channel Test Script
Sends a real alert to the Telegram channel and private chat,
verifies API success, and reports results.
Does NOT print the bot token.
"""
import sys
import os
import time
import json
import requests
from datetime import datetime

# Force UTF-8 for Windows console (emoji support)
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

from app.config.settings import settings
from app.notifications.telegram import TelegramNotifier, _format_alert_message

RESULTS = {}

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def result(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    RESULTS[name] = {"status": status, "detail": detail}
    icon = "✅" if passed else "❌"
    print(f"{icon} [{status}] {name}")
    if detail:
        print(f"     {detail}")

# ─── Verify Config ──────────────────────────────────────────────
section("STEP 0: Configuration Check")
print(f"BOT TOKEN:         SET (length={len(settings.TELEGRAM_BOT_TOKEN)})")
print(f"PRIVATE CHAT ID:   {settings.TELEGRAM_CHAT_ID}")
print(f"CHANNEL ENABLED:   {settings.TELEGRAM_CHANNEL_ENABLED}")
print(f"CHANNEL ID:        {settings.TELEGRAM_CHANNEL_ID}")

config_ok = (
    bool(settings.TELEGRAM_BOT_TOKEN)
    and bool(settings.TELEGRAM_CHAT_ID)
    and settings.TELEGRAM_CHANNEL_ENABLED
    and bool(settings.TELEGRAM_CHANNEL_ID)
)
result("Configuration", config_ok, f"Channel ID={settings.TELEGRAM_CHANNEL_ID}")

if not config_ok:
    print("FATAL: Configuration incomplete. Aborting.")
    sys.exit(1)

# ─── Test A: Controlled Channel Alert ───────────────────────────
section("TEST A: Controlled Channel Test Alert")

test_doc = {
    "priority": "HIGH",
    "exchange": "NSE",
    "event_type": "REGULATORY_CHANGE",
    "company_name": "ExchangeWatch AI System",
    "title": "ExchangeWatch AI — Phase 6 Channel Live Test",
    "subject": "ExchangeWatch AI — Phase 6 Channel Live Test",
    "pub_date": datetime.now().strftime("%d %b %Y %H:%M IST"),
    "effective_date": datetime.now().strftime("%d-%B-%Y"),
    "start_date": "",
    "end_date": "",
    "deadline": "Not stated in document.",
    "summary": (
        "This is a controlled system test alert confirming that the "
        "ExchangeWatch AI Telegram Channel integration is working correctly. "
        "No regulatory action required."
    ),
    "key_changes": [
        "Telegram Channel integration successfully configured",
        "Bot administrator permissions verified",
        "Dual delivery (private + channel) operational",
    ],
    "reason_for_priority": "HIGH: System verification test for channel go-live.",
    "action_required": "No action required — system test only.",
    "doc_url": "https://www.nseindia.com",
    "official_source_url": "https://www.nseindia.com",
    "doc_id": f"TEST/CHANNEL/{datetime.now().strftime('%Y%m%d%H%M%S')}",
    "latency_summary": {"total_latency_ms": 0},
    "analysis_mode": "CONTROLLED_TEST",
}

# Format the alert message
msg = _format_alert_message(test_doc)
print(f"\nAlert message length: {len(msg)} chars")
print(f"Preview:\n{msg[:300]}...")

# Send to channel directly via raw API call (to capture exact response)
token = settings.TELEGRAM_BOT_TOKEN
channel_id = settings.TELEGRAM_CHANNEL_ID
private_id = settings.TELEGRAM_CHAT_ID

print(f"\n--- Sending to Channel ({channel_id}) ---")
t0 = time.perf_counter()
try:
    r_channel = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": channel_id, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=15,
    )
    channel_ms = (time.perf_counter() - t0) * 1000
    ch_data = r_channel.json()
    ch_ok = ch_data.get("ok", False)
    ch_msg_id = ch_data.get("result", {}).get("message_id") if ch_ok else None
    ch_detail = (
        f"HTTP {r_channel.status_code} | ok={ch_ok} | message_id={ch_msg_id} | {channel_ms:.0f}ms"
        if ch_ok
        else f"HTTP {r_channel.status_code} | ok=False | error: {ch_data.get('description')}"
    )
    result("Channel API success (HTTP 200 + ok=true)", ch_ok, ch_detail)
    result("Channel message_id returned", ch_msg_id is not None, f"message_id={ch_msg_id}")
except Exception as e:
    channel_ms = (time.perf_counter() - t0) * 1000
    result("Channel API success (HTTP 200 + ok=true)", False, str(e))
    result("Channel message_id returned", False, "Exception occurred")
    ch_ok = False

print(f"\n--- Sending to Private Chat ({private_id}) ---")
t1 = time.perf_counter()
try:
    r_priv = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": private_id, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=15,
    )
    priv_ms = (time.perf_counter() - t1) * 1000
    pr_data = r_priv.json()
    pr_ok = pr_data.get("ok", False)
    pr_msg_id = pr_data.get("result", {}).get("message_id") if pr_ok else None
    pr_detail = (
        f"HTTP {r_priv.status_code} | ok={pr_ok} | message_id={pr_msg_id} | {priv_ms:.0f}ms"
        if pr_ok
        else f"HTTP {r_priv.status_code} | error: {pr_data.get('description')}"
    )
    result("Private chat API success", pr_ok, pr_detail)
except Exception as e:
    priv_ms = (time.perf_counter() - t1) * 1000
    result("Private chat API success", False, str(e))
    pr_ok = False

# ─── Test B: send_alert() dual delivery ─────────────────────────
section("TEST B: TelegramNotifier.send_alert() Dual Delivery")
notifier = TelegramNotifier()
print(f"Channel configured: {notifier.is_channel_configured()}")
t2 = time.perf_counter()
overall_ok = notifier.send_alert(test_doc)
dual_ms = (time.perf_counter() - t2) * 1000
result("send_alert() dual delivery", overall_ok, f"{dual_ms:.0f}ms total")

# ─── Test C: Channel failure isolation ──────────────────────────
section("TEST C: Channel Failure Isolation (private chat must survive)")
from unittest.mock import patch, MagicMock
notifier2 = TelegramNotifier()
notifier2.channel_id = "@nonexistent_broken_channel_xyz999"

with patch("requests.post") as mock_post:
    def side_effect(url, **kwargs):
        resp = MagicMock()
        chat_id_val = str(kwargs.get("json", {}).get("chat_id", ""))
        if "broken_channel" in chat_id_val:
            resp.status_code = 400
            resp.json.return_value = {"ok": False, "description": "chat not found"}
        else:
            resp.status_code = 200
            resp.json.return_value = {"ok": True, "result": {"message_id": 999}}
        return resp
    mock_post.side_effect = side_effect
    isolation_ok = notifier2.send_alert(test_doc)

result("Channel failure does not kill private delivery", isolation_ok,
       "Private succeeded even when channel returned 400")

# ─── Summary ────────────────────────────────────────────────────
section("TEST A/B/C SUMMARY")
all_pass = all(v["status"] == "PASS" for v in RESULTS.values())
for name, res in RESULTS.items():
    icon = "✅" if res["status"] == "PASS" else "❌"
    print(f"  {icon} {name}: {res['status']}")

print(f"\nOverall channel+private delivery: {'✅ ALL PASS' if all_pass else '❌ FAILURES DETECTED'}")

# Save to file for reference
with open("channel_test_a_results.json", "w") as f:
    json.dump({
        "timestamp": datetime.now().isoformat(),
        "channel_id_tested": channel_id,
        "results": RESULTS,
        "all_pass": all_pass,
    }, f, indent=2)
print("\nResults saved to channel_test_a_results.json")
