"""
Fast NLP fallback provider for ExchangeWatch AI.

Uses deterministic keyword matching and regex to produce structured analysis
when Ollama is unavailable. Never invents facts.
"""
import re
from typing import Dict, Any, List
from app.ai.provider import BaseAIProvider
from app.ai.analysis_schema import (
    classify_event_type, make_empty_analysis,
    VALID_PRIORITIES, VALID_EVENT_TYPES
)


class FastNLPProvider(BaseAIProvider):
    CRITICAL_KEYWORDS = [
        "suspension", "halt", "surveillance", "margin requirement", "default",
        "penalty", "investigation", "circular cancellation", "emergency", "circuit limit",
        "trading halt", "asm", "gsm", "compulsory delisting",
    ]
    HIGH_KEYWORDS = [
        "amendment", "revised", "revision", "new listing", "ipo", "trading hours",
        "settlement schedule", "cybersecurity", "reporting deadline", "fee revision",
        "buyback", "takeover", "delisting", "open offer", "merger", "acquisition",
        "results", "quarterly results", "resignation", "appointment",
        "cfo", "ceo", "managing director", "auditor", "statutory auditor",
        "order win", "contract awarded", "contract cancellation",
    ]
    MEDIUM_KEYWORDS = [
        "holiday", "clarification", "system maintenance", "testing", "mock trading",
        "compliance update", "change of name", "index", "derivatives",
        "dividend", "record date", "annual general meeting",
    ]

    def analyze_document(self, title: str, category: str, content: str) -> Dict[str, Any]:
        result = make_empty_analysis()
        result["analysis_mode"] = "FAST_NLP"

        combined_text = f"{title} {category} {content}".lower()

        # 1. Classify event type
        result["event_type"] = classify_event_type(title, category, content)

        # 2. Determine Priority from keywords & taxonomy baseline
        if any(kw in combined_text for kw in self.CRITICAL_KEYWORDS):
            result["priority"] = "CRITICAL"
            result["reason_for_priority"] = (
                "CRITICAL: Document contains keywords indicating trading suspension, "
                "halt, surveillance, or debt emergency."
            )
        elif any(kw in combined_text for kw in self.HIGH_KEYWORDS):
            result["priority"] = "HIGH"
            result["reason_for_priority"] = (
                "HIGH: Document involves leadership change, corporate action, new listing, "
                "or significant material disclosure."
            )
        elif any(kw in combined_text for kw in self.MEDIUM_KEYWORDS):
            result["priority"] = "MEDIUM"
            result["reason_for_priority"] = (
                "MEDIUM: Document involves operational updates, compliance, or market maintenance."
            )
        else:
            from app.ai.taxonomy import CATEGORY_DEFAULT_PRIORITY
            default_p = CATEGORY_DEFAULT_PRIORITY.get(result["event_type"], "LOW")
            result["priority"] = default_p
            result["reason_for_priority"] = (
                f"{default_p}: Baseline priority for category {result['event_type']}."
            )

        # 3. Extract dates from content
        effective_date = self._extract_effective_date(content)
        result["effective_date"] = effective_date

        # 4. Extract offer period / start-end dates
        start_date, end_date = self._extract_offer_period(content)
        result["start_date"] = start_date
        result["end_date"] = end_date

        # 5. Extract deadline
        deadline = self._extract_deadline(content)
        result["deadline"] = deadline

        # 6. Extract action required
        action = self._extract_action_required(content, title)
        result["action_required"] = action

        # 7. Build summary (factual, no inventions)
        summary_parts = [f"{title}."]
        if effective_date and effective_date != "Not stated in document.":
            summary_parts.append(f"Effective: {effective_date}.")
        if start_date and end_date:
            summary_parts.append(f"Period: {start_date} to {end_date}.")
        result["summary"] = " ".join(summary_parts)

        # 8. Extract key changes
        result["key_changes"] = self._extract_key_changes(title, content)

        # 9. Confidence - fast NLP is rule-based, moderate confidence
        result["confidence"] = "MEDIUM"

        # 10. Note: FAST_NLP cannot reliably extract company name / symbol
        result["company_name"] = ""
        result["symbol"] = None
        result["uncertainties"] = [
            "Full LLM analysis was unavailable. Using rule-based Fast NLP fallback.",
            "Company name and symbol not extracted (requires LLM or deterministic source).",
        ]

        return result

    def _extract_effective_date(self, text: str) -> str:
        """Extract effective date from source text without reinterpreting format."""
        patterns = [
            r'(?:w\.e\.f\.?|with effect from|effective from|effective date[:\s]+)\s*([0-9]{1,2}[-/\.][0-9]{1,2}[-/\.][0-9]{2,4})',
            r'(?:w\.e\.f\.?|with effect from|effective from)\s+([0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})',
            r'(?:w\.e\.f\.?|with effect from|effective from)\s+([A-Za-z]+\s+[0-9]{1,2},\s+[0-9]{4})',
            r'(?:w\.e\.f\.?|with effect from|effective from)\s+([0-9]{1,2}-[A-Za-z]+-[0-9]{4})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return "Not stated in document."

    def _extract_offer_period(self, text: str):
        """Extract start and end date of an offer/period window."""
        patterns = [
            r'(?:offer period|issue period|period)[:\s]+([0-9]{1,2}[-/\.][0-9A-Za-z]+[-/\.][0-9]{2,4})\s*(?:to|–|-)\s*([0-9]{1,2}[-/\.][0-9A-Za-z]+[-/\.][0-9]{2,4})',
            r'(?:from)\s+([0-9]{1,2}[-/\.][0-9A-Za-z]+[-/\.][0-9]{2,4})\s*(?:to|–|-)\s*([0-9]{1,2}[-/\.][0-9A-Za-z]+[-/\.][0-9]{2,4})',
            r'([0-9]{1,2}-[A-Za-z]+-[0-9]{4})\s*(?:to|–|-)\s*([0-9]{1,2}-[A-Za-z]+-[0-9]{4})',
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1).strip(), m.group(2).strip()
        return "", ""

    def _extract_deadline(self, text: str) -> str:
        """Extract settlement or action deadline from source text."""
        patterns = [
            r'(?:deadline|last date|due date)[:\s]+([0-9]{1,2}[-/\.][0-9A-Za-z]+[-/\.][0-9]{2,4})',
            r'(?:deadline|last date|due date)[:\s]+([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})',
        ]
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return "Not stated in document."

    def _extract_action_required(self, content: str, title: str) -> str:
        """Extract what action is required from the document."""
        patterns = [
            r'(?:members?|participants?|investors?)\s+(?:are requested to|should|must|shall)\s+([^\.]{10,120})',
            r'(?:please|kindly)\s+(?:note|ensure|submit|comply)[^\.]{5,100}',
        ]
        for pattern in patterns:
            m = re.search(pattern, content, re.IGNORECASE)
            if m:
                action_text = m.group(0).strip()
                if len(action_text) < 200:
                    return action_text
        return "Not stated in document."

    def _extract_key_changes(self, title: str, content: str) -> List[str]:
        """Extract factual bullet points from document lines."""
        changes = []
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        for line in lines:
            if any(w in line.lower() for w in [
                "shall be", "revised to", "effective from", "changed from",
                "deadline", "modified", "offer period", "buyback", "takeover",
                "suspension", "listing", "settlement"
            ]):
                if 10 < len(line) < 180:
                    changes.append(line)
            if len(changes) >= 6:
                break

        if not changes:
            changes.append(title)
        return changes[:6]


fast_nlp_provider = FastNLPProvider()
