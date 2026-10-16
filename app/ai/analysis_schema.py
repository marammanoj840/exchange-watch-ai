"""
Structured AI analysis for ExchangeWatch AI.

This module defines the full analysis result schema returned by all AI providers.
Fields that come from deterministic extraction are NOT overwritten by AI.

Legacy event types (BUYBACK, MERGER, etc.) are preserved for backward compatibility.
New taxonomy categories (MANAGEMENT_CHANGE, FINANCIAL_RESULTS, etc.) are imported
from app.ai.taxonomy and merged into VALID_EVENT_TYPES.
"""
from app.ai.taxonomy import VALID_TAXONOMY_CATEGORIES

# Legacy event types (kept for backward compatibility with existing data and tests)
_LEGACY_EVENT_TYPES = {
    "CORPORATE_ACTION", "BUYBACK", "TAKEOVER", "DELISTING", "MERGER",
    "ACQUISITION", "LISTING", "TRADING_HALT", "SURVEILLANCE", "REGULATORY",
    "COMPLIANCE", "SETTLEMENT", "MARGIN", "DERIVATIVES", "INDEX",
    "MARKET_OPERATIONS", "INVESTOR_NOTICE", "RESULTS", "GENERAL_NOTICE", "OTHER"
}

# Full valid event type set = legacy + new 15-category taxonomy
VALID_EVENT_TYPES = _LEGACY_EVENT_TYPES | VALID_TAXONOMY_CATEGORIES

# Allowed priorities
VALID_PRIORITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}

# Keyword-to-event-type mapping for fast classification (legacy schema, AI prompt use)
EVENT_TYPE_KEYWORDS = {
    "BUYBACK": ["buyback", "buy-back", "buy back", "repurchase", "tender offer"],
    "TAKEOVER": ["takeover", "open offer", "substantial acquisition"],
    "DELISTING": ["delisting", "delist", "voluntary delisting", "compulsory delisting"],
    "MERGER": ["merger", "amalgamation", "scheme of arrangement"],
    "ACQUISITION": ["acquisition", "stake acquisition", "acquiring"],
    "LISTING": ["listing", "listed", "new listing", "ipo", "initial public offer"],
    "TRADING_HALT": ["trading halt", "suspension", "halt in trading", "circuit breaker"],
    "SURVEILLANCE": ["surveillance", "asm", "graded surveillance", "gsm"],
    "REGULATORY": ["sebi", "regulation", "regulatory", "compliance notice", "penalty"],
    "COMPLIANCE": ["compliance", "reporting deadline", "annual report", "disclosure"],
    "SETTLEMENT": ["settlement", "pay-in", "pay-out", "clearing"],
    "MARGIN": ["margin", "var margin", "exposure margin", "additional margin"],
    "DERIVATIVES": ["futures", "options", "derivatives", "expiry", "rollover"],
    "INDEX": ["index", "nifty", "sensex", "index reconstitution", "index rebalancing"],
    "MARKET_OPERATIONS": ["trading hours", "market holiday", "mock trading", "system maintenance"],
    "INVESTOR_NOTICE": ["investor", "investor notice", "investor awareness"],
    "RESULTS": ["results", "financial results", "quarterly results", "annual results"],
    "GENERAL_NOTICE": ["notice", "circular", "general notice"],
}


def classify_event_type(title: str, category: str, content: str) -> str:
    """Classify event type from document content using keyword matching.
    Delegates to the new taxonomy classifier."""
    from app.ai.taxonomy import classify_to_taxonomy
    return classify_to_taxonomy(title, category, content)


def make_empty_analysis() -> dict:
    """Return a fully populated empty analysis result skeleton."""
    return {
        "exchange": "",
        "document_id": "",
        "reference_number": "",
        "company_name": "",
        "symbol": None,
        "event_type": "OTHER",
        "priority": "MEDIUM",
        "publication_date": "",
        "effective_date": "",
        "start_date": "",
        "end_date": "",
        "deadline": "",
        "action_required": "Not stated in document.",
        "subject": "",
        "summary": "",
        "key_changes": [],
        "affected_parties": [],
        "reason_for_priority": "",
        "uncertainties": [],
        "official_source_url": "",
        "confidence": "LOW",
        "analysis_mode": "UNKNOWN",  # "LLM" or "FAST_NLP"
        # New importance filtering fields
        "importance_score": 0,
        "should_publish": False,
        "key_facts": [],
        "materiality_evidence": {},
        "is_routine": False,
    }

