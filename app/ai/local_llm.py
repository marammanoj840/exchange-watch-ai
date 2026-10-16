"""
Local LLM provider for ExchangeWatch AI.

Uses Ollama (llama3.2:1b) to produce structured document analysis.
Deterministic source values ALWAYS override LLM output.
Falls back to Fast NLP on any Ollama failure.
"""
import requests
import json
from typing import Dict, Any
from app.config.settings import settings
from app.core.logger import logger
from app.ai.provider import BaseAIProvider
from app.ai.fast_nlp import fast_nlp_provider
from app.ai.analysis_schema import (
    make_empty_analysis, VALID_PRIORITIES, VALID_EVENT_TYPES,
    classify_event_type
)


class LocalLLMProvider(BaseAIProvider):

    def analyze_document(self, title: str, category: str, content: str) -> Dict[str, Any]:
        if not settings.LOCAL_AI_ENABLED:
            logger.info("Local AI disabled by configuration. Falling back to Fast NLP.")
            return fast_nlp_provider.analyze_document(title, category, content)

        # Pre-classify event type using deterministic keywords
        # This helps the LLM but also provides a safe fallback
        deterministic_event_type = classify_event_type(title, category, content)

        prompt = f"""You are an official stock exchange document analyst for NSE and BSE India.
Analyze the following official document and respond ONLY with a valid JSON object.

RULES:
- Extract facts ONLY from the document. Do NOT invent any information.
- If a fact is not present, use: "Not stated in document."
- Do NOT make investment recommendations.
- Do NOT predict market movements.
- Preserve dates EXACTLY as written in the source (e.g., 01/10/2026, 30-Sep-2026).
- Company name must come from the document, not guessed.

Document Title: {title}
Category: {category}
Content (first 2000 chars):
{content[:2000]}

Respond ONLY with this JSON (no markdown, no explanation):
{{
  "company_name": "Company name from document, or empty string if not mentioned",
  "symbol": "NSE/BSE trading symbol if mentioned, else null",
  "event_type": "one of: CORPORATE_ACTION|BUYBACK|TAKEOVER|DELISTING|MERGER|ACQUISITION|LISTING|TRADING_HALT|SURVEILLANCE|REGULATORY|COMPLIANCE|SETTLEMENT|MARGIN|DERIVATIVES|INDEX|MARKET_OPERATIONS|INVESTOR_NOTICE|RESULTS|GENERAL_NOTICE|OTHER",
  "priority": "one of: CRITICAL|HIGH|MEDIUM|LOW",
  "reason_for_priority": "1 sentence explaining why, citing document facts only",
  "effective_date": "Effective date as written in source, or 'Not stated in document.'",
  "start_date": "Start date of offer/period as written, or empty",
  "end_date": "End date of offer/period as written, or empty",
  "deadline": "Deadline as written in source, or 'Not stated in document.'",
  "action_required": "What action is required from participants/investors, or 'Not stated in document.'",
  "subject": "Official subject line of the document",
  "summary": "2-4 sentence factual summary: what happened, who is affected, what dates matter",
  "key_changes": ["Bullet 1 (max 6 factual points from document)", "Bullet 2"],
  "affected_parties": ["e.g. Members", "Investors", "Clearing Members"],
  "uncertainties": ["Any genuinely ambiguous points in the document"]
}}"""

        try:
            payload = {
                "model": settings.LOCAL_AI_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1,   # Low temperature for factual accuracy
                }
            }
            timeout_sec = getattr(settings, "LOCAL_AI_TIMEOUT_SECONDS", 10)
            res = requests.post(settings.LOCAL_AI_URL, json=payload, timeout=timeout_sec)
            if res.status_code == 200:
                resp_json = res.json()
                raw_response = resp_json.get("response", "")
                parsed = json.loads(raw_response)

                result = make_empty_analysis()
                result["analysis_mode"] = "LLM"

                # --- Apply LLM output with validation ---
                result["company_name"] = parsed.get("company_name", "") or ""
                result["symbol"] = parsed.get("symbol") or None

                # Event type - validate against allowed values
                llm_event_type = str(parsed.get("event_type", "OTHER")).upper().strip()
                if llm_event_type in VALID_EVENT_TYPES:
                    result["event_type"] = llm_event_type
                else:
                    logger.debug(f"LLM returned invalid event_type '{llm_event_type}', using deterministic '{deterministic_event_type}'")
                    result["event_type"] = deterministic_event_type

                # Priority - validate against allowed values
                llm_priority = str(parsed.get("priority", "MEDIUM")).upper().strip()
                result["priority"] = llm_priority if llm_priority in VALID_PRIORITIES else "MEDIUM"

                result["reason_for_priority"] = parsed.get("reason_for_priority", "") or ""
                result["subject"] = parsed.get("subject", "") or ""
                result["summary"] = parsed.get("summary", title) or title
                result["action_required"] = parsed.get("action_required", "Not stated in document.") or "Not stated in document."
                result["deadline"] = parsed.get("deadline", "Not stated in document.") or "Not stated in document."

                # Dates - use LLM output but these will be overridden by deterministic values in main.py
                result["effective_date"] = parsed.get("effective_date", "") or ""
                result["start_date"] = parsed.get("start_date", "") or ""
                result["end_date"] = parsed.get("end_date", "") or ""

                # Lists
                key_changes = parsed.get("key_changes", [])
                result["key_changes"] = [str(k) for k in key_changes if k][:6] or [title]

                affected_parties = parsed.get("affected_parties", [])
                result["affected_parties"] = [str(p) for p in affected_parties if p][:5]

                uncertainties = parsed.get("uncertainties", [])
                result["uncertainties"] = [str(u) for u in uncertainties if u][:5]

                result["confidence"] = "HIGH"
                return result

        except json.JSONDecodeError as e:
            logger.warning(f"LLM returned invalid JSON ({e}). Falling back to Fast NLP.")
        except Exception as e:
            # Redact token from error message if present
            err_msg = str(e)
            logger.warning(f"Local LLM unavailable ({err_msg}). Gracefully falling back to Fast NLP.")

        return fast_nlp_provider.analyze_document(title, category, content)


ai_provider = LocalLLMProvider()
