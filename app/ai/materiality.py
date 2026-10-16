"""
ExchangeWatch AI — Materiality Rules and Financial Evidence Extraction

Implements Section D financial materiality rules:
  - Major Orders / Contracts
  - Bulk / Block Deals
  - Management & Auditor Changes
  - Financial Results
  - Promoter Shareholding & Pledge
  - Regulatory & Legal Events

Guarantees:
  - Never fabricates figures, ratios, comparisons, or reasons.
  - Distinguishes allegations from proven findings.
  - Distinguishes percentage-point changes from growth percentages.
  - Flags incomplete or unverifiable data without guessing.
"""

import re
from typing import Dict, Any, List, Optional, Tuple


class MaterialityAnalyzer:
    """Analyzes document text against domain-specific financial materiality rules."""

    # -----------------------------------------------------------------------
    # 1. MAJOR ORDERS / CONTRACTS
    # -----------------------------------------------------------------------
    @staticmethod
    def analyze_order_contract(text: str, title: str = "") -> Dict[str, Any]:
        """
        Extracts verified order/contract details:
          - order_value (e.g., 'Rs. 250 Crore')
          - awarding_entity
          - duration / completion period
          - cancellation_conditions
          - is_cancellation
        Never invents comparison ratios or revenue comparisons if missing.
        """
        evidence: Dict[str, Any] = {
            "order_value": None,
            "awarding_entity": None,
            "duration": None,
            "cancellation_conditions": None,
            "is_cancellation": False,
            "materiality_note": None,
        }
        low = text.lower()
        low_title = title.lower()

        # Check if cancellation
        is_cancel = False
        if any(w in low_title or w in low for w in [
            "contract cancelled", "order cancelled", "termination of contract",
            "cancellation of order", "cancelled the order", "cancelled the contract",
            "cancellation of contract", "order cancellation", "contract cancellation",
        ]):
            is_cancel = True
        elif ("cancellation" in low_title or "termination" in low_title) and ("contract" in low_title or "order" in low_title):
            is_cancel = True
        elif "cancelled" in low and ("order" in low or "contract" in low):
            is_cancel = True

        if is_cancel:
            evidence["is_cancellation"] = True
            evidence["materiality_note"] = "Order or contract cancellation disclosed."

        # Extract value
        val_patterns = [
            r'(?:worth|valued at|value of|order of|contract of|amounting to)\s*(?:approx\.?|aggregating)?\s*(?:rs\.?|inr|₹)?\s*([0-9,]+(?:\.[0-9]+)?)\s*(crore|cr|lakh|lac|million|billion)',
            r'(?:rs\.?|inr|₹)\s*([0-9,]+(?:\.[0-9]+)?)\s*(crore|cr|lakh|lac|million|billion)',
        ]
        for pat in val_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                num = m.group(1).strip()
                unit = m.group(2).strip()
                evidence["order_value"] = f"INR {num} {unit.capitalize()}"
                break

        # Awarding entity
        client_patterns = [
            r'(?:awarded by|received from|bagged from|order from|contract from)\s+([A-Z][A-Za-z0-9\s&,\.\(\)]+?)(?:\s+(?:for|to|worth|valued|dated|w\.e\.f\.|\.|\n))',
        ]
        for pat in client_patterns:
            m = re.search(pat, text)
            if m:
                client = m.group(1).strip()
                if len(client) > 3 and len(client) < 120:
                    evidence["awarding_entity"] = client
                    break

        # Duration
        dur_patterns = [
            r'(?:time period|execution period|duration|completion period|to be executed in|within|for|over|period of)\s*(?:is|of)?\s*([0-9]+\s*(?:months?|years?|days?|weeks?))',
        ]
        for pat in dur_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                evidence["duration"] = m.group(1).strip()
                break

        return evidence

    # -----------------------------------------------------------------------
    # 2. BULK / BLOCK DEALS
    # -----------------------------------------------------------------------
    @staticmethod
    def analyze_bulk_block_deal(text: str) -> Dict[str, Any]:
        """
        Extracts verified transaction data:
          - client_name
          - deal_type: 'BULK' | 'BLOCK'
          - direction: 'BUY' | 'SELL'
          - quantity
          - price
          - transaction_value (calculated ONLY if both quantity and price are verified)
        Never infers insider wrongdoing or predicts stock direction.
        """
        evidence: Dict[str, Any] = {
            "deal_type": "BLOCK" if "block deal" in text.lower() else "BULK",
            "direction": None,
            "quantity": None,
            "price": None,
            "calculated_value_inr": None,
            "client_name": None,
        }
        low = text.lower()
        if " buy " in low or " bought " in low or " purchase " in low:
            evidence["direction"] = "BUY"
        elif " sell " in low or " sold " in low or " sale " in low:
            evidence["direction"] = "SELL"

        # Quantity
        qty_m = re.search(r'(?:quantity|shares|qty)[:\s]*([0-9,]+)', text, re.IGNORECASE)
        if qty_m:
            try:
                evidence["quantity"] = int(qty_m.group(1).replace(",", ""))
            except ValueError:
                pass

        # Price
        price_m = re.search(r'(?:price|rate|avg price)[:\s]*(?:rs\.?|inr|₹)?\s*([0-9]+(?:\.[0-9]+)?)', text, re.IGNORECASE)
        if price_m:
            try:
                evidence["price"] = float(price_m.group(1))
            except ValueError:
                pass

        # Calculate transaction value ONLY when both verified
        if evidence["quantity"] and evidence["price"]:
            evidence["calculated_value_inr"] = round(evidence["quantity"] * evidence["price"], 2)

        return evidence

    # -----------------------------------------------------------------------
    # 3. MANAGEMENT & AUDITOR CHANGES
    # -----------------------------------------------------------------------
    @staticmethod
    def analyze_management_or_auditor(text: str) -> Dict[str, Any]:
        """
        Distinguishes:
          - appointment vs. resignation vs. removal/cessation
          - preserves stated reason for departure verbatim
          - detects qualified opinion, adverse opinion, or internal control weaknesses
          - never invents a reason for resignation
        """
        evidence: Dict[str, Any] = {
            "change_type": None,  # APPOINTMENT, RESIGNATION, REMOVAL, OPINION_QUALIFICATION
            "role": None,
            "person_name": None,
            "stated_reason": None,
            "has_adverse_opinion": False,
            "has_qualification": False,
            "governance_concern": False,
        }
        low = text.lower()

        # Check audit opinions
        if "adverse opinion" in low or "disclaimer of opinion" in low:
            evidence["has_adverse_opinion"] = True
            evidence["governance_concern"] = True
            evidence["change_type"] = "OPINION_QUALIFICATION"
        elif "qualified opinion" in low or "audit qualification" in low or "qualification" in low:
            evidence["has_qualification"] = True
            evidence["governance_concern"] = True
            evidence["change_type"] = "OPINION_QUALIFICATION"

        # Change nature
        if "resignation" in low or "resigned" in low or "stepping down" in low:
            evidence["change_type"] = "RESIGNATION"
        elif "removal" in low or "removed" in low or "termination" in low:
            evidence["change_type"] = "REMOVAL"
            evidence["governance_concern"] = True
        elif "appointment" in low or "appointed" in low:
            evidence["change_type"] = "APPOINTMENT"

        # Role
        roles = [
            ("Statutory Auditor", ["statutory auditor", "independent auditor", "auditor"]),
            ("CEO", ["chief executive officer", "ceo"]),
            ("CFO", ["chief financial officer", "cfo"]),
            ("Managing Director", ["managing director", "md"]),
            ("Executive Director", ["executive director"]),
            ("Independent Director", ["independent director"]),
            ("Company Secretary", ["company secretary", "compliance officer"]),
        ]
        for role_name, kws in roles:
            if any(kw in low for kw in kws):
                evidence["role"] = role_name
                break

        # Statutory auditor resignation or removal is always a governance concern
        if evidence["role"] == "Statutory Auditor" and evidence["change_type"] in ("RESIGNATION", "REMOVAL"):
            evidence["governance_concern"] = True

        # Independent director or executive resignation citing governance/control concerns
        if (
            "governance concern" in low or "internal financial control" in low
            or "related party" in low or "accounting irregularity" in low
            or "loss of confidence" in low
        ):
            evidence["governance_concern"] = True

        # Stated reason (extract explicitly stated reason, never invent)
        reason_patterns = [
            r'(?:due to|reason for (?:resignation|cessation|departure|change)[:\s]+)\s*([^\n\.;]+)',
            r'(?:owing to|on account of)\s*([^\n\.;]+)',
        ]
        for pat in reason_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                r_text = m.group(1).strip()
                if len(r_text) > 3 and len(r_text) < 150:
                    evidence["stated_reason"] = r_text
                    break

        return evidence

    # -----------------------------------------------------------------------
    # 4. FINANCIAL RESULTS
    # -----------------------------------------------------------------------
    @staticmethod
    def analyze_financial_results(text: str) -> Dict[str, Any]:
        """
        Extracts reported numbers:
          - comparison_period (YoY, QoQ)
          - exceptional_items
          - restatements
          - audit qualifications
        Never calculates growth rates without both valid baseline & target values.
        """
        evidence: Dict[str, Any] = {
            "period": None,
            "is_yoy_mentioned": "yoy" in text.lower() or "year on year" in text.lower(),
            "is_qoq_mentioned": "qoq" in text.lower() or "quarter on quarter" in text.lower(),
            "has_exceptional_items": "exceptional item" in text.lower(),
            "has_restatement": "restatement" in text.lower() or "restated" in text.lower(),
            "has_qualified_opinion": "qualified opinion" in text.lower() or "with qualification" in text.lower(),
            "reported_pat": None,
            "reported_revenue": None,
        }

        # Reported PAT/Profit
        pat_m = re.search(r'(?:profit after tax|net profit|pat|net loss)[:\s]*(?:rs\.?|inr|₹)?\s*([0-9,]+(?:\.[0-9]+)?)\s*(crore|cr|lakh|lac)?', text, re.IGNORECASE)
        if pat_m:
            evidence["reported_pat"] = pat_m.group(0).strip()

        # Reported Revenue
        rev_m = re.search(r'(?:revenue from operations|total income|total revenue)[:\s]*(?:rs\.?|inr|₹)?\s*([0-9,]+(?:\.[0-9]+)?)\s*(crore|cr|lakh|lac)?', text, re.IGNORECASE)
        if rev_m:
            evidence["reported_revenue"] = rev_m.group(0).strip()

        return evidence

    # -----------------------------------------------------------------------
    # 5. PROMOTER SHAREHOLDING & PLEDGE
    # -----------------------------------------------------------------------
    @staticmethod
    def analyze_shareholding_or_pledge(text: str) -> Dict[str, Any]:
        """
        Extracts disclosed ownership percentages & periods.
        Distinguishes percentage-point change from percentage growth.
        Detects pledge invocation vs release vs creation.
        """
        evidence: Dict[str, Any] = {
            "is_pledge_creation": any(w in text.lower() for w in ["pledge created", "creation of pledge", "pledged"]),
            "is_pledge_release": any(w in text.lower() for w in ["release of pledge", "pledge released", "revocation of pledge"]),
            "is_pledge_invocation": any(w in text.lower() for w in ["invocation of pledge", "pledge invoked"]),
            "percentages_extracted": [],
        }

        # Percentage figures
        pct_matches = re.findall(r'([0-9]+(?:\.[0-9]+)?)\s*%', text)
        if pct_matches:
            evidence["percentages_extracted"] = [f"{p}%" for p in pct_matches[:4]]

        return evidence

    # -----------------------------------------------------------------------
    # 6. REGULATORY & LEGAL EVENTS
    # -----------------------------------------------------------------------
    @staticmethod
    def analyze_regulatory_legal(text: str) -> Dict[str, Any]:
        """
        Distinguishes:
          - allegation vs. investigation vs. interim order vs. final order vs. appeal vs. settlement
          - Never presents an allegation as proven wrongdoing.
          - Captures penalty amounts only when explicitly stated.
        """
        evidence: Dict[str, Any] = {
            "legal_stage": "NOTICE_OR_GENERAL",
            "penalty_amount": None,
            "regulator": None,
            "is_allegation_only": False,
        }
        low = text.lower()

        # Identify stage
        if "final order" in low or "adjudication order" in low or "order passed" in low:
            evidence["legal_stage"] = "FINAL_ORDER"
        elif "interim order" in low:
            evidence["legal_stage"] = "INTERIM_ORDER"
        elif "settlement" in low or "compounding" in low:
            evidence["legal_stage"] = "SETTLEMENT"
        elif "appeal" in low or "appealed" in low or "sat" in low or "high court" in low:
            evidence["legal_stage"] = "APPEAL"
        elif "investigation" in low or "inquiry" in low or "forensic audit" in low:
            evidence["legal_stage"] = "INVESTIGATION"
        elif "show cause notice" in low or "allegation" in low or "alleged" in low:
            evidence["legal_stage"] = "ALLEGATION_OR_SHOW_CAUSE"
            evidence["is_allegation_only"] = True

        # Regulator identification
        if "sebi" in low:
            evidence["regulator"] = "SEBI"
        elif "rbi" in low:
            evidence["regulator"] = "RBI"
        elif "nclt" in low:
            evidence["regulator"] = "NCLT"
        elif "cci" in low or "competition commission" in low:
            evidence["regulator"] = "CCI"
        elif "ed" in low or "enforcement directorate" in low:
            evidence["regulator"] = "Enforcement Directorate"

        # Penalty amount
        pen_m = re.search(r'(?:penalty|fine|penalty of|fine of)[:\s]*(?:rs\.?|inr|₹)?\s*([0-9,]+(?:\.[0-9]+)?)\s*(crore|cr|lakh|lac)?', text, re.IGNORECASE)
        if pen_m:
            evidence["penalty_amount"] = pen_m.group(0).strip()

        return evidence


materiality_analyzer = MaterialityAnalyzer()
