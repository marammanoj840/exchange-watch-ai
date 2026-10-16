"""
ExchangeWatch AI — Main Daemon

Architecture:
  NSE/BSE Collectors
    → Deduplication (SQLite)
    → Document download
    → Text extraction
    → Deterministic fact extraction
    → Local Ollama AI analysis (with Fast NLP fallback)
    → Importance classification (taxonomy + scoring)
    → Validation (deterministic values override AI)
    → Publication policy filter
    → Structured alert
        ├── SQLite (all processed documents, regardless of publication)
        ├── Excel
        ├── Private Telegram bot/chat (important events only)
        └── Telegram Channel (important events only)
"""
import time
import requests
from typing import Dict, Any
from app.config.settings import settings
from app.core.logger import logger
from app.core.latency_tracker import LatencyTracker
from app.storage.db import db_manager
from app.storage.excel_writer import excel_writer
from app.ingestion.extractor import extractor
from app.ai.local_llm import ai_provider
from app.ai.validator import validate_and_merge
from app.ai.importance import compute_importance
from app.collectors.nse_collector import nse_collector
from app.collectors.bse_collector import bse_collector
from app.notifications.telegram import telegram_notifier


class ExchangeWatchDaemon:
    def __init__(self):
        self.collectors = [nse_collector, bse_collector]

    def process_release(self, release: Dict[str, Any]) -> None:
        doc_key = release["doc_key"]
        existing = db_manager.get_document(doc_key)
        is_revision = False

        # 1. Deduplication check — distinguish exact duplicates from revisions
        if existing:
            title_curr = release.get("title", "").strip()
            title_prev = existing.get("title", "").strip()
            title_changed = title_curr != title_prev

            if title_changed:
                is_revision = True
                logger.info(f"🔄 Revision indicator detected for {doc_key}: '{title_prev}' -> '{title_curr}'")
            elif existing.get("content_hash") or existing.get("alert_sent"):
                # Exact duplicate already processed — skip immediately
                return


        tracker = LatencyTracker(doc_key)
        logger.info(
            f"🚨 New release detected from {release['exchange']}: "
            f"{release['title']} ({doc_key})"
        )

        # 2. Document download & text extraction
        tracker.record("download_started_at")
        content_text = release["title"]  # fallback if download fails
        content_hash = ""
        doc_url = release.get("doc_url", "")

        if doc_url:
            try:
                res = requests.get(doc_url, timeout=12, headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36"
                    )
                })
                if res.status_code == 200:
                    tracker.record("download_completed_at")
                    tracker.record("extraction_started_at")
                    extracted_text, content_hash = extractor.extract_text(
                        res.content, release.get("filename", "")
                    )
                    if extracted_text.strip():
                        content_text = extracted_text
                    tracker.record("extraction_completed_at")
                else:
                    logger.warning(
                        f"Document download returned HTTP {res.status_code} "
                        f"for {doc_url}. Using title as fallback content."
                    )
            except Exception as e:
                logger.warning(
                    f"Could not download document from {doc_url}: {e}. "
                    "Using title as fallback content."
                )

        # Content hash check for existing documents without title change
        if existing and not is_revision:
            if content_hash and existing.get("content_hash") and content_hash != existing.get("content_hash"):
                is_revision = True
                logger.info(f"🔄 Document content hash changed for {doc_key}. Processing revision.")
            else:
                # Content hash is identical, skip exact duplicate
                logger.debug(f"Document {doc_key} already processed with identical hash. Skipping.")
                return

        release["is_revision"] = is_revision

        # 3. Deterministic metadata extraction
        # These values ALWAYS override AI output
        deterministic_effective_date = ""

        if release.get("exchange") == "BSE":
            bse_meta = extractor.parse_bse_notice(content_text)
            if bse_meta.get("notice_no"):
                release["doc_id"] = bse_meta["notice_no"]
            if bse_meta.get("notice_date"):
                release["pub_date"] = bse_meta["notice_date"]
            if bse_meta.get("category"):
                release["category"] = bse_meta["category"]
            if bse_meta.get("department"):
                release["department"] = bse_meta["department"]
            if bse_meta.get("effective_window"):
                deterministic_effective_date = bse_meta["effective_window"]
            elif bse_meta.get("important_dates"):
                deterministic_effective_date = ", ".join(bse_meta["important_dates"][:2])

        elif release.get("exchange") == "NSE":
            nse_meta = extractor.parse_nse_circular(content_text)
            if nse_meta.get("download_ref_no"):
                release["doc_id"] = nse_meta["download_ref_no"]
            if nse_meta.get("department"):
                release["department"] = nse_meta["department"]
            if nse_meta.get("effective_date"):
                deterministic_effective_date = nse_meta["effective_date"]
            elif nse_meta.get("important_dates"):
                deterministic_effective_date = ", ".join(nse_meta["important_dates"][:2])

        # Store deterministic date with underscore prefix for validator
        release["_deterministic_effective_date"] = deterministic_effective_date

        # 4. Importance & Taxonomy classification (deterministic first)
        tracker.record("classification_started_at")
        importance = compute_importance(
            release=release,
            content_text=content_text
        )
        tracker.record("classification_completed_at")

        # 5. AI Analysis (Fast NLP default path; selective Local LLM for ambiguous filings)
        tracker.record("ai_started_at")
        use_llm = False
        processing_mode = getattr(settings, "AI_PROCESSING_MODE", "FAST_NLP_FIRST")

        if getattr(settings, "LOCAL_AI_ENABLED", True):
            if processing_mode == "ALWAYS_LLM":
                use_llm = True
            elif processing_mode == "FAST_NLP_FIRST" and getattr(settings, "LOCAL_AI_SELECTIVE", True):
                # Selective Ollama: Only invoke for ambiguous or borderline disclosures,
                # NEVER for obvious routine filings or clear-cut default/insolvencies.
                is_ambiguous = (
                    importance["event_type"] == "MATERIAL_DISCLOSURE" or
                    (35 <= importance["importance_score"] <= 65 and not importance["is_routine"])
                )
                if is_ambiguous:
                    use_llm = True

        if use_llm:
            ai_res = ai_provider.analyze_document(
                title=release["title"],
                category=release.get("category", ""),
                content=content_text
            )
        else:
            # Deterministic / Fast NLP default path (<5ms)
            from app.ai.fast_nlp import fast_nlp_provider
            ai_res = fast_nlp_provider.analyze_document(
                title=release["title"],
                category=release.get("category", ""),
                content=content_text
            )
        tracker.record("ai_completed_at")

        # Merge importance results into ai_res (importance wins over raw AI output)
        ai_res["event_type"] = importance["event_type"]
        ai_res["priority"] = importance["priority"]
        ai_res["reason_for_priority"] = importance["reason_for_priority"]
        ai_res["key_facts"] = importance.get("key_facts", [])
        ai_res["materiality_evidence"] = importance.get("materiality_evidence", {})
        ai_res["importance_score"] = importance["importance_score"]
        ai_res["should_publish"] = importance["should_publish"]
        ai_res["is_routine"] = importance["is_routine"]

        # 6. Validate & merge — deterministic values win
        release["content_hash"] = content_hash
        release["detected_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

        final_doc = validate_and_merge(release, ai_res)

        # Carry importance fields into final_doc
        final_doc["importance_score"] = importance["importance_score"]
        final_doc["should_publish"] = importance["should_publish"]
        final_doc["is_routine"] = importance["is_routine"]
        final_doc["key_facts"] = importance.get("key_facts", [])
        final_doc["materiality_evidence"] = importance.get("materiality_evidence", {})
        final_doc["is_revision"] = is_revision
        final_doc["is_duplicate"] = False

        # Cross-exchange deduplication check
        cross_match = db_manager.find_cross_exchange_duplicate(
            exchange=release.get("exchange", ""),
            content_hash=content_hash,
            company_name=final_doc.get("company_name", ""),
            title=release.get("title", "")
        )
        if cross_match:
            final_doc["is_duplicate"] = True
            final_doc["cross_exchange_ref"] = cross_match.get("doc_key", "")
            if release.get("exchange") == "NSE":
                final_doc["nse_source_url"] = release.get("doc_url", "")
                final_doc["bse_source_url"] = cross_match.get("doc_url", "") or cross_match.get("official_source_url", "")
            else:
                final_doc["bse_source_url"] = release.get("doc_url", "")
                final_doc["nse_source_url"] = cross_match.get("doc_url", "") or cross_match.get("official_source_url", "")

        # 7. Publication policy filter
        should_publish = final_doc.get("should_publish", False)
        priority = final_doc.get("priority", "LOW")

        # If already alerted via another exchange, suppress duplicate Telegram alert
        if cross_match and cross_match.get("alert_sent"):
            should_publish = False
            logger.info(
                f"🔗 Cross-exchange match found with {cross_match.get('doc_key')}. "
                "Alert already published on primary exchange; suppressing duplicate alert."
            )

        # Never suppress CRITICAL events unless duplicate
        if priority == "CRITICAL" and not (cross_match and cross_match.get("alert_sent")):
            should_publish = True

        alert_sent = False

        # 8. Alert dispatch (only for events that pass publication policy)
        tracker.record("notification_started_at")
        if should_publish:
            alert_sent = telegram_notifier.send_alert(final_doc)
            tracker.record("notification_sent_at")
            if not alert_sent:
                logger.warning(
                    f"⚠️ Telegram alert dispatch failed for {doc_key}. "
                    "Recorded with alert_sent=0."
                )
        else:
            tracker.record("notification_sent_at")
            logger.info(
                f"📭 {doc_key} suppressed by publication policy "
                f"(priority={priority}, score={importance['importance_score']}, "
                f"routine={importance['is_routine']})"
            )
        tracker.record("alert_sent_at")

        final_doc["alert_sent"] = alert_sent
        tracker.record("finished_at")
        final_doc["latency_summary"] = tracker.get_summary()

        # 9. Persist to SQLite and Excel (ALL processed documents, not just published)
        tracker.record("storage_started_at")
        db_manager.save_document(final_doc)
        excel_writer.append_alert(final_doc)
        tracker.record("storage_completed_at")

        total_ms = final_doc["latency_summary"].get("total_latency_ms", 0)
        logger.info(
            f"✅ Finished processing {doc_key} | "
            f"event_type={final_doc.get('event_type')} | "
            f"priority={final_doc.get('priority')} | "
            f"score={importance['importance_score']} | "
            f"published={'YES' if alert_sent else ('SUPPRESSED' if not should_publish else 'FAILED')} | "
            f"{total_ms:.0f}ms total"
        )


    def retry_pending_alerts(self) -> None:
        """Retry any alerts that were flagged for publication but failed to deliver."""
        pending = db_manager.get_pending_alerts(limit=5)
        for doc in pending:
            doc_key = doc.get("doc_key")
            logger.info(f"🔁 Retrying unsent alert for {doc_key}: '{doc.get('title')}'")
            try:
                sent = telegram_notifier.send_alert(doc)
                if sent:
                    db_manager.mark_alert_sent(doc_key, True)
                    logger.info(f"✅ Pending alert for {doc_key} delivered on retry.")
                    time.sleep(1.0)
                else:
                    logger.warning(f"⚠️ Retry delivery failed for {doc_key}. Will retry on next cycle.")
                    break
            except Exception as e:
                logger.error(f"Error retrying alert {doc_key}: {e}")
                break

    def run_cycle(self) -> None:
        for collector in self.collectors:
            try:
                releases = collector.fetch_latest_releases()
                db_manager.update_source_status(collector.exchange_name, "OK")
                for release in releases:
                    try:
                        self.process_release(release)
                    except Exception as e:
                        logger.error(
                            f"Error processing release {release.get('doc_key')}: {e}"
                        )
            except Exception as e:
                logger.error(
                    f"Error in {collector.exchange_name} collector loop: {e}"
                )
                db_manager.update_source_status(
                    collector.exchange_name, "ERROR", str(e)
                )

        # Retry any previously failed deliveries
        self.retry_pending_alerts()

    def start_247(self) -> None:
        logger.info("=" * 54)
        logger.info("🚀 EXCHANGEWATCH AI DAEMON STARTED")
        logger.info(f"   Polling Interval : {settings.POLL_INTERVAL_SECONDS}s")
        logger.info(f"   Local AI Enabled : {settings.LOCAL_AI_ENABLED}")
        logger.info(f"   AI Model         : {settings.LOCAL_AI_MODEL}")
        logger.info(f"   Database         : {settings.DATABASE_PATH}")
        logger.info(f"   Excel            : {settings.EXCEL_OUTPUT_PATH}")
        logger.info(f"   Private Chat     : {'✅' if settings.TELEGRAM_CHAT_ID else '❌ NOT SET'}")
        channel_status = "✅" if settings.TELEGRAM_CHANNEL_ENABLED and settings.TELEGRAM_CHANNEL_ID else "❌ NOT CONFIGURED"
        logger.info(f"   Channel          : {channel_status}")
        logger.info("=" * 54)

        # Self-test channel if enabled
        if settings.TELEGRAM_CHANNEL_ENABLED:
            if settings.TELEGRAM_CHANNEL_ID:
                logger.info("Testing Telegram Channel connectivity...")
                telegram_notifier.test_channel()
            else:
                logger.warning(
                    "TELEGRAM_CHANNEL_ENABLED=true but TELEGRAM_CHANNEL_ID is not set. "
                    "Add TELEGRAM_CHANNEL_ID to .env to enable channel posting."
                )

        while True:
            try:
                self.run_cycle()
            except KeyboardInterrupt:
                logger.info("🛑 ExchangeWatch daemon stopped gracefully.")
                break
            except Exception as e:
                logger.critical(f"Unhandled exception in daemon cycle: {e}")

            try:
                time.sleep(settings.POLL_INTERVAL_SECONDS)
            except KeyboardInterrupt:
                logger.info("🛑 ExchangeWatch daemon stopped gracefully.")
                break


if __name__ == "__main__":
    daemon = ExchangeWatchDaemon()
    daemon.start_247()
