"""
End-to-End Pipeline Verification for ExchangeWatch AI (Phase 5).

Verifies the complete pipeline from fixture to delivery state:
  Official-document fixture
  → extraction
  → deterministic metadata
  → event classification
  → importance filtering
  → AI analysis or fallback
  → output validation
  → deduplication
  → Telegram message formatting
  → mocked delivery
  → stored delivery state
"""

import pytest
import sqlite3
import pandas as pd
from unittest.mock import patch, MagicMock
from pathlib import Path

from app.storage.db import DatabaseManager
from app.storage.excel_writer import ExcelWriter
from app.main import ExchangeWatchDaemon
from app.notifications.telegram import _format_alert_message


from app.config.settings import settings

@pytest.fixture
def test_env(tmp_path):
    db_path = tmp_path / "e2e_test.db"
    excel_path = tmp_path / "e2e_test.xlsx"
    csv_path = tmp_path / "e2e_test.csv"
    db = DatabaseManager(db_path=db_path)
    ew = ExcelWriter(excel_path=excel_path, csv_path=csv_path)
    daemon = ExchangeWatchDaemon()
    with patch.object(settings, "LOCAL_AI_ENABLED", False):
        yield {
            "db": db,
            "ew": ew,
            "daemon": daemon,
            "db_path": db_path,
            "excel_path": excel_path,
        }


def test_e2e_important_event_produces_alert(test_env):
    """An important event (Statutory Auditor resignation) must produce alert and be delivered."""
    daemon = test_env["daemon"]
    db = test_env["db"]
    ew = test_env["ew"]

    release = {
        "doc_key": "E2E_AUDITOR_001",
        "exchange": "NSE",
        "doc_id": "NSE/CML/99001",
        "title": "Resignation of Statutory Auditor",
        "category": "Corporate",
        "department": "Listing",
        "pub_date": "14 Oct 2026",
        "doc_url": "https://nsearchives.nseindia.com/e2e/aud.zip",
        "filename": "aud.zip",
    }
    fixture_content = (
        "M/s Sharp & Associates, Statutory Auditors of ABC Infra Limited, "
        "have tendered their resignation citing material audit qualification in revenue recognition."
    )

    sent_alerts = []

    def mock_send_alert(doc_data):
        sent_alerts.append(dict(doc_data))
        return True

    with patch("app.main.db_manager", db), \
         patch("app.main.excel_writer", ew), \
         patch("app.main.telegram_notifier.send_alert", side_effect=mock_send_alert), \
         patch("app.main.settings.LOCAL_AI_ENABLED", False), \
         patch("requests.get") as mock_get:
        # Mock document download
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = fixture_content.encode("utf-8")
        mock_get.return_value = mock_resp

        daemon.process_release(release)

    # Verify alert was sent to Telegram
    assert len(sent_alerts) == 1
    alert = sent_alerts[0]
    assert alert["event_type"] == "AUDITOR_CHANGE"
    assert alert["priority"] in ("HIGH", "CRITICAL")

    # Verify persisted in SQLite with alert_sent=1
    saved = db.get_document("E2E_AUDITOR_001")
    assert saved is not None
    assert saved["alert_sent"] == 1
    assert saved["event_type"] == "AUDITOR_CHANGE"


def test_e2e_routine_event_is_suppressed(test_env):
    """A routine notice must be processed into SQLite/Excel but suppressed from Telegram."""
    daemon = test_env["daemon"]
    db = test_env["db"]
    ew = test_env["ew"]

    release = {
        "doc_key": "E2E_ROUTINE_002",
        "exchange": "BSE",
        "doc_id": "BSE/OPS/88002",
        "title": "Schedule of Mock Trading Session and System Maintenance",
        "category": "Notice",
        "department": "Market Operations",
        "pub_date": "14 Oct 2026",
        "doc_url": "https://www.bseindia.com/notices/88002.pdf",
        "filename": "88002.pdf",
    }
    fixture_content = "Exchange announces mock trading session on Saturday. General circular."

    sent_alerts = []

    with patch("app.main.db_manager", db), \
         patch("app.main.excel_writer", ew), \
         patch("app.main.telegram_notifier.send_alert", side_effect=lambda d: sent_alerts.append(d)), \
         patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = fixture_content.encode("utf-8")
        mock_get.return_value = mock_resp

        daemon.process_release(release)

    # Telegram must NOT have received any alert
    assert len(sent_alerts) == 0

    # But document is recorded in DB as processed and suppressed
    saved = db.get_document("E2E_ROUTINE_002")
    assert saved is not None
    assert saved["alert_sent"] == 0
    assert saved["event_type"] == "ROUTINE_LOW_PRIORITY"


def test_e2e_failed_delivery_is_never_marked_as_sent(test_env):
    """When Telegram dispatch fails, alert_sent must remain 0."""
    daemon = test_env["daemon"]
    db = test_env["db"]
    ew = test_env["ew"]

    release = {
        "doc_key": "E2E_FAIL_003",
        "exchange": "NSE",
        "doc_id": "NSE/CML/77003",
        "title": "Debt Default Notice",
        "category": "Corporate",
        "pub_date": "14 Oct 2026",
        "doc_url": "",
    }

    with patch("app.main.db_manager", db), \
         patch("app.main.excel_writer", ew), \
         patch("app.main.telegram_notifier.send_alert", return_value=False):
        daemon.process_release(release)

    saved = db.get_document("E2E_FAIL_003")
    assert saved is not None
    assert saved["alert_sent"] == 0, "Failed delivery must NEVER be marked as sent"


def test_e2e_reprocessing_same_document_does_not_duplicate(test_env):
    """Reprocessing an identical document must exit early without sending duplicate alert."""
    daemon = test_env["daemon"]
    db = test_env["db"]
    ew = test_env["ew"]

    release = {
        "doc_key": "E2E_DEDUP_004",
        "exchange": "BSE",
        "doc_id": "20261014-99",
        "title": "Corporate Action Interim Dividend",
        "category": "Corporate",
        "pub_date": "14 Oct 2026",
        "doc_url": "",
    }

    sent_count = 0

    def mock_send(d):
        nonlocal sent_count
        sent_count += 1
        return True

    with patch("app.main.db_manager", db), \
         patch("app.main.excel_writer", ew), \
         patch("app.main.telegram_notifier.send_alert", side_effect=mock_send):
        # First processing
        daemon.process_release(release)
        # Second processing (identical)
        daemon.process_release(release)

    assert sent_count <= 1, "Duplicate processing must not send duplicate alerts"


def test_e2e_revision_is_processed_and_not_discarded(test_env):
    """A revised document with title modification must be processed."""
    daemon = test_env["daemon"]
    db = test_env["db"]
    ew = test_env["ew"]

    initial_release = {
        "doc_key": "E2E_REV_005",
        "exchange": "NSE",
        "doc_id": "NSE/REV/005",
        "title": "Outcome of Board Meeting",
        "category": "Corporate",
        "pub_date": "14 Oct 2026",
        "doc_url": "",
    }
    revised_release = {
        "doc_key": "E2E_REV_005",
        "exchange": "NSE",
        "doc_id": "NSE/REV/005",
        "title": "Corrigendum and Revised Outcome of Board Meeting",
        "category": "Corporate",
        "pub_date": "14 Oct 2026",
        "doc_url": "",
    }

    with patch("app.main.db_manager", db), \
         patch("app.main.excel_writer", ew), \
         patch("app.main.telegram_notifier.send_alert", return_value=True):
        daemon.process_release(initial_release)
        daemon.process_release(revised_release)

    saved = db.get_document("E2E_REV_005")
    assert saved is not None
    assert "Revised" in saved["title"] or "Corrigendum" in saved["title"]
    assert saved["is_revision"] == 1
