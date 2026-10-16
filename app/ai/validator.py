"""
Alert validation for ExchangeWatch AI.

Validates that AI-generated analysis does not contradict deterministic source data.
On conflict: KEEP the deterministic value and log the conflict.
"""
from typing import Dict, Any
from app.core.logger import logger
from app.ai.analysis_schema import VALID_PRIORITIES, VALID_EVENT_TYPES


def _dates_conflict(det_date: str, ai_date: str) -> bool:
    """Check if two date strings represent a possible conflict."""
    if not det_date or not ai_date:
        return False
    if ai_date in ("Not stated in document.", "Immediate / As specified", ""):
        return False
    # Simple text mismatch — not full parsing to avoid re-interpretation
    return det_date.strip() != ai_date.strip()


def validate_and_merge(release: Dict[str, Any], ai_res: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge deterministic source data with AI analysis result.

    Deterministic source values (from release dict) ALWAYS win over AI.
    Conflicts are logged for debugging.

    Returns the final merged document data dict.
    """
    final = dict(release)  # Start with source data

    # --- Fields always taken from AI (no deterministic equivalent) ---
    final["company_name"] = ai_res.get("company_name", "") or release.get("company_name", "")
    final["symbol"] = ai_res.get("symbol") or release.get("symbol")
    final["event_type"] = ai_res.get("event_type", "OTHER")
    final["subject"] = ai_res.get("subject", "") or release.get("title", "")
    final["summary"] = ai_res.get("summary", release.get("title", ""))
    final["key_changes"] = ai_res.get("key_changes", [release.get("title", "")])
    final["affected_parties"] = ai_res.get("affected_parties", [])
    final["reason_for_priority"] = ai_res.get("reason_for_priority", "")
    final["uncertainties"] = ai_res.get("uncertainties", [])
    final["action_required"] = ai_res.get("action_required", "Not stated in document.")
    final["deadline"] = ai_res.get("deadline", "Not stated in document.")
    final["start_date"] = ai_res.get("start_date", "")
    final["end_date"] = ai_res.get("end_date", "")
    final["confidence"] = ai_res.get("confidence", "LOW")
    final["analysis_mode"] = ai_res.get("analysis_mode", "UNKNOWN")

    # --- Priority: AI provides, but must be valid ---
    ai_priority = str(ai_res.get("priority", "MEDIUM")).upper()
    final["priority"] = ai_priority if ai_priority in VALID_PRIORITIES else "MEDIUM"

    # --- Effective date: deterministic wins ---
    det_eff_date = release.get("_deterministic_effective_date", "")
    ai_eff_date = ai_res.get("effective_date", "")
    if det_eff_date:
        if _dates_conflict(det_eff_date, ai_eff_date):
            logger.debug(
                f"[VALIDATION] Effective date conflict for {release.get('doc_key', '')}: "
                f"deterministic='{det_eff_date}' vs AI='{ai_eff_date}'. Keeping deterministic."
            )
        final["effective_date"] = det_eff_date
    else:
        final["effective_date"] = ai_eff_date or "Not stated in document."

    # --- Publication date: deterministic wins ---
    if release.get("pub_date"):
        final["publication_date"] = release["pub_date"]
    else:
        final["publication_date"] = ""

    # --- Reference number: from source ---
    final["reference_number"] = release.get("doc_id", "")
    final["document_id"] = release.get("doc_key", "")

    # --- Official source URL: from collector ---
    final["official_source_url"] = release.get("doc_url", "")

    # --- Exchange: from collector ---
    final["exchange"] = release.get("exchange", "")

    # --- Final validation checks ---
    warnings = []
    if not final["summary"] or final["summary"].strip() == "":
        warnings.append("Summary is empty — using title as fallback.")
        final["summary"] = release.get("title", "No summary available.")

    if not final["key_changes"]:
        warnings.append("Key changes list is empty — using title as fallback.")
        final["key_changes"] = [release.get("title", "")]

    if final["event_type"] not in VALID_EVENT_TYPES:
        warnings.append(f"Invalid event_type '{final['event_type']}' — using OTHER.")
        final["event_type"] = "OTHER"

    if warnings:
        logger.warning(
            f"[VALIDATION] {release.get('doc_key', '')} had {len(warnings)} issue(s): "
            + "; ".join(warnings)
        )

    return final
