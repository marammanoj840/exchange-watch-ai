"""
ExchangeWatch AI — Importance Classifier

Computes event_type, priority, importance_score, and should_publish
for every candidate filing using:
  1. Deterministic taxonomy keyword matching
  2. Document evidence signals (from extracted text)
  3. AI analysis validation

This module never invents facts. All signals come from document content
or verified metadata.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from app.ai.taxonomy import (
    classify_to_taxonomy,
    CATEGORY_DEFAULT_PRIORITY,
    PUBLISH_BY_DEFAULT,
    VALID_TAXONOMY_CATEGORIES,
)
from app.ai.materiality import materiality_analyzer
from app.core.logger import logger

# ---------------------------------------------------------------------------
# Priority constants
# ---------------------------------------------------------------------------

VALID_PRIORITIES = frozenset({"CRITICAL", "HIGH", "MEDIUM", "LOW"})

# Priority rank for comparison (higher = more important)
PRIORITY_RANK: Dict[str, int] = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
}

# ---------------------------------------------------------------------------
# Importance scoring signals
# ---------------------------------------------------------------------------

# Signals that strongly boost importance_score
CRITICAL_SIGNALS: List[str] = [
    # Debt / insolvency
    "default", "insolvency", "nclt admission", "nclt insolvency", "ibc", "winding up", "liquidation",
    # Regulatory enforcement
    "sebi order", "trading ban", "debarment", "licence cancelled", "enforcement directorate",
    "search and seizure", "search operations", "pmla", "cbi search",
    # Trading disruption
    "trading suspension", "suspension of trading", "trading shall be suspended", "halt in trading", "circuit breaker",
    # Governance crisis
    "auditor resigned", "auditors have resigned", "auditor has resigned",
    "statutory auditor resigned", "statutory auditors have resigned",
    "resignation of statutory auditor", "resignation of statutory auditors",
    "qualified opinion", "adverse opinion", "disclaimer of opinion",
    "md resigned", "ceo resigned", "cfo resigned",
    # Pledge invocation
    "pledge invocation", "invocation of pledge", "pledge invoked", "invoked pledge",
    # Financial distress
    "going concern", "material uncertainty",
]

HIGH_SIGNALS: List[str] = [
    "resignation", "appointment of ceo", "appointment of cfo",
    "merger", "acquisition", "amalgamation", "takeover",
    "open offer", "buyback", "buy-back",
    "rights issue", "qip", "bonus issue", "bonus shares", "stock split",
    "credit rating downgrade", "rating downgrade",
    "order cancelled", "contract cancelled", "terminated and cancelled",
    "major order", "receipt of major order", "epc contract", "significant order",
    "bulk deal", "promoter stake", "promoter shareholding", "sast",
    "pledge on", "pledge invocation", "pledge created", "creation of pledge",
    "net loss", "material loss", "restatement", "profit after tax",
    "penalty", "adjudication order", "tax search", "search and seizure",
    "commissioning", "capacity expansion", "worker strike", "labour strike", "illegal strike", "operations halted",
]

MEDIUM_SIGNALS: List[str] = [
    "order received", "contract awarded", "new order",
    "dividend", "interim dividend", "record date",
    "shareholding pattern", "change in shareholding",
    "financial results", "quarterly results",
    "capex", "show cause", "show cause notice",
    "board meeting", "preliminary discussion", "exploratory",
]

SUPPRESSION_SIGNALS: List[str] = [
    "mock trading", "mock session", "system maintenance",
    "market holiday", "trading holiday",
    "investor awareness", "investor education",
    "annual report dispatch", "compliance certificate",
    "general circular", "administrative notice",
    "reminder", "corrigendum of",
]


def _count_signals(text: str, signals: List[str]) -> int:
    """Count how many signals appear in the text (case-insensitive)."""
    low = text.lower()
    return sum(1 for s in signals if s in low)


def _extract_importance_evidence(text: str) -> Dict[str, Any]:
    """
    Extract concrete evidence signals from document text.
    Returns a dict of evidence items found in the document.
    Never invents values.
    """
    evidence: Dict[str, Any] = {}
    low = text.lower()

    # Monetary values (INR amounts)
    money_patterns = [
        r'(?:rs\.?|inr|₹)\s*([0-9,]+(?:\.[0-9]+)?)\s*(?:crore|cr\.?|lakh|lac)',
        r'([0-9,]+(?:\.[0-9]+)?)\s*(?:crore|cr\.?)\s*(?:rupees?)?',
    ]
    amounts_found = []
    for pat in money_patterns:
        for m in re.finditer(pat, low):
            amounts_found.append(m.group(0).strip())
    if amounts_found:
        evidence["monetary_values_found"] = amounts_found[:5]

    # Percentage changes
    pct_patterns = [
        r'([0-9]+(?:\.[0-9]+)?)\s*%\s*(?:decrease|decline|fall|drop|rise|increase|growth)',
        r'(?:decrease|decline|fall|drop|rise|increase|growth)\s*(?:of|by)\s*([0-9]+(?:\.[0-9]+)?)\s*%',
    ]
    pct_found = []
    for pat in pct_patterns:
        for m in re.finditer(pat, low):
            pct_found.append(m.group(0).strip())
    if pct_found:
        evidence["percentage_changes_found"] = pct_found[:3]

    # Company names from specific disclosure patterns
    company_patterns = [
        r'(?:of|in|by|for)\s+([A-Z][A-Za-z\s&]+(?:Limited|Ltd\.?|Corporation|Corp\.?))',
    ]
    companies_found = []
    for pat in company_patterns:
        for m in re.finditer(pat, text):
            name = m.group(1).strip()
            if len(name) > 5:
                companies_found.append(name)
    if companies_found:
        evidence["companies_mentioned"] = list(set(companies_found))[:3]

    # Key disclosure flags
    if any(s in low for s in ["going concern", "material uncertainty"]):
        evidence["going_concern_flag"] = True
    if any(s in low for s in ["qualified opinion", "adverse opinion", "disclaimer of opinion"]):
        evidence["audit_opinion_issue"] = True
    if any(s in low for s in ["default", "npa", "non-performing"]):
        evidence["default_flag"] = True
    if any(s in low for s in ["sebi order", "sebi notice", "adjudication order"]):
        evidence["regulatory_action"] = True

    return evidence


def compute_importance(
    release: Dict[str, Any],
    content_text: str,
    ai_event_type: Optional[str] = None,
    ai_priority: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute the full importance assessment for a filing.

    Args:
        release: The collector release dict (metadata).
        content_text: Extracted document text (may be empty if download failed).
        ai_event_type: Event type from AI (optional, used as signal not ground truth).
        ai_priority: Priority from AI (optional, used as signal not ground truth).

    Returns:
        Dict with:
          - event_type (str): Taxonomy category
          - priority (str): CRITICAL / HIGH / MEDIUM / LOW
          - importance_score (int): 0–100 internal heuristic
          - reason_for_priority (str): Explanation citing document evidence
          - key_facts (list): Verified facts from document
          - materiality_evidence (dict): Evidence signals found
          - should_publish (bool): Whether to publish per default policy
          - is_routine (bool): True when clearly routine/administrative
    """
    title = release.get("title", "")
    category = release.get("category", "")
    combined_text = f"{title} {category} {content_text}"

    # 1. Determine taxonomy category (deterministic keyword matching)
    event_type = classify_to_taxonomy(title, category, content_text)

    # 2. Extract evidence signals
    evidence = _extract_importance_evidence(combined_text)

    # 3. Compute domain-specific financial materiality evidence
    category_evidence = {}
    if event_type == "MAJOR_ORDER_CONTRACT":
        category_evidence = materiality_analyzer.analyze_order_contract(combined_text, title)
    elif event_type == "BULK_BLOCK_DEAL":
        category_evidence = materiality_analyzer.analyze_bulk_block_deal(combined_text)
    elif event_type in ("MANAGEMENT_CHANGE", "AUDITOR_CHANGE"):
        category_evidence = materiality_analyzer.analyze_management_or_auditor(combined_text)
    elif event_type == "FINANCIAL_RESULTS":
        category_evidence = materiality_analyzer.analyze_financial_results(combined_text)
    elif event_type in ("PROMOTER_SHAREHOLDING", "PLEDGE_ENCUMBRANCE"):
        category_evidence = materiality_analyzer.analyze_shareholding_or_pledge(combined_text)
    elif event_type == "REGULATORY_LEGAL":
        category_evidence = materiality_analyzer.analyze_regulatory_legal(combined_text)

    evidence["category_details"] = category_evidence
    materiality_evidence = evidence

    # 4. Compute importance score (0–100, heuristic)
    category_baseline: Dict[str, int] = {
        "DEBT_CREDIT_DEFAULT": 85,
        "MANAGEMENT_CHANGE": 50,
        "AUDITOR_CHANGE": 50,
        "REGULATORY_LEGAL": 50,
        "M_AND_A_RESTRUCTURING": 50,
        "TRADING_EXCHANGE_CHANGE": 50,
        "FINANCIAL_RESULTS": 50,
        "MAJOR_ORDER_CONTRACT": 50,
        "CORPORATE_ACTION": 50,
        "PROMOTER_SHAREHOLDING": 50,
        "BULK_BLOCK_DEAL": 50,
        "PLEDGE_ENCUMBRANCE": 50,
        "BUSINESS_OPERATIONS": 45,
        "MATERIAL_DISCLOSURE": 25,
        "ROUTINE_LOW_PRIORITY": 0,
    }

    if not category_evidence.get("is_allegation_only"):
        score = category_baseline.get(event_type, 10)
    else:
        score = 20

    reasons: List[str] = []

    critical_count = _count_signals(combined_text, CRITICAL_SIGNALS)
    high_count = _count_signals(combined_text, HIGH_SIGNALS)
    medium_count = _count_signals(combined_text, MEDIUM_SIGNALS)
    suppression_count = _count_signals(combined_text, SUPPRESSION_SIGNALS)

    # Score from signals
    score += min(critical_count * 25, 50)
    score += min(high_count * 10, 30)
    score += min(medium_count * 5, 15)
    score -= suppression_count * 15

    # Score adjustments from domain-specific evidence
    if category_evidence.get("is_cancellation"):
        score = max(score + 35, 75)
        reasons.append("Major order or contract cancellation detected")
    if category_evidence.get("governance_concern"):
        score += 25
        reasons.append("Governance concern, resignation, or audit qualification detected")
    if category_evidence.get("has_restatement") or category_evidence.get("has_qualified_opinion"):
        score += 25
        reasons.append("Restatement or qualified opinion in financial results")
    if category_evidence.get("is_pledge_invocation"):
        score += 25
        reasons.append("Promoter pledge invocation detected")
    if category_evidence.get("legal_stage") == "FINAL_ORDER":
        score += 20
        reasons.append("Final regulatory order passed")
    elif category_evidence.get("is_allegation_only"):
        reasons.append("Disclosed as allegation or show-cause notice (not proven wrongdoing)")

    # Score from general evidence flags
    if evidence.get("going_concern_flag"):
        score += 25
        reasons.append("Going concern or material uncertainty disclosed")
    if evidence.get("audit_opinion_issue"):
        score += 25
        reasons.append("Qualified or adverse audit opinion present")
    if evidence.get("default_flag"):
        score += 30
        reasons.append("Default or NPA disclosure detected")
    if evidence.get("regulatory_action"):
        score += 20
        reasons.append("Regulatory action or SEBI order detected")
    if evidence.get("monetary_values_found"):
        score += 10  # Quantified financial transaction
    if evidence.get("percentage_changes_found"):
        score += 5   # Quantified percentage change

    if category_evidence.get("is_allegation_only"):
        score = min(score, 35)

    # AI agreement bonus (small — AI is a signal, not ground truth)
    if ai_event_type and ai_event_type == event_type:
        score = min(score + 5, 100)

    score = max(0, min(score, 100))

    # 4. Determine priority from score and category
    if score >= 75 or critical_count >= 1:
        priority = "CRITICAL"
        score = max(score, 75)
    elif score >= 45 or high_count >= 1:
        priority = "HIGH"
        score = max(score, 45)
    elif score >= 25 or medium_count >= 1:
        priority = "MEDIUM"
        score = max(score, 25)
    else:
        priority = "LOW"

    # Allegation-only notices are capped at MEDIUM unless proven wrongdoing
    if category_evidence.get("is_allegation_only") and critical_count == 0:
        priority = "MEDIUM"
        score = min(score, 35)

    # Respect AI priority if it's higher (AI may have seen more context)
    if ai_priority and ai_priority in VALID_PRIORITIES:
        if PRIORITY_RANK.get(ai_priority, 0) > PRIORITY_RANK.get(priority, 0):
            priority = ai_priority
            reasons.append(f"AI analysis elevated priority to {ai_priority}")

    # Force ROUTINE categories to LOW unless there are strong signals
    if event_type == "ROUTINE_LOW_PRIORITY" and critical_count == 0:
        priority = "LOW"
        score = min(score, 20)

    # 5. Build reason_for_priority
    category_default = CATEGORY_DEFAULT_PRIORITY.get(event_type, "MEDIUM")
    reason_parts = [f"Category: {event_type} (default priority: {category_default})."]
    if critical_count > 0:
        reason_parts.append(f"{critical_count} critical signal(s) detected.")
    if high_count > 0:
        reason_parts.append(f"{high_count} high-importance signal(s) detected.")
    if reasons:
        reason_parts.extend(reasons)
    reason_for_priority = " ".join(reason_parts)

    # 6. Extract key facts (brief, verified from document text)
    key_facts = _extract_key_facts(title, content_text, event_type)

    # 7. Publication policy
    is_routine = (event_type == "ROUTINE_LOW_PRIORITY" or suppression_count >= 2)
    should_publish = PUBLISH_BY_DEFAULT.get(priority, False)

    # MEDIUM: publish if score >= 40 (configurable threshold)
    if priority == "MEDIUM" and score >= 40:
        should_publish = True

    # Never suppress a potentially CRITICAL event
    if priority == "CRITICAL":
        should_publish = True

    # Routine events: always suppress unless explicitly CRITICAL
    if is_routine and priority != "CRITICAL":
        should_publish = False

    return {
        "event_type": event_type,
        "priority": priority,
        "importance_score": score,
        "reason_for_priority": reason_for_priority,
        "key_facts": key_facts,
        "materiality_evidence": materiality_evidence,
        "should_publish": should_publish,
        "is_routine": is_routine,
        # Passthrough for deduplication / Telegram
        "source_url": release.get("doc_url", ""),
        "source_reference": release.get("doc_id", ""),
        "is_duplicate": release.get("is_duplicate", False),
    }


def _extract_key_facts(title: str, content: str, event_type: str) -> List[str]:
    """
    Extract brief, factual bullet points from the document.
    Never fabricates information.
    """
    facts: List[str] = []
    lines = [line.strip() for line in content.split("\n") if line.strip()]

    # Keywords that often appear near key facts, category-aware
    fact_keywords = {
        "MANAGEMENT_CHANGE": [
            "resigned", "appointed", "ceased", "effective",
            "with effect from", "w.e.f.",
        ],
        "FINANCIAL_RESULTS": [
            "profit", "loss", "revenue", "turnover", "ebitda",
            "eps", "pat", "pbt", "crore", "lakh",
        ],
        "MAJOR_ORDER_CONTRACT": [
            "order", "contract", "awarded", "value", "crore", "period",
        ],
        "DEBT_CREDIT_DEFAULT": [
            "default", "rating", "downgrade", "npa", "insolvency",
        ],
        "REGULATORY_LEGAL": [
            "sebi", "penalty", "order", "notice", "investigation",
        ],
        "CORPORATE_ACTION": [
            "record date", "ex-date", "dividend", "buyback", "offer period",
            "ratio", "price",
        ],
    }

    target_keywords = fact_keywords.get(event_type, [
        "effective", "w.e.f.", "crore", "lakh", "date", "approved", "resolved",
    ])

    for line in lines:
        if any(kw in line.lower() for kw in target_keywords):
            if 10 < len(line) < 200:
                facts.append(line)
        if len(facts) >= 5:
            break

    # Fallback: use title if no facts extracted
    if not facts:
        facts = [title]

    return facts[:5]


def should_consolidate_cross_exchange(
    doc_a: Dict[str, Any],
    doc_b: Dict[str, Any],
) -> bool:
    """
    Determine if two documents from different exchanges represent the
    same underlying filing (for cross-exchange consolidation).

    Returns True only when there is strong evidence of identity.
    Never consolidates based on title similarity alone.
    """
    exchange_a = doc_a.get("exchange", "")
    exchange_b = doc_b.get("exchange", "")

    # Must be from different exchanges
    if exchange_a == exchange_b:
        return False

    # Same content hash = same document
    hash_a = doc_a.get("content_hash", "")
    hash_b = doc_b.get("content_hash", "")
    if hash_a and hash_b and hash_a == hash_b:
        return True

    # Same company + same event_type + same pub_date within 1 day window
    company_a = (doc_a.get("company_name") or "").lower().strip()
    company_b = (doc_b.get("company_name") or "").lower().strip()
    if not company_a or not company_b:
        return False

    if company_a != company_b:
        return False

    event_a = doc_a.get("event_type", "")
    event_b = doc_b.get("event_type", "")
    if event_a != event_b:
        return False

    pub_a = doc_a.get("pub_date", "")
    pub_b = doc_b.get("pub_date", "")
    if pub_a and pub_b and pub_a[:10] == pub_b[:10]:
        return True

    return False
