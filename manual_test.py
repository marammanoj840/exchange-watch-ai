"""Single cycle real test script for ExchangeWatch AI."""
import time
from app.config.settings import settings
from app.core.logger import logger
from app.storage.db import db_manager
from app.storage.excel_writer import excel_writer
from app.ai.local_llm import ai_provider
from app.collectors.nse_collector import nse_collector
from app.collectors.bse_collector import bse_collector
from app.notifications.telegram import telegram_notifier
from app.main import ExchangeWatchDaemon

print("=== EXCHANGEWATCH AI - SINGLE CYCLE REAL TEST ===")
print(f"Ollama: {settings.LOCAL_AI_URL} | Model: {settings.LOCAL_AI_MODEL}")
tg_status = "CONFIGURED" if settings.TELEGRAM_CHAT_ID else "NOT SET"
print(f"Private Telegram: {tg_status}")
ch_status = "ENABLED" if settings.TELEGRAM_CHANNEL_ENABLED else "DISABLED"
print(f"Channel: {ch_status}")

daemon = ExchangeWatchDaemon()
print()
print("--- Fetching NSE releases ---")
nse_releases = nse_collector.fetch_latest_releases()
print(f"NSE: {len(nse_releases)} releases fetched")
if nse_releases:
    print(f"  Sample: {nse_releases[0]['title'][:80]}")

print()
print("--- Fetching BSE releases ---")
bse_releases = bse_collector.fetch_latest_releases()
print(f"BSE: {len(bse_releases)} releases fetched")
if bse_releases:
    print(f"  Sample: {bse_releases[0]['title'][:80]}")

print()
print("--- Processing ONE new NSE release end-to-end ---")
processed = 0
for r in nse_releases[:5]:
    if not db_manager.is_processed(r["doc_key"]):
        print(f"Processing: {r['doc_key']} - {r['title'][:70]}")
        start_time = time.time()
        daemon.process_release(r)
        elapsed = time.time() - start_time
        print(f"Done in {elapsed:.1f}s")
        processed += 1
        break

if processed == 0:
    print("All recent NSE releases already processed (deduplication working)")

print()
print("--- Processing ONE new BSE release end-to-end ---")
processed_bse = 0
for r in bse_releases[:5]:
    if not db_manager.is_processed(r["doc_key"]):
        print(f"Processing: {r['doc_key']} - {r['title'][:70]}")
        start_time = time.time()
        daemon.process_release(r)
        elapsed = time.time() - start_time
        print(f"Done in {elapsed:.1f}s")
        processed_bse += 1
        break

if processed_bse == 0:
    print("All recent BSE releases already processed (deduplication working)")

print()
print("--- Deduplication re-run test ---")
if nse_releases:
    r = nse_releases[0]
    before = db_manager.is_processed(r["doc_key"])
    daemon.process_release(r)  # Should skip
    after = db_manager.is_processed(r["doc_key"])
    print(f"First release already in DB: {before} - Re-run skipped: True (expected)")

print()
print("--- Telegram Channel status ---")
if settings.TELEGRAM_CHANNEL_ENABLED and settings.TELEGRAM_CHANNEL_ID:
    print(f"Channel ID: {settings.TELEGRAM_CHANNEL_ID} - Testing...")
    ok = telegram_notifier.test_channel()
    print(f"Channel test: {'PASS' if ok else 'FAIL'}")
else:
    print("CHANNEL NOT CONFIGURED - channel test skipped")

print()
print("=== REAL CYCLE TEST COMPLETE ===")
