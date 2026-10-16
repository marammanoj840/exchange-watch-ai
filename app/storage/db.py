"""
SQLite database manager for ExchangeWatch AI.

Responsibilities:
  - Deduplication state (is_processed)
  - Alert state persistence
  - Source health tracking
  - Restart persistence

Not used as a large document archive.
"""
import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
from app.config.settings import settings
from app.core.logger import logger


class DatabaseManager:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or settings.DATABASE_PATH)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Main documents table — primary deduplication + alert state
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_key TEXT PRIMARY KEY,
                exchange TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT,
                department TEXT,
                pub_date TEXT,
                doc_url TEXT,
                content_hash TEXT,
                priority TEXT,
                event_type TEXT,
                company_name TEXT,
                symbol TEXT,
                effective_date TEXT,
                start_date TEXT,
                end_date TEXT,
                deadline TEXT,
                action_required TEXT,
                subject TEXT,
                summary TEXT,
                key_changes TEXT,
                affected_parties TEXT,
                reason_for_priority TEXT,
                confidence TEXT,
                analysis_mode TEXT,
                detected_at TEXT NOT NULL,
                alert_sent INTEGER DEFAULT 0,
                latency_summary TEXT
            );
            """)

            # Migrate: add new columns if they don't exist (for existing databases)
            new_columns = [
                ("event_type", "TEXT"),
                ("company_name", "TEXT"),
                ("symbol", "TEXT"),
                ("start_date", "TEXT"),
                ("end_date", "TEXT"),
                ("deadline", "TEXT"),
                ("action_required", "TEXT"),
                ("subject", "TEXT"),
                ("key_changes", "TEXT"),
                ("affected_parties", "TEXT"),
                ("reason_for_priority", "TEXT"),
                ("confidence", "TEXT"),
                ("analysis_mode", "TEXT"),
                ("importance_score", "INTEGER DEFAULT 0"),
                ("should_publish", "INTEGER DEFAULT 0"),
                ("is_revision", "INTEGER DEFAULT 0"),
                ("is_duplicate", "INTEGER DEFAULT 0"),
                ("cross_exchange_ref", "TEXT"),
                ("nse_source_url", "TEXT"),
                ("bse_source_url", "TEXT"),
            ]
            for col_name, col_type in new_columns:
                try:
                    cursor.execute(
                        f"ALTER TABLE documents ADD COLUMN {col_name} {col_type};"
                    )
                except sqlite3.OperationalError:
                    pass  # Column already exists

            # Source health table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS source_status (
                source_name TEXT PRIMARY KEY,
                last_poll_time TEXT,
                last_success_time TEXT,
                status TEXT,
                error_message TEXT
            );
            """)
            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    def is_processed(self, doc_key: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM documents WHERE doc_key = ?", (doc_key,))
            return cursor.fetchone() is not None

    def get_document(self, doc_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve existing document by doc_key."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM documents WHERE doc_key = ?", (doc_key,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_cross_exchange_duplicate(
        self, exchange: str, content_hash: str = "", company_name: str = "", title: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Check if the same document exists on another exchange.
        Matches by identical content_hash (non-empty) or matching company and similar title.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if content_hash:
                cursor.execute(
                    "SELECT * FROM documents WHERE exchange != ? AND content_hash = ? AND content_hash != '' LIMIT 1",
                    (exchange, content_hash)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)

            if company_name and title:
                cursor.execute(
                    "SELECT * FROM documents WHERE exchange != ? AND company_name = ? AND title = ? LIMIT 1",
                    (exchange, company_name, title)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)

            return None

    def save_document(self, doc_data: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO documents (
                doc_key, exchange, doc_id, title, category, department, pub_date,
                doc_url, content_hash, priority, event_type, company_name, symbol,
                effective_date, start_date, end_date, deadline, action_required,
                subject, summary, key_changes, affected_parties, reason_for_priority,
                confidence, analysis_mode, detected_at, alert_sent, latency_summary,
                importance_score, should_publish, is_revision, is_duplicate,
                cross_exchange_ref, nse_source_url, bse_source_url
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?
            )
            """, (
                doc_data["doc_key"],
                doc_data.get("exchange", ""),
                doc_data.get("doc_id", ""),
                doc_data.get("title", ""),
                doc_data.get("category", ""),
                doc_data.get("department", ""),
                doc_data.get("pub_date", ""),
                doc_data.get("doc_url", "") or doc_data.get("official_source_url", ""),
                doc_data.get("content_hash", ""),
                doc_data.get("priority", "MEDIUM"),
                doc_data.get("event_type", "OTHER"),
                doc_data.get("company_name", ""),
                doc_data.get("symbol", ""),
                doc_data.get("effective_date", ""),
                doc_data.get("start_date", ""),
                doc_data.get("end_date", ""),
                doc_data.get("deadline", ""),
                doc_data.get("action_required", ""),
                doc_data.get("subject", ""),
                doc_data.get("summary", ""),
                json.dumps(doc_data.get("key_changes", [])),
                json.dumps(doc_data.get("affected_parties", [])),
                doc_data.get("reason_for_priority", ""),
                doc_data.get("confidence", ""),
                doc_data.get("analysis_mode", ""),
                doc_data.get("detected_at", datetime.now().isoformat()),
                1 if doc_data.get("alert_sent") else 0,
                json.dumps(doc_data.get("latency_summary", {})),
                int(doc_data.get("importance_score", 0)),
                1 if doc_data.get("should_publish") else 0,
                1 if doc_data.get("is_revision") else 0,
                1 if doc_data.get("is_duplicate") else 0,
                doc_data.get("cross_exchange_ref", ""),
                doc_data.get("nse_source_url", ""),
                doc_data.get("bse_source_url", ""),
            ))
            conn.commit()

    def update_source_status(
        self, source_name: str, status: str, error_message: str = ""
    ) -> None:
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO source_status (
                source_name, last_poll_time, last_success_time, status, error_message
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_name) DO UPDATE SET
                last_poll_time = excluded.last_poll_time,
                last_success_time = CASE
                    WHEN excluded.status = 'OK' THEN excluded.last_poll_time
                    ELSE source_status.last_success_time
                END,
                status = excluded.status,
                error_message = excluded.error_message
            """, (
                source_name,
                now,
                now if status == "OK" else None,
                status,
                error_message
            ))
            conn.commit()

    def get_recent_documents(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM documents ORDER BY detected_at DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_pending_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve documents that were flagged for publication but failed to send."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM documents WHERE should_publish = 1 AND alert_sent = 0 ORDER BY detected_at ASC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def mark_alert_sent(self, doc_key: str, alert_sent: bool = True) -> None:
        """Update alert_sent status for a document."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE documents SET alert_sent = ? WHERE doc_key = ?",
                (1 if alert_sent else 0, doc_key)
            )
            conn.commit()


db_manager = DatabaseManager()

