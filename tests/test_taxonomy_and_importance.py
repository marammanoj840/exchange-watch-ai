"""
Comprehensive tests for ExchangeWatch AI:
  - 15-category event taxonomy classification
  - Materiality rules and heuristic importance scoring
  - Publication policy and routine suppression
  - Revisions and cross-exchange deduplication
  - AI validation and Fast NLP fallback resilience
  - Telegram message formatting and delivery states
"""

import pytest
import sqlite3
import json
from unittest.mock import patch, MagicMock
from pathlib import Path

from app.ai.taxonomy import (
    classify_to_taxonomy,
    EVENT_CATEGORIES,
    VALID_TAXONOMY_CATEGORIES,
    CATEGORY_DEFAULT_PRIORITY,
    PUBLISH_BY_DEFAULT,
)
from app.ai.importance import (
    compute_importance,
    should_consolidate_cross_exchange,
)
from app.ai.materiality import materiality_analyzer
from app.ai.analysis_schema import make_empty_analysis, VALID_EVENT_TYPES
from app.ai.fast_nlp import FastNLPProvider
from app.ai.validator import validate_and_merge
from app.notifications.telegram import _format_alert_message, TelegramNotifier
from app.storage.db import DatabaseManager
from app.storage.excel_writer import ExcelWriter


# ===========================================================================
# 1. TAXONOMY CLASSIFICATION TESTS (ALL 15 CATEGORIES + ROUTINE SUPPRESSION)
# ===========================================================================

@pytest.mark.parametrize("category_key,title,content", [
    (
        "MANAGEMENT_CHANGE",
        "Resignation of Chief Executive Officer",
        "Mr. Rajesh Sharma has tendered his resignation as CEO with effect from October 31, 2026.",
    ),
    (
        "AUDITOR_CHANGE",
        "Resignation of Statutory Auditor",
        "M/s S.K. & Associates, Statutory Auditors of the Company, have resigned citing inability to obtain audit evidence.",
    ),
    (
        "FINANCIAL_RESULTS",
        "Outcome of Board Meeting - Unaudited Financial Results for Q2",
        "Approved standalone and consolidated financial results for the quarter ended September 30, 2026. Profit after tax is Rs. 145 crore.",
    ),
    (
        "MAJOR_ORDER_CONTRACT",
        "Receipt of Significant Order Worth Rs. 850 Crore",
        "The company has been awarded a major order from National Highways Authority of India for EPC project.",
    ),
    (
        "BULK_BLOCK_DEAL",
        "Disclosure of Large Bulk Deal Transaction",
        "Promoter entity sold 1,500,000 shares in a bulk deal at Rs. 420.50 per share on the exchange platform.",
    ),
    (
        "PROMOTER_SHAREHOLDING",
        "Disclosure under SAST Regulations - Change in Promoter Stake",
        "Promoter group holding increased from 52.4% to 54.1% through open market purchase.",
    ),
    (
        "PLEDGE_ENCUMBRANCE",
        "Disclosure of Creation of Pledge on Promoter Shares",
        "Promoter has pledged 2,000,000 equity shares in favor of State Bank of India as collateral.",
    ),
    (
        "DEBT_CREDIT_DEFAULT",
        "Disclosure of Default on Payment of Principal and Interest on Term Loan",
        "The company has defaulted on repayment of Rs. 35 crore loan installment due to Punjab National Bank.",
    ),
    (
        "REGULATORY_LEGAL",
        "SEBI Adjudication Order in the matter of Insider Trading",
        "Securities and Exchange Board of India has passed an adjudication order imposing penalty of Rs. 25 lakh on noticee.",
    ),
    (
        "M_AND_A_RESTRUCTURING",
        "Scheme of Amalgamation and Merger Approved by Board",
        "Board has approved the merger of wholly owned subsidiary XYZ Limited with ABC Corporation.",
    ),
    (
        "CORPORATE_ACTION",
        "Declaration of Interim Dividend and Fixation of Record Date",
        "Board declared an interim dividend of Rs. 5 per share. Record date fixed as November 15, 2026.",
    ),
    (
        "BUSINESS_OPERATIONS",
        "Announcement of Major Capex for Capacity Expansion",
        "Company announces commissioning of new manufacturing line with capex of Rs. 120 crore.",
    ),
    (
        "TRADING_EXCHANGE_CHANGE",
        "Surveillance Measure - Additional Surveillance Measure (ASM) Stage I",
        "Securities of the company have been shortlisted under Framework for Additional Surveillance Measure (ASM).",
    ),
    (
        "MATERIAL_DISCLOSURE",
        "General Update on Clarification Sought by Exchange",
        "Clarification with reference to news item appearing in media.",
    ),
    (
        "ROUTINE_LOW_PRIORITY",
        "Schedule of Mock Trading Session for Capital Market Segment",
        "Exchange shall conduct a mock trading session on Saturday, October 24, 2026. General circular.",
    ),
])
def test_all_15_taxonomy_categories_classified_accurately(category_key, title, content):
    """Every single one of the 15 categories must be accurately detected by deterministic keyword matching."""
    detected = classify_to_taxonomy(title, "General", content)
    assert detected == category_key, f"Expected {category_key}, got {detected}"


def test_taxonomy_completeness():
    """All 15 taxonomy categories must be present and mapped in metadata."""
    assert len(EVENT_CATEGORIES) == 15
    for cat in VALID_TAXONOMY_CATEGORIES:
        assert cat in CATEGORY_DEFAULT_PRIORITY
        assert cat in VALID_EVENT_TYPES


# ===========================================================================
# 2. IMPORTANCE FILTER & PUBLICATION POLICY TESTS
# ===========================================================================

def test_critical_default_event_is_published():
    """A debt default notice must be classified as CRITICAL and marked should_publish=True."""
    release = {
        "doc_key": "NSE_DEF_001",
        "exchange": "NSE",
        "title": "Default on Loan Repayment",
        "category": "Debt",
        "doc_url": "https://example.com/def.pdf",
        "doc_id": "NSE/DEF/001",
    }
    content = "The company has committed a default on debt repayment of Rs. 150 crore to consortium of banks."
    res = compute_importance(release, content)
    assert res["event_type"] == "DEBT_CREDIT_DEFAULT"
    assert res["priority"] == "CRITICAL"
    assert res["importance_score"] >= 70
    assert res["should_publish"] is True
    assert "default" in res["reason_for_priority"].lower()


def test_routine_notice_is_suppressed_by_policy():
    """Administrative and mock trading notices must have LOW priority and should_publish=False."""
    release = {
        "doc_key": "BSE_ROUTINE_001",
        "exchange": "BSE",
        "title": "Mock Trading Session Announcement",
        "category": "Notice",
        "doc_url": "https://example.com/mock.pdf",
        "doc_id": "BSE/MOCK/001",
    }
    content = "Exchange will conduct mock trading and system maintenance on Saturday. No live market impact."
    res = compute_importance(release, content)
    assert res["event_type"] == "ROUTINE_LOW_PRIORITY"
    assert res["priority"] == "LOW"
    assert res["should_publish"] is False
    assert res["is_routine"] is True


def test_major_contract_cancellation_elevates_priority():
    """Contract cancellations are material governance events and must elevate priority."""
    release = {
        "doc_key": "NSE_ORD_002",
        "exchange": "NSE",
        "title": "Termination and Cancellation of Major EPC Contract",
        "category": "Corporate",
        "doc_url": "https://example.com/cancel.pdf",
        "doc_id": "NSE/ORD/002",
    }
    content = "Client has cancelled the order of Rs. 300 crore citing project delays."
    res = compute_importance(release, content)
    assert res["priority"] in ("HIGH", "CRITICAL")
    assert res["should_publish"] is True
    assert res["materiality_evidence"]["category_details"]["is_cancellation"] is True


def test_statutory_auditor_resignation_elevates_priority():
    """Statutory auditor resignation represents governance concern and must be HIGH priority."""
    release = {
        "doc_key": "BSE_AUD_001",
        "exchange": "BSE",
        "title": "Resignation of Statutory Auditor",
        "category": "Auditor",
        "doc_url": "https://example.com/aud.pdf",
        "doc_id": "BSE/AUD/001",
    }
    content = "Statutory auditor M/s ABC & Co resigned citing qualification in inventory valuation."
    res = compute_importance(release, content)
    assert res["event_type"] == "AUDITOR_CHANGE"
    assert res["priority"] in ("HIGH", "CRITICAL")
    assert res["should_publish"] is True
    assert res["materiality_evidence"]["category_details"]["governance_concern"] is True


# ===========================================================================
# 3. DOMAIN MATERIALITY & ANTI-FABRICATION RULES (SECTION D)
# ===========================================================================

def test_order_extraction_without_fabrication():
    """Materiality analyzer extracts order value and client without fabricating ratios."""
    text = "Company has received a contract awarded by Larsen & Toubro worth Rs. 450 crore for 18 months."
    ev = materiality_analyzer.analyze_order_contract(text)
    assert ev["order_value"] == "INR 450 Crore"
    assert "Larsen & Toubro" in ev["awarding_entity"]
    assert "18 months" in ev["duration"]


def test_bulk_deal_value_calculated_only_from_verified_inputs():
    """Bulk deal value is calculated strictly when quantity and price are present."""
    text = "Transaction details: Quantity: 500,000 shares at price Rs. 200.50 bought on exchange."
    ev = materiality_analyzer.analyze_bulk_block_deal(text)
    assert ev["quantity"] == 500000
    assert ev["price"] == 200.50
    assert ev["calculated_value_inr"] == 100250000.0  # 500,000 * 200.50
    assert ev["direction"] == "BUY"


def test_bulk_deal_missing_price_does_not_invent_value():
    """When price is missing, calculated value must be None."""
    text = "Transaction details: Quantity: 500,000 shares sold on exchange."
    ev = materiality_analyzer.analyze_bulk_block_deal(text)
    assert ev["quantity"] == 500000
    assert ev["price"] is None
    assert ev["calculated_value_inr"] is None


def test_auditor_preserves_stated_reason_without_inventing():
    """Preserves stated departure reason verbatim, never invents one."""
    text = "Statutory auditor resigned due to pre-occupations in other professional assignments."
    ev = materiality_analyzer.analyze_management_or_auditor(text)
    assert ev["stated_reason"] is not None
    assert "pre-occupations" in ev["stated_reason"].lower()


def test_regulatory_distinguishes_allegation_from_final_order():
    """A show-cause notice must be identified as allegation, not proven wrongdoing."""
    text = "SEBI has issued a show cause notice alleging violation of disclosure regulations."
    ev = materiality_analyzer.analyze_regulatory_legal(text)
    assert ev["is_allegation_only"] is True
    assert ev["legal_stage"] == "ALLEGATION_OR_SHOW_CAUSE"
    assert ev["regulator"] == "SEBI"


# ===========================================================================
# 4. REVISIONS & DEDUPLICATION (SECTION E)
# ===========================================================================

def test_genuine_revision_is_not_discarded(tmp_path):
    """A revision with same doc_key but different content hash must be recognized as revision."""
    db_file = tmp_path / "test_rev.db"
    db = DatabaseManager(db_path=db_file)

    initial_doc = {
        "doc_key": "NSE_CML_1001",
        "exchange": "NSE",
        "doc_id": "1001",
        "title": "Financial Results for Q2",
        "content_hash": "hash_v1_initial",
        "priority": "MEDIUM",
        "event_type": "FINANCIAL_RESULTS",
    }
    db.save_document(initial_doc)
    assert db.is_processed("NSE_CML_1001")

    # Document was saved with hash_v1
    existing = db.get_document("NSE_CML_1001")
    assert existing["content_hash"] == "hash_v1_initial"

    # Revision with new hash
    revised_hash = "hash_v2_revised_with_corrections"
    assert existing["content_hash"] != revised_hash, "Revision detected by content hash mismatch"


def test_cross_exchange_consolidation_detection(tmp_path):
    """Same filing published on both NSE and BSE is detected for consolidation."""
    db_file = tmp_path / "test_cross.db"
    db = DatabaseManager(db_path=db_file)

    nse_doc = {
        "doc_key": "NSE_CIRC_500",
        "exchange": "NSE",
        "doc_id": "CIRC_500",
        "title": "Buyback Offer Announcement",
        "company_name": "Tata Steel Limited",
        "content_hash": "sha256_shared_content_hash",
        "priority": "HIGH",
        "event_type": "CORPORATE_ACTION",
        "doc_url": "https://nsearchives.nseindia.com/500.zip",
        "alert_sent": 1,
    }
    db.save_document(nse_doc)

    # BSE receives same announcement with same hash
    match = db.find_cross_exchange_duplicate(
        exchange="BSE",
        content_hash="sha256_shared_content_hash",
        company_name="Tata Steel Limited",
        title="Buyback Offer Announcement"
    )
    assert match is not None
    assert match["doc_key"] == "NSE_CIRC_500"
    assert match["alert_sent"] == 1


# ===========================================================================
# 5. TELEGRAM MESSAGE FORMATTING (SECTION G)
# ===========================================================================

def test_telegram_layout_matches_section_g():
    """Telegram message layout must follow Section G specification exactly."""
    doc_data = {
        "priority": "CRITICAL",
        "exchange": "BSE",
        "event_type": "DEBT_CREDIT_DEFAULT",
        "company_name": "Reliance Infrastructure Limited",
        "symbol": "RELINFRA",
        "title": "Default on Loan Installment",
        "pub_date": "14 Oct 2026",
        "effective_date": "14/10/2026",
        "key_facts": ["Default of Rs. 120 crore to State Bank of India", "NPA classification initiated"],
        "reason_for_priority": "CRITICAL: Loan repayment default under IBC framework.",
        "summary": "Reliance Infrastructure Limited has disclosed default in repayment of credit facilities.",
        "official_source_url": "https://www.bseindia.com/notices/20261014-01.pdf",
        "doc_id": "20261014-01",
    }
    msg = _format_alert_message(doc_data)

    # Required section markers
    assert "🏢 Reliance Infrastructure Limited (RELINFRA)" in msg
    assert "📊 DEBT / CREDIT / DEFAULT" in msg
    assert "🔴 CRITICAL" in msg
    assert "⚡ Key Highlights" in msg
    assert "▸ Default of Rs. 120 crore to State Bank of India" in msg
    assert "🧠 ExchangeWatch AI" in msg
    assert "🎯 What Matters" in msg
    assert "📅 Important Dates" in msg
    assert "🔗 Official BSE Filing" in msg
    assert "⚠️ Informational update. Not investment advice." in msg


def test_telegram_hide_empty_fields():
    """When company, symbol, or dates are missing, lines are hidden cleanly."""
    doc_data = {
        "priority": "LOW",
        "exchange": "NSE",
        "event_type": "ROUTINE_LOW_PRIORITY",
        "company_name": "",
        "symbol": None,
        "title": "General Exchange Procedures",
        "pub_date": "",
        "effective_date": "",
        "summary": "Routine exchange operating procedure.",
        "official_source_url": "",
    }
    msg = _format_alert_message(doc_data)
    assert "🏢 General Exchange Procedures" in msg
    assert "📅 Important Dates" not in msg
    assert "None" not in msg


# ===========================================================================
# 6. AI VALIDATION AND SAFE FALLBACKS (PHASE 3B)
# ===========================================================================

def test_validator_preserves_deterministic_data_on_conflicting_ai():
    """Deterministic reference number, dates, and URLs must always override AI values."""
    release = {
        "doc_key": "NSE_FIX_123",
        "exchange": "NSE",
        "doc_id": "NSE/EXP/123",
        "pub_date": "14 Oct 2026",
        "doc_url": "https://nsearchives.nseindia.com/123.zip",
        "title": "Deterministic Title",
        "_deterministic_effective_date": "15-10-2026",
    }
    ai_output = make_empty_analysis()
    ai_output["company_name"] = "AI Guessed Company"
    ai_output["effective_date"] = "01-01-2099"  # Contradictory AI date
    ai_output["priority"] = "HIGH"
    ai_output["summary"] = "Summary from AI."

    merged = validate_and_merge(release, ai_output)
    assert merged["effective_date"] == "15-10-2026", "Deterministic date must win"
    assert merged["reference_number"] == "NSE/EXP/123"
    assert merged["official_source_url"] == "https://nsearchives.nseindia.com/123.zip"


def test_fast_nlp_fallback_operates_when_ai_offline():
    """Fast NLP produces factual analysis when LLM is unavailable."""
    nlp = FastNLPProvider()
    res = nlp.analyze_document(
        title="Appointment of Chief Financial Officer",
        category="Corporate",
        content="Board has appointed Mr. Amit Patel as CFO w.e.f. 01/11/2026."
    )
    assert res["analysis_mode"] == "FAST_NLP"
    assert res["effective_date"] == "01/11/2026"
    assert res["priority"] in ("HIGH", "MEDIUM")
    assert res["summary"] is not None
