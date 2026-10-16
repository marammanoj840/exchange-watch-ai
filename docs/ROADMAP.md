# ExchangeWatch AI — Implementation Roadmap

## Overview
This document outlines the step-by-step implementation phases for ExchangeWatch AI, prioritizing research, zero-cost architecture, low latency, local AI inference, and 24/7 reliability.

---

## Phase 0: Data Source Research & Architecture (COMPLETED)
- [x] Research official public NSE circular endpoints (`https://www.nseindia.com/api/circulars`)
- [x] Research official public BSE notices feeds (`https://www.bseindia.com/markets/MarketInfo/DispNoticesCirculars.aspx`)
- [x] Establish legal, compliance, and rate-limiting guidelines (`docs/DATA_SOURCES.md`)
- [x] Design low-latency architecture & Oracle Cloud Always Free deployment plan (`docs/ARCHITECTURE.md`)

---

## Phase 1: Core Foundation & Deduplication Engine (CURRENT)
- [ ] Create repository folder structure (`app/`, `tests/`, `output/`, `config/`)
- [ ] Implement SQLite persistent state manager (`app/storage/db.py`) for deduplication
- [ ] Implement Excel / CSV exporter (`app/storage/excel_writer.py`)
- [ ] Implement environment configuration loader (`app/config/settings.py`)

---

## Phase 2: Permitted Source Collectors & Document Ingestion
- [ ] Build **NSE Collector** (`app/collectors/nse_collector.py`)
- [ ] Build **BSE Collector** (`app/collectors/bse_collector.py`)
- [ ] Build **Document Extractor** (`app/ingestion/extractor.py`) for PDF, ZIP, and HTML text parsing
- [ ] Implement OCR fallback mechanism (`app/ingestion/ocr.py`)

---

## Phase 3: Local AI & Priority Intelligence Engine
- [ ] Create **AI Provider Abstraction** (`app/ai/provider.py`)
- [ ] Implement **Local LLM Client** (`app/ai/local_llm.py` supporting Ollama / llama.cpp)
- [ ] Implement **Fast Heuristic / Rule-based NLP Engine** (`app/ai/fast_nlp.py`) as robust fallback
- [ ] Train/configure prompt schemas for:
  - Document priority classification (CRITICAL, HIGH, MEDIUM, LOW)
  - Key change summary generation
  - Effective date extraction

---

## Phase 4: Fast Telegram Alerting & Latency Tracking
- [ ] Implement **Telegram Bot Dispatcher** (`app/notifications/telegram.py`)
- [ ] Format rich markdown message templates
- [ ] Build latency tracking module (`app/core/latency_tracker.py`) measuring end-to-end processing time
- [ ] Implement retry queue with exponential backoff

---

## Phase 5: 24/7 Service Daemon & Automated Testing
- [ ] Implement main async orchestrator loop (`app/main.py`)
- [ ] Write systemd service file (`scripts/exchangewatch.service`) for 24/7 auto-restart
- [ ] Write integration test suite (`tests/test_collectors.py`, `tests/test_ai.py`, `tests/test_notifications.py`)
- [ ] Verify Excel output generation and Telegram alert delivery

---

## Phase 6: Oracle Cloud Always Free Deployment & Verification
- [ ] Package setup script (`scripts/setup_oracle_free.sh`)
- [ ] Deploy and launch daemon on target host
- [ ] Validate 24/7 uptime, low-latency alert dispatch, and persistent logging
