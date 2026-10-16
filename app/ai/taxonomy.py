"""
ExchangeWatch AI — Centralized Event Taxonomy

Defines the 15-category classification system for NSE/BSE filings.
Configurable, extensible, and deterministic-first.

Categories:
  1.  MANAGEMENT_CHANGE
  2.  AUDITOR_CHANGE
  3.  FINANCIAL_RESULTS
  4.  MAJOR_ORDER_CONTRACT
  5.  BULK_BLOCK_DEAL
  6.  PROMOTER_SHAREHOLDING
  7.  PLEDGE_ENCUMBRANCE
  8.  DEBT_CREDIT_DEFAULT
  9.  REGULATORY_LEGAL
  10. M_AND_A_RESTRUCTURING
  11. CORPORATE_ACTION
  12. BUSINESS_OPERATIONS
  13. TRADING_EXCHANGE_CHANGE
  14. MATERIAL_DISCLOSURE
  15. ROUTINE_LOW_PRIORITY
"""

import re
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Canonical event taxonomy
# ---------------------------------------------------------------------------

EVENT_CATEGORIES: Dict[str, str] = {
    "MANAGEMENT_CHANGE": (
        "CEO, CFO, MD, executive director or key managerial personnel "
        "appointment/resignation, senior leadership exit, significant "
        "board or control changes."
    ),
    "AUDITOR_CHANGE": (
        "Statutory auditor resignation/removal, qualified/adverse audit opinion, "
        "material audit qualifications or internal control weaknesses."
    ),
    "FINANCIAL_RESULTS": (
        "Quarterly/annual results, material earnings deterioration or improvement, "
        "unexpected losses, restatements, material accounting issues."
    ),
    "MAJOR_ORDER_CONTRACT": (
        "Significant order wins and contract awards, major order cancellations, "
        "material order-book or key-customer changes."
    ),
    "BULK_BLOCK_DEAL": (
        "Significant bulk deals and block deals, unusually large verified "
        "transactions, material institutional or promoter buying/selling."
    ),
    "PROMOTER_SHAREHOLDING": (
        "Significant promoter stake increases/decreases, large insider or "
        "institutional stake changes, control changes and open offers."
    ),
    "PLEDGE_ENCUMBRANCE": (
        "New/increased promoter pledging, pledge invocation or release, "
        "material changes in encumbered shares."
    ),
    "DEBT_CREDIT_DEFAULT": (
        "Loan/debt repayment defaults, material credit-rating downgrades, "
        "covenant breaches, insolvency concerns, restructuring."
    ),
    "REGULATORY_LEGAL": (
        "Material regulator orders or penalties, significant investigations, "
        "litigation or enforcement, trading bans, licence restrictions, "
        "insolvency proceedings."
    ),
    "M_AND_A_RESTRUCTURING": (
        "Mergers, acquisitions, demergers, material subsidiary or business "
        "sales, takeovers and changes in control."
    ),
    "CORPORATE_ACTION": (
        "Buybacks, dividends, rights issues, QIPs, preferential issues, "
        "warrants, bonus/split, material changes to announced corporate "
        "actions, important record dates and deadlines."
    ),
    "BUSINESS_OPERATIONS": (
        "Major capex and capacity expansion, plant shutdowns or significant "
        "production disruption, major project delays/cancellations, material "
        "customer/product/business developments."
    ),
    "TRADING_EXCHANGE_CHANGE": (
        "Trading suspensions/relisting, material surveillance or price-band "
        "changes, settlement disruptions and trading restrictions."
    ),
    "MATERIAL_DISCLOSURE": (
        "Other material company disclosures that do not fit the categories above."
    ),
    "ROUTINE_LOW_PRIORITY": (
        "Administrative, repetitive or non-material disclosures."
    ),
}

# All valid category names (for validation)
VALID_TAXONOMY_CATEGORIES: frozenset = frozenset(EVENT_CATEGORIES.keys())

# ---------------------------------------------------------------------------
# Keyword → category mapping (deterministic, ordered by specificity)
# Uses word-boundary regexes to prevent false-substring matches (e.g. segment -> egm)
# ---------------------------------------------------------------------------

TAXONOMY_KEYWORD_RULES: List[Tuple[str, List[str]]] = [
    # ---- ROUTINE_LOW_PRIORITY (Evaluated early to prevent routine operational notices matching broader categories) ----
    ("ROUTINE_LOW_PRIORITY", [
        "mock trading", "mock session", "system maintenance",
        "market holiday", "trading holiday", "settlement holiday", "clearing holiday",
        "investor awareness", "investor education",
        "loss of share certificate", "loss of share", "duplicate share certificate", "issue of duplicate share",
        "closure of trading window", "trading window",
        "newspaper publication", "newspaper advertisement", "copies of newspaper",
        "analyst meet", "investor meet", "analyst call", "institutional investor meeting",
        "address of registrar", "address of rta", "registrar and share transfer agent",
        "margin trading facility", "eligible for margin",
        "dispatch of annual report", "annual report dispatch", "notice of 32nd annual", "notice of annual general meeting",
        "regulation 7(3)", "regulation 40(9)", "regulation 74(5)", "compliance certificate",
        "reaffirms credit rating", "credit rating reaffirmed", "stable outlook",
        "press release on community", "corporate social responsibility", "csr",
        "clarification on price movement", "clarification with reference to increase in volume",
        "general circular", "administrative notice",
    ]),

    # ---- MANAGEMENT_CHANGE ----
    ("MANAGEMENT_CHANGE", [
        "ceo resignation", "cfo resignation", "md resignation", "ceo appointment",
        "cfo appointment", "md appointment", "managing director resigned",
        "chief executive officer resigned", "chief financial officer resigned",
        "resignation of chief executive officer", "appointment of chief executive officer",
        "resignation of chief financial officer", "appointment of chief financial officer",
        "resignation of managing director", "appointment of managing director",
        "resignation of director", "appointment of director", "cessation of director",
        "resignation of executive director", "appointment of executive director",
        "resignation of independent director", "appointment of independent director",
        "resignation of kmp", "appointment of kmp",
        "resignation as ceo", "resignation as cfo", "resigned as ceo", "resigned as cfo",
        "appointed as ceo", "appointed as cfo", "appointed as md", "resigned as md",
        "key managerial personnel", "kmp resignation", "kmp appointment",
        "board change", "director appointment", "director resignation",
        "change in management", "change in directorate", "cessation of director",
        "whole-time director",
    ]),

    # ---- AUDITOR_CHANGE ----
    ("AUDITOR_CHANGE", [
        "auditor resignation", "statutory auditor", "statutory auditors", "auditor removed",
        "resignation of statutory auditor", "resignation of statutory auditors", "removal of statutory auditor",
        "qualified opinion", "adverse opinion", "audit qualification",
        "material weakness", "internal control weakness", "auditor reappointment",
        "change of auditor", "appointment of auditor", "auditor report",
    ]),

    # ---- DEBT_CREDIT_DEFAULT (Critical governance/solvency events) ----
    ("DEBT_CREDIT_DEFAULT", [
        "debt default", "loan default", "npa",
        "credit rating downgrade", "rating downgrade",
        "insolvency petition", "insolvency proceeding", "ibc proceeding", "nclt admission", "cirp",
        "covenant breach", "debt restructuring",
        "one-time settlement", "ots",
        "bank declared npa", "asset classification",
        "default on payment", "default in repayment",
        "default on debt", "default on loan",
    ]),

    # ---- MAJOR_ORDER_CONTRACT ----
    ("MAJOR_ORDER_CONTRACT", [
        "contract cancellation", "order cancellation",
        "cancellation of order", "cancellation of contract",
        "termination of contract", "termination of order",
        "order win", "order received", "contract awarded", "award of",
        "secured contract", "secured order", "mega order",
        "letter of intent", "loi received",
        "work order", "supply order", "purchase order received",
        "order book update", "new order", "significant order",
        "key customer", "major contract", "epc contract",
    ]),

    # ---- BULK_BLOCK_DEAL ----
    ("BULK_BLOCK_DEAL", [
        "bulk deal", "block deal", "bulk/block deal",
        "large transaction", "significant transaction",
        "institutional purchase", "institutional sale",
        "promoter purchase", "promoter sale",
    ]),

    # ---- PROMOTER_SHAREHOLDING ----
    ("PROMOTER_SHAREHOLDING", [
        "promoter shareholding", "promoter stake", "promoter holding",
        "shareholding pattern", "substantial acquisition",
        "open offer", "public announcement",
        "insider stake", "institutional stake change",
        "change in shareholding", "sast", "takeover code",
    ]),

    # ---- PLEDGE_ENCUMBRANCE ----
    ("PLEDGE_ENCUMBRANCE", [
        "pledge invocation", "pledge release", "pledge creation",
        "pledge revocation", "creation of pledge", "release of pledge",
        "invocation of pledge", "pledged", "pledging", "encumbrance", "encumbered",
    ]),

    # ---- FINANCIAL_RESULTS ----
    ("FINANCIAL_RESULTS", [
        "financial results", "quarterly results", "annual results",
        "q1 results", "q2 results", "q3 results", "q4 results",
        "standalone results", "consolidated results", "half-yearly results",
        "unaudited financial", "audited financial", "profit after tax",
        "net loss", "net profit", "earnings per share", "restatement",
        "financial restatement", "material accounting",
    ]),

    # ---- REGULATORY_LEGAL ----
    ("REGULATORY_LEGAL", [
        "sebi order", "sebi notice", "sebi penalty", "sebi investigation",
        "rbi action", "enforcement directorate", "ed action", "ed search",
        "cbi investigation", "cbi search", "sfio investigation", "pmla",
        "court order", "tribunal order",
        "regulatory penalty", "show cause notice", "adjudication order",
        "securities fraud", "insider trading allegation",
        "trading ban", "debarment", "licence cancellation",
        "compounding", "settlement with sebi",
    ]),

    # ---- M_AND_A_RESTRUCTURING ----
    ("M_AND_A_RESTRUCTURING", [
        "merger", "amalgamation", "acquisition", "takeover",
        "demerger", "scheme of arrangement", "scheme of amalgamation", "business transfer",
        "subsidiary sale", "stake acquisition", "controlling interest",
        "joint venture", "slump sale",
    ]),

    # ---- CORPORATE_ACTION ----
    ("CORPORATE_ACTION", [
        "buyback", "buy-back", "buy back", "tender offer",
        "delisting", "voluntary delisting", "delisting proposal", "floor price",
        "dividend", "interim dividend", "final dividend", "special dividend",
        "rights issue", "qip", "preferential allotment", "preferential issue",
        "bonus shares", "bonus issue", "stock split", "face value split",
        "subdivision of shares", "sub-division", "warrant conversion", "record date", "ex-date",
        "extraordinary general meeting", "egm",
    ]),

    # ---- BUSINESS_OPERATIONS ----
    ("BUSINESS_OPERATIONS", [
        "capex", "capacity expansion", "plant shutdown", "factory closure",
        "production disruption", "project delay", "project cancellation",
        "incident of fire", "fire broke out", "fire at",
        "worker strike", "labour strike", "illegal strike", "strike by", "lockout",
        "operations halted", "operations temporarily halted", "temporarily halted",
        "new plant", "expansion project", "commissioning",
        "product launch", "business development",
        "joint venture formation",
    ]),

    # ---- TRADING_EXCHANGE_CHANGE ----
    ("TRADING_EXCHANGE_CHANGE", [
        "trading suspension", "suspension of trading",
        "trading halt", "price band", "circuit breaker",
        "asm", "gsm", "surveillance measure",
        "relisting", "re-listing", "settlement disruption",
        "margin requirement", "var margin", "exposure margin",
    ]),
]

# Compile regexes with word boundaries for precision
COMPILED_TAXONOMY_RULES = []
for category_name, patterns in TAXONOMY_KEYWORD_RULES:
    # Use word boundaries for short acronyms/words (<= 4 chars) and clean matching
    category_regexes = [
        re.compile(r"\b" + re.escape(p) + r"\b", re.IGNORECASE)
        for p in patterns
    ]
    COMPILED_TAXONOMY_RULES.append((category_name, category_regexes))


def classify_to_taxonomy(title: str, category: str, content: str) -> str:
    """
    Classify a document to one of the 15 taxonomy categories using
    deterministic word-boundary regex matching.

    Returns the matched category name (always in VALID_TAXONOMY_CATEGORIES).
    Falls back to MATERIAL_DISCLOSURE when no strong match is found.
    """
    combined = f"{title} {category} {content}".lower()

    for event_category, regexes in COMPILED_TAXONOMY_RULES:
        for r in regexes:
            if r.search(combined):
                return event_category

    return "MATERIAL_DISCLOSURE"


# ---------------------------------------------------------------------------
# Priority guidance per category
# (Starting guidance — actual priority is evidence-driven)
# ---------------------------------------------------------------------------

CATEGORY_DEFAULT_PRIORITY: Dict[str, str] = {
    "MANAGEMENT_CHANGE":      "HIGH",
    "AUDITOR_CHANGE":         "HIGH",
    "FINANCIAL_RESULTS":      "MEDIUM",
    "MAJOR_ORDER_CONTRACT":   "MEDIUM",
    "BULK_BLOCK_DEAL":        "MEDIUM",
    "PROMOTER_SHAREHOLDING":  "MEDIUM",
    "PLEDGE_ENCUMBRANCE":     "MEDIUM",
    "DEBT_CREDIT_DEFAULT":    "CRITICAL",
    "REGULATORY_LEGAL":       "HIGH",
    "M_AND_A_RESTRUCTURING":  "HIGH",
    "CORPORATE_ACTION":       "MEDIUM",
    "BUSINESS_OPERATIONS":    "LOW",
    "TRADING_EXCHANGE_CHANGE": "HIGH",
    "MATERIAL_DISCLOSURE":    "LOW",
    "ROUTINE_LOW_PRIORITY":   "LOW",
}

# ---------------------------------------------------------------------------
# Publication policy per priority
# ---------------------------------------------------------------------------

PUBLISH_BY_DEFAULT: Dict[str, bool] = {
    "CRITICAL": True,
    "HIGH":     True,
    "MEDIUM":   False,   # Configurable — needs materiality check
    "LOW":      False,
}
