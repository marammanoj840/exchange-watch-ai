"""
Excel + CSV writer for ExchangeWatch AI historical records.

Writes one row per processed alert with all structured fields.
Deduplicates by Doc ID to prevent double entries.
Uses atomic write (tmp file → rename) to prevent file corruption.
"""
import json
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional
from app.config.settings import settings
from app.core.logger import logger


# Full column set for the Excel/CSV output
COLUMNS = [
    "Detected At",
    "Exchange",
    "Company",
    "Symbol",
    "Event Type",
    "Priority",
    "Doc ID / Reference",
    "Category / Department",
    "Title / Subject",
    "Published At",
    "Effective Date",
    "Start Date",
    "End Date",
    "Deadline",
    "Summary",
    "Key Changes",
    "Action Required",
    "Reason for Priority",
    "Affected Parties",
    "Analysis Mode",
    "AI Model",
    "Confidence",
    "Alert Sent",
    "Importance Score",
    "Should Publish",
    "Is Revision",
    "Processing Time (ms)",
    "Document URL",
]


class ExcelWriter:
    def __init__(
        self,
        excel_path: Optional[Path] = None,
        csv_path: Optional[Path] = None
    ):
        self.excel_path = excel_path or settings.EXCEL_OUTPUT_PATH
        self.csv_path = csv_path or settings.CSV_OUTPUT_PATH
        self._ensure_files_exist()

    def _ensure_files_exist(self) -> None:
        self.excel_path.parent.mkdir(parents=True, exist_ok=True)
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.excel_path.exists():
            df = pd.DataFrame(columns=COLUMNS)
            with pd.ExcelWriter(self.excel_path, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Alerts")
            logger.info(f"Created initial Excel file at {self.excel_path}")

        if not self.csv_path.exists():
            df = pd.DataFrame(columns=COLUMNS)
            df.to_csv(self.csv_path, index=False)
            logger.info(f"Created initial CSV file at {self.csv_path}")

    def _build_row(self, doc_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build a flat row dict from the document data."""
        key_changes_raw = doc_data.get("key_changes", [])
        if isinstance(key_changes_raw, list):
            key_changes_str = "\n".join(f"• {k}" for k in key_changes_raw)
        else:
            key_changes_str = str(key_changes_raw)

        affected_raw = doc_data.get("affected_parties", [])
        if isinstance(affected_raw, list):
            affected_str = ", ".join(affected_raw)
        else:
            affected_str = str(affected_raw)

        latency = doc_data.get("latency_summary", {})
        if isinstance(latency, str):
            try:
                latency = json.loads(latency)
            except Exception:
                latency = {}
        total_ms = latency.get("total_latency_ms", "")

        return {
            "Detected At": doc_data.get("detected_at", ""),
            "Exchange": doc_data.get("exchange", ""),
            "Company": doc_data.get("company_name", ""),
            "Symbol": doc_data.get("symbol", ""),
            "Event Type": doc_data.get("event_type", "OTHER"),
            "Priority": doc_data.get("priority", "MEDIUM"),
            "Doc ID / Reference": doc_data.get("doc_id", "") or doc_data.get("reference_number", ""),
            "Category / Department": (
                f"{doc_data.get('category', '')} / {doc_data.get('department', '')}".strip(" /")
            ),
            "Title / Subject": doc_data.get("subject", "") or doc_data.get("title", ""),
            "Published At": doc_data.get("pub_date", "") or doc_data.get("publication_date", ""),
            "Effective Date": doc_data.get("effective_date", ""),
            "Start Date": doc_data.get("start_date", ""),
            "End Date": doc_data.get("end_date", ""),
            "Deadline": doc_data.get("deadline", ""),
            "Summary": doc_data.get("summary", ""),
            "Key Changes": key_changes_str,
            "Action Required": doc_data.get("action_required", ""),
            "Reason for Priority": doc_data.get("reason_for_priority", ""),
            "Affected Parties": affected_str,
            "Analysis Mode": doc_data.get("analysis_mode", ""),
            "AI Model": settings.LOCAL_AI_MODEL,
            "Confidence": doc_data.get("confidence", ""),
            "Alert Sent": "Yes" if doc_data.get("alert_sent") else "No",
            "Importance Score": doc_data.get("importance_score", 0),
            "Should Publish": "Yes" if doc_data.get("should_publish") else "No",
            "Is Revision": "Yes" if doc_data.get("is_revision") else "No",
            "Processing Time (ms)": total_ms,
            "Document URL": doc_data.get("doc_url", "") or doc_data.get("official_source_url", ""),
        }

    def append_alert(self, doc_data: Dict[str, Any]) -> None:
        new_row = self._build_row(doc_data)
        doc_id_val = doc_data.get("doc_id", "") or doc_data.get("reference_number", "")

        # --- Update CSV ---
        try:
            df_new = pd.DataFrame([new_row])
            df_new.to_csv(
                self.csv_path,
                mode="a",
                header=not self.csv_path.exists(),
                index=False
            )
        except Exception as e:
            logger.error(f"Error appending to CSV: {e}")

        # --- Update Excel ---
        try:
            if self.excel_path.exists():
                df_existing = pd.read_excel(self.excel_path, sheet_name="Alerts")

                # Deduplication: don't add duplicate rows
                if not df_existing.empty and doc_id_val:
                    id_col = "Doc ID / Reference"
                    if id_col in df_existing.columns:
                        if doc_id_val in df_existing[id_col].astype(str).values:
                            logger.info(
                                f"Excel already contains '{doc_id_val}'. "
                                "Skipping duplicate append."
                            )
                            return

                # Ensure all expected columns exist (for backward compat)
                for col in COLUMNS:
                    if col not in df_existing.columns:
                        df_existing[col] = ""

                df_updated = pd.concat(
                    [df_existing, pd.DataFrame([new_row])],
                    ignore_index=True
                )
            else:
                df_updated = pd.DataFrame([new_row])

            # Atomic write via temp file → rename
            temp_excel = self.excel_path.with_suffix(".tmp.xlsx")
            with pd.ExcelWriter(temp_excel, engine="openpyxl") as writer:
                df_updated.to_excel(writer, index=False, sheet_name="Alerts")
            temp_excel.replace(self.excel_path)
            logger.info(f"Excel record saved: {doc_id_val}")

        except Exception as e:
            logger.error(f"Error writing to Excel: {e}")


excel_writer = ExcelWriter()
