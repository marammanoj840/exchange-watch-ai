import pytest
import os
import sqlite3
import pandas as pd
from pathlib import Path
from app.config.settings import settings
from app.storage.db import DatabaseManager
from app.storage.excel_writer import ExcelWriter
from app.ingestion.extractor import DocumentExtractor
from app.ai.fast_nlp import FastNLPProvider
from app.collectors.nse_collector import nse_collector
from app.notifications.telegram import TelegramNotifier

def test_database_deduplication(tmp_path):
    db_file = tmp_path / "test_exchangewatch.db"
    db = DatabaseManager(db_path=db_file)
    
    doc_key = "NSE_99999"
    assert not db.is_processed(doc_key)
    
    doc_data = {
        "doc_key": doc_key,
        "exchange": "NSE",
        "doc_id": "NSE/TEST/99999",
        "title": "Test Listing Circular",
        "category": "Listing",
        "department": "Listing",
        "pub_date": "2026-09-30",
        "doc_url": "http://example.com/doc.pdf",
        "priority": "HIGH",
        "summary": "Listing of Test Equity Shares",
        "alert_sent": True
    }
    db.save_document(doc_data)
    assert db.is_processed(doc_key)

def test_excel_writer(tmp_path):
    excel_file = tmp_path / "test_alerts.xlsx"
    csv_file = tmp_path / "test_alerts.csv"
    writer = ExcelWriter(excel_path=excel_file, csv_path=csv_file)
    
    doc_data = {
        "detected_at": "2026-09-30 12:00:00",
        "exchange": "NSE",
        "doc_id": "NSE/TEST/101",
        "category": "Trading",
        "department": "Market Ops",
        "priority": "CRITICAL",
        "title": "Emergency Market Halt Test",
        "effective_date": "Immediate",
        "summary": "Test alert for market halt",
        "doc_url": "http://example.com/test.pdf"
    }
    writer.append_alert(doc_data)
    
    assert excel_file.exists()
    assert csv_file.exists()
    
    df_excel = pd.read_excel(excel_file, sheet_name='Alerts')
    assert len(df_excel) == 1
    assert df_excel.iloc[0]["Doc ID / Reference"] == "NSE/TEST/101"

def test_document_extractor():
    sample_text = "<html><body><h1>NSE Circular</h1><p>Trading hours revised effective from 01/10/2026.</p></body></html>"
    text, content_hash = DocumentExtractor.extract_text(sample_text.encode('utf-8'), "circular.html")
    assert "Trading hours revised" in text
    assert len(content_hash) == 64

def test_fast_nlp_priority():
    nlp = FastNLPProvider()
    
    res1 = nlp.analyze_document(
        title="Surveillance Margin Requirement Revision",
        category="Surveillance",
        content="Notice regarding margin requirement emergency penalty."
    )
    assert res1["priority"] == "CRITICAL"
    
    res2 = nlp.analyze_document(
        title="Revision of Trading Hours",
        category="Trading",
        content="Trading hours shall be revised with effect from October 5, 2026."
    )
    assert res2["priority"] == "HIGH"
    assert "october 5, 2026" in res2["effective_date"].lower()

def test_nse_collector_fetch():
    releases = nse_collector.fetch_latest_releases()
    assert isinstance(releases, list)
    if releases:
        sample = releases[0]
        assert "doc_key" in sample
        assert sample["exchange"] == "NSE"
        assert "title" in sample
