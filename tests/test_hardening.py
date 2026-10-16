import os
import time
import pytest
import sqlite3
import pandas as pd
from unittest.mock import patch, MagicMock
from pathlib import Path

from app.config.settings import settings
from app.storage.db import DatabaseManager
from app.storage.excel_writer import ExcelWriter
from app.collectors.bse_collector import BSECollector
from app.collectors.nse_collector import NSECollector
from app.ingestion.extractor import extractor
from app.ai.local_llm import LocalLLMProvider
from app.notifications.telegram import TelegramNotifier
from app.main import ExchangeWatchDaemon

TEST_DATA_DIR = Path(__file__).parent / "test_scratch"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
TEST_DB_PATH = TEST_DATA_DIR / "test_hardening.db"
TEST_EXCEL_PATH = TEST_DATA_DIR / "test_hardening.xlsx"
TEST_CSV_PATH = TEST_DATA_DIR / "test_hardening.csv"

@pytest.fixture(autouse=True)
def clean_test_env():
    # Cleanup before test
    for p in [TEST_DB_PATH, TEST_EXCEL_PATH, TEST_CSV_PATH]:
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
    yield
    # Cleanup after test
    for p in [TEST_DB_PATH, TEST_EXCEL_PATH, TEST_CSV_PATH]:
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

def test_deduplication_and_restart_persistence():
    db = DatabaseManager(TEST_DB_PATH)
    ew = ExcelWriter(excel_path=TEST_EXCEL_PATH, csv_path=TEST_CSV_PATH)
    
    doc = {
        "doc_key": "TEST_DEDUP_001",
        "exchange": "BSE",
        "doc_id": "TEST_001",
        "title": "Deduplication Test Notice",
        "category": "Notice",
        "department": "Operations",
        "pub_date": "2026-10-01",
        "doc_url": "https://example.com/doc.pdf",
        "content_hash": "hash123",
        "priority": "HIGH",
        "effective_date": "01/10/2026",
        "summary": "Sample summary",
        "detected_at": "2026-10-01 10:00:00",
        "alert_sent": True
    }
    
    assert not db.is_processed("TEST_DEDUP_001")
    db.save_document(doc)
    ew.append_alert(doc)
    
    assert db.is_processed("TEST_DEDUP_001")
    df1 = pd.read_excel(TEST_EXCEL_PATH, sheet_name="Alerts")
    assert len(df1) == 1
    
    # Simulate restart by creating new manager instances on same file
    db_restarted = DatabaseManager(TEST_DB_PATH)
    ew_restarted = ExcelWriter(excel_path=TEST_EXCEL_PATH, csv_path=TEST_CSV_PATH)
    assert db_restarted.is_processed("TEST_DEDUP_001")
    
    # Attempt second append
    ew_restarted.append_alert(doc)
    df2 = pd.read_excel(TEST_EXCEL_PATH, sheet_name="Alerts")
    assert len(df2) == 1, "Excel writer must not append duplicate rows"

def test_source_network_failures_do_not_crash_collector():
    bse = BSECollector()
    nse = NSECollector()
    
    # Simulate BSE HTTP 503 failure
    with patch.object(bse.session, "get") as mock_bse_get:
        mock_bse_get.side_effect = Exception("503 Service Temporarily Unavailable")
        releases = bse.fetch_latest_releases()
        assert releases == [], "BSE collector must return empty list on network failure, not raise exception"

    # Simulate NSE HTTP timeout
    with patch.object(nse.session, "get") as mock_nse_get:
        mock_nse_get.side_effect = Exception("Connection Timeout")
        releases = nse.fetch_latest_releases()
        assert releases == [], "NSE collector must return empty list on network failure, not raise exception"

def test_one_failed_collector_does_not_stop_the_other():
    daemon = ExchangeWatchDaemon()
    
    mock_failing_collector = MagicMock()
    mock_failing_collector.exchange_name = "FAIL_EXCHANGE"
    mock_failing_collector.fetch_latest_releases.side_effect = RuntimeError("Fatal network crash on exchange 1")
    
    mock_healthy_collector = MagicMock()
    mock_healthy_collector.exchange_name = "HEALTHY_EXCHANGE"
    mock_healthy_collector.fetch_latest_releases.return_value = []
    
    daemon.collectors = [mock_failing_collector, mock_healthy_collector]
    
    # Running cycle should not raise RuntimeError and healthy collector must still be called
    daemon.run_cycle()
    mock_healthy_collector.fetch_latest_releases.assert_called_once()

def test_document_download_failure_falls_back_gracefully():
    daemon = ExchangeWatchDaemon()
    doc_key = f"TEST_DOWNLOAD_FAIL_{int(time.time()*1000)}"
    release = {
        "doc_key": doc_key,
        "exchange": "BSE",
        "doc_id": "ERR_404",
        "title": "Notice With Broken PDF Link",
        "category": "Notice",
        "department": "Listing",
        "pub_date": "2026-10-01",
        "doc_url": "https://broken.example.com/nonexistent.pdf",
        "filename": "nonexistent.pdf"
    }
    
    saved_docs = []

    def capture_save(doc_data):
        saved_docs.append(dict(doc_data))

    with patch("app.main.db_manager.is_processed", return_value=False), \
         patch("app.main.db_manager.save_document", side_effect=capture_save), \
         patch("app.main.excel_writer.append_alert"), \
         patch("app.main.telegram_notifier.send_alert", return_value=True), \
         patch("requests.get", side_effect=Exception("404 Not Found")):
        daemon.process_release(release)
        # After processing, summary must exist in the saved document
        assert len(saved_docs) == 1, "Document must be saved even when download fails"
        assert saved_docs[0].get("summary") is not None, "Summary must be populated from fallback"


def test_ollama_failure_safely_falls_back_to_fast_nlp():
    provider = LocalLLMProvider()

    # Point to nonexistent port to trigger connection error
    with patch.object(settings, "LOCAL_AI_URL", "http://localhost:99999/api/generate"):
        res = provider.analyze_document(
            title="Trading Suspension of XYZ Ltd for non-compliance",
            category="Suspension",
            content="Trading in securities of XYZ Ltd shall be suspended w.e.f. 15-10-2026."
        )
        # Fast NLP must take over and identify CRITICAL priority and exact date
        assert res["priority"] == "CRITICAL"
        assert "15-10-2026" in res["effective_date"]
        # Summary must be non-empty and contain the title text
        assert res["summary"] is not None and len(res["summary"]) > 0
        # analysis_mode must be FAST_NLP when fallback is used
        assert res["analysis_mode"] == "FAST_NLP"

def test_telegram_failure_does_not_crash_and_redacts_secrets():
    notifier = TelegramNotifier()
    notifier.bot_token = "SECRET_BOT_TOKEN_12345"
    notifier.chat_id = "12345678"
    # Disable channel to ensure exactly ONE logger.error call (private chat only)
    notifier.channel_enabled = False
    notifier.channel_id = ""

    doc = {
        "exchange": "BSE",
        "doc_id": "NOTIF_TEST",
        "department": "Operations",
        "title": "Alert Failure Test",
        "summary": "Testing telegram failure",
        "effective_date": "01/10/2026",
        "doc_url": "https://example.com"
    }

    # Simulate connection error exposing token in exception message
    with patch("requests.post") as mock_post:
        mock_post.side_effect = Exception("HTTPSConnectionPool: Max retries exceeded with url: /botSECRET_BOT_TOKEN_12345/sendMessage")
        with patch("app.notifications.telegram.logger.error") as mock_log_err:
            success = notifier.send_alert(doc)
            assert success is False
            mock_log_err.assert_called_once()
            logged_msg = mock_log_err.call_args[0][0]
            assert "SECRET_BOT_TOKEN_12345" not in logged_msg
            assert "[REDACTED_BOT_TOKEN]" in logged_msg


def test_date_preservation_deterministic():
    text = """
    NOTICE No. 20261001-99 Date: 01 Oct 2026
    Category: Trading Segment: Equity Department: Operations
    Subject: Change in Trading Hours w.e.f. 10/10/2026
    Effective window conducted from 10/10/2026 to 20/10/2026.
    """
    bse_meta = extractor.parse_bse_notice(text)
    assert bse_meta["notice_no"] == "20261001-99"
    assert bse_meta["notice_date"] == "01 Oct 2026"
    assert "10/10/2026" in bse_meta["effective_window"]

def test_gitignore_protects_secrets():
    gitignore_path = Path(__file__).parent.parent / ".gitignore"
    assert gitignore_path.exists(), ".gitignore must exist"
    content = gitignore_path.read_text(encoding="utf-8")
    assert ".env" in content
    assert "*.key" in content
    assert "*.pem" in content
    assert "*.db" in content
