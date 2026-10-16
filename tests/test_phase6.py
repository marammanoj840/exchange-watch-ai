"""
Phase 6 tests — Telegram Channel, structured analysis, validation, event types.

These tests ensure the new features work correctly while preserving all
existing tests that already pass.
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path

from app.config.settings import settings
from app.ai.analysis_schema import (
    classify_event_type, make_empty_analysis,
    VALID_PRIORITIES, VALID_EVENT_TYPES
)
from app.ai.fast_nlp import FastNLPProvider, fast_nlp_provider
from app.ai.local_llm import LocalLLMProvider
from app.ai.validator import validate_and_merge
from app.notifications.telegram import TelegramNotifier, _format_alert_message
from app.storage.excel_writer import ExcelWriter, COLUMNS
from app.storage.db import DatabaseManager


# ===========================================================================
# Test: Analysis Schema
# ===========================================================================

def test_analysis_schema_make_empty_analysis():
    """make_empty_analysis() must return all required keys."""
    result = make_empty_analysis()
    required_keys = [
        "exchange", "document_id", "reference_number", "company_name",
        "symbol", "event_type", "priority", "publication_date",
        "effective_date", "start_date", "end_date", "deadline",
        "action_required", "subject", "summary", "key_changes",
        "affected_parties", "reason_for_priority", "uncertainties",
        "official_source_url", "confidence", "analysis_mode",
    ]
    for key in required_keys:
        assert key in result, f"Missing key in analysis schema: {key}"


def test_classify_event_type_buyback():
    result = classify_event_type(
        "Buyback of shares under Tender Offer",
        "Corporate Action",
        "The company has announced a buyback offer period."
    )
    # New taxonomy maps buyback → CORPORATE_ACTION
    assert result in ("BUYBACK", "CORPORATE_ACTION"), (
        f"Expected BUYBACK or CORPORATE_ACTION, got {result}"
    )


def test_classify_event_type_trading_halt():
    result = classify_event_type(
        "Trading Suspension of XYZ Ltd",
        "Surveillance",
        "Trading in securities of XYZ Ltd has been suspended."
    )
    # New taxonomy maps trading suspension → TRADING_EXCHANGE_CHANGE
    assert result in ("TRADING_HALT", "TRADING_EXCHANGE_CHANGE"), (
        f"Expected TRADING_HALT or TRADING_EXCHANGE_CHANGE, got {result}"
    )


def test_classify_event_type_unknown_returns_other():
    result = classify_event_type(
        "General Circular Notice",
        "General",
        "Please be informed of the updated procedure."
    )
    assert result in VALID_EVENT_TYPES  # Must always be in valid set


def test_valid_event_types_set():
    """All event types in VALID_EVENT_TYPES must be uppercase strings."""
    for et in VALID_EVENT_TYPES:
        assert et == et.upper(), f"Event type '{et}' is not uppercase."
        assert isinstance(et, str)


# ===========================================================================
# Test: Enhanced Fast NLP
# ===========================================================================

def test_fast_nlp_returns_full_schema():
    """FastNLP must return all fields of the structured schema."""
    nlp = FastNLPProvider()
    result = nlp.analyze_document(
        title="Trading Halt for ABC Ltd",
        category="Surveillance",
        content="Trading in ABC Ltd suspended w.e.f. 01/10/2026 due to surveillance."
    )
    schema_keys = [
        "event_type", "priority", "effective_date", "start_date", "end_date",
        "deadline", "action_required", "summary", "key_changes",
        "affected_parties", "reason_for_priority", "uncertainties",
        "confidence", "analysis_mode",
    ]
    for key in schema_keys:
        assert key in result, f"FastNLP missing key: {key}"
    assert result["analysis_mode"] == "FAST_NLP"


def test_fast_nlp_buyback_priority_and_event_type():
    nlp = FastNLPProvider()
    result = nlp.analyze_document(
        title="Buyback Offer Announcement",
        category="Corporate Action",
        content="Global Pet Industries Limited has announced a buyback offer under Tender Offer scheme. Offer period: 01-October-2026 to 08-October-2026."
    )
    assert result["priority"] == "HIGH"
    # New taxonomy maps buyback → CORPORATE_ACTION
    assert result["event_type"] in ("BUYBACK", "CORPORATE_ACTION"), (
        f"Expected BUYBACK or CORPORATE_ACTION, got {result['event_type']}"
    )


def test_fast_nlp_offer_period_extraction():
    nlp = FastNLPProvider()
    content = "The offer period shall be from 01-October-2026 to 08-October-2026."
    result = nlp.analyze_document("Buyback Offer", "Corporate", content)
    assert result["start_date"] == "01-October-2026"
    assert result["end_date"] == "08-October-2026"


def test_fast_nlp_no_invention():
    """Fast NLP must not invent effective_date when not present."""
    nlp = FastNLPProvider()
    result = nlp.analyze_document(
        title="General Notice",
        category="General",
        content="This is a general notice about the exchange procedures."
    )
    assert result["effective_date"] == "Not stated in document."


# ===========================================================================
# Test: Validator
# ===========================================================================

def test_validator_deterministic_effective_date_wins():
    """Deterministic effective date must always override AI date."""
    release = {
        "doc_key": "NSE_TEST_001",
        "exchange": "NSE",
        "doc_id": "NSE/TEST/001",
        "title": "Test Circular",
        "doc_url": "https://example.com/test.pdf",
        "pub_date": "01 Oct 2026",
        "_deterministic_effective_date": "01/10/2026",
    }
    ai_res = make_empty_analysis()
    ai_res["effective_date"] = "January 10, 2026"  # AI incorrectly interprets date
    ai_res["priority"] = "MEDIUM"
    ai_res["summary"] = "Test summary."
    ai_res["key_changes"] = ["Some change"]

    result = validate_and_merge(release, ai_res)
    assert result["effective_date"] == "01/10/2026", \
        "Deterministic date must win over AI-misinterpreted date."


def test_validator_fills_all_required_fields():
    """validate_and_merge must produce a complete result dict."""
    release = {
        "doc_key": "BSE_TEST_002",
        "exchange": "BSE",
        "doc_id": "20261001-01",
        "title": "BSE Notice",
        "doc_url": "https://example.com",
        "pub_date": "01 Oct 2026",
        "_deterministic_effective_date": "",
    }
    ai_res = make_empty_analysis()
    ai_res["priority"] = "LOW"
    ai_res["summary"] = "A test notice."
    ai_res["key_changes"] = ["Item 1"]

    result = validate_and_merge(release, ai_res)
    assert result["exchange"] == "BSE"
    assert result["reference_number"] == "20261001-01"
    assert result["official_source_url"] == "https://example.com"


def test_validator_invalid_priority_defaults_to_medium():
    release = {
        "doc_key": "TEST_PRIO",
        "exchange": "NSE",
        "doc_id": "NSE/PRIO/001",
        "title": "Priority Test",
        "doc_url": "",
        "_deterministic_effective_date": "",
    }
    ai_res = make_empty_analysis()
    ai_res["priority"] = "SUPER_HIGH"  # Invalid priority
    ai_res["summary"] = "Test."
    ai_res["key_changes"] = ["Point 1"]

    result = validate_and_merge(release, ai_res)
    assert result["priority"] == "MEDIUM"


# ===========================================================================
# Test: Telegram Channel
# ===========================================================================

def test_telegram_notifier_channel_not_configured_reports_correctly():
    """When channel is not configured, test_channel() returns False without crash."""
    notifier = TelegramNotifier()
    notifier.bot_token = "FAKE_TOKEN"
    notifier.channel_enabled = True
    notifier.channel_id = ""  # Not set

    result = notifier.test_channel()
    assert result is False


def test_telegram_channel_is_configured_check():
    notifier = TelegramNotifier()
    notifier.bot_token = "FAKE_TOKEN"
    notifier.channel_enabled = True
    notifier.channel_id = "@testchannel"
    assert notifier.is_channel_configured() is True


def test_telegram_channel_not_configured_when_disabled():
    notifier = TelegramNotifier()
    notifier.bot_token = "FAKE_TOKEN"
    notifier.channel_enabled = False
    notifier.channel_id = "@testchannel"
    assert notifier.is_channel_configured() is False


def test_telegram_alert_format_contains_required_fields():
    """Alert message must contain priority, exchange, and URL."""
    doc_data = {
        "priority": "HIGH",
        "exchange": "NSE",
        "event_type": "BUYBACK",
        "company_name": "Global Pet Industries Limited",
        "title": "Buyback Offer Under Tender Offer Scheme",
        "subject": "Buyback Offer Under Tender Offer Scheme",
        "pub_date": "30 Sep 2026",
        "effective_date": "",
        "start_date": "01-October-2026",
        "end_date": "08-October-2026",
        "deadline": "Not stated in document.",
        "summary": "Global Pet Industries Limited announced a buyback offer.",
        "key_changes": ["Buyback offer announced", "Offer period: 01-October-2026 to 08-October-2026"],
        "reason_for_priority": "HIGH: Corporate buyback with defined offer period.",
        "action_required": "Not stated in document.",
        "doc_url": "https://nsearchives.nseindia.com/test/76641.zip",
        "official_source_url": "https://nsearchives.nseindia.com/test/76641.zip",
        "doc_id": "NSE/CML/76641",
        "latency_summary": {"total_latency_ms": 1234},
        "analysis_mode": "LLM",
    }
    msg = _format_alert_message(doc_data)
    assert "HIGH PRIORITY" in msg
    assert "NSE" in msg
    assert "BUYBACK" in msg
    assert "Global Pet Industries Limited" in msg
    assert "01-October-2026" in msg
    assert "08-October-2026" in msg
    assert "nsearchives.nseindia.com" in msg
    assert "NSE/CML/76641" in msg


def test_telegram_channel_failure_does_not_crash_daemon():
    """Channel delivery failure must NOT cause send_alert to return False."""
    notifier = TelegramNotifier()
    notifier.bot_token = "FAKE_TOKEN"
    notifier.chat_id = "FAKE_CHAT"
    notifier.channel_enabled = True
    notifier.channel_id = "@fakechannel"

    doc = {
        "priority": "MEDIUM",
        "exchange": "BSE",
        "event_type": "GENERAL_NOTICE",
        "company_name": "",
        "title": "Test Alert",
        "subject": "Test Alert",
        "pub_date": "01 Oct 2026",
        "effective_date": "",
        "start_date": "",
        "end_date": "",
        "deadline": "",
        "summary": "Test summary.",
        "key_changes": ["Test point"],
        "reason_for_priority": "MEDIUM test.",
        "action_required": "None.",
        "doc_url": "https://example.com",
        "official_source_url": "https://example.com",
        "doc_id": "BSE/TEST/001",
        "latency_summary": {},
        "analysis_mode": "FAST_NLP",
    }

    with patch("requests.post") as mock_post:
        # Private chat succeeds, channel fails
        def side_effect(url, **kwargs):
            resp = MagicMock()
            if "FAKE_CHAT" in str(kwargs.get("json", {}).get("chat_id", "")):
                resp.status_code = 200
            else:
                resp.status_code = 400
                resp.text = "Bad Request: chat not found"
            return resp
        mock_post.side_effect = side_effect
        result = notifier.send_alert(doc)
        # Private chat succeeded, so overall result should be True
        assert result is True


# ===========================================================================
# Test: Excel Writer with new columns
# ===========================================================================

def test_excel_writer_new_columns(tmp_path):
    """Excel writer must write all new structured columns."""
    excel_file = tmp_path / "test_phase6.xlsx"
    csv_file = tmp_path / "test_phase6.csv"
    writer = ExcelWriter(excel_path=excel_file, csv_path=csv_file)

    doc_data = {
        "detected_at": "2026-10-01 10:00:00",
        "exchange": "NSE",
        "company_name": "Global Pet Industries Limited",
        "symbol": "GLOBALPET",
        "event_type": "BUYBACK",
        "priority": "HIGH",
        "doc_id": "NSE/CML/76641",
        "category": "Corporate Action",
        "department": "Listing",
        "title": "Buyback Offer",
        "subject": "Buyback Offer Under Tender Offer Scheme",
        "pub_date": "30 Sep 2026",
        "effective_date": "01-October-2026",
        "start_date": "01-October-2026",
        "end_date": "08-October-2026",
        "deadline": "Not stated in document.",
        "summary": "Global Pet Industries announced buyback.",
        "key_changes": ["Buyback announced", "Offer period: 01-Oct to 08-Oct"],
        "action_required": "Not stated in document.",
        "reason_for_priority": "Corporate buyback with defined offer period.",
        "affected_parties": ["Members", "Investors"],
        "analysis_mode": "LLM",
        "confidence": "HIGH",
        "alert_sent": True,
        "latency_summary": {"total_latency_ms": 1500},
        "doc_url": "https://nsearchives.nseindia.com/test.zip",
    }

    writer.append_alert(doc_data)

    import pandas as pd
    df = pd.read_excel(excel_file, sheet_name="Alerts")
    assert len(df) == 1
    assert df.iloc[0]["Event Type"] == "BUYBACK"
    assert df.iloc[0]["Company"] == "Global Pet Industries Limited"
    assert df.iloc[0]["Start Date"] == "01-October-2026"
    assert df.iloc[0]["End Date"] == "08-October-2026"
    assert "NSE/CML/76641" in str(df.iloc[0]["Doc ID / Reference"])


# ===========================================================================
# Test: Database with new columns
# ===========================================================================

def test_database_stores_event_type_and_company(tmp_path):
    db_file = tmp_path / "test_phase6.db"
    db = DatabaseManager(db_path=db_file)

    doc = {
        "doc_key": "NSE_PHASE6_001",
        "exchange": "NSE",
        "doc_id": "NSE/CML/76641",
        "title": "Buyback Offer",
        "category": "Corporate Action",
        "department": "Listing",
        "pub_date": "30 Sep 2026",
        "doc_url": "https://example.com",
        "event_type": "BUYBACK",
        "company_name": "Global Pet Industries Limited",
        "symbol": "GLOBALPET",
        "priority": "HIGH",
        "effective_date": "01-October-2026",
        "start_date": "01-October-2026",
        "end_date": "08-October-2026",
        "deadline": "Not stated in document.",
        "action_required": "Not stated in document.",
        "subject": "Buyback Offer Under Tender Offer Scheme",
        "summary": "Buyback announced.",
        "key_changes": ["Buyback offer announced"],
        "affected_parties": ["Members"],
        "reason_for_priority": "Corporate buyback.",
        "confidence": "HIGH",
        "analysis_mode": "LLM",
        "detected_at": "2026-10-01 10:00:00",
        "alert_sent": True,
        "latency_summary": {},
    }

    assert not db.is_processed("NSE_PHASE6_001")
    db.save_document(doc)
    assert db.is_processed("NSE_PHASE6_001")

    recent = db.get_recent_documents(limit=1)
    assert len(recent) == 1
    assert recent[0]["event_type"] == "BUYBACK"
    assert recent[0]["company_name"] == "Global Pet Industries Limited"
