# ExchangeWatch AI — System Architecture

## 1. High-Level Architecture

ExchangeWatch AI is designed as a **resilient, low-latency, modular event-driven service** built for 24/7 continuous operation on lightweight cloud infrastructure (such as Oracle Cloud Always Free VM or local Linux/Windows servers).

```text
 ┌─────────────────────────────────────────────────────────────┐
 │                    OFFICIAL PUBLIC SOURCES                  │
 │             NSE (JSON API)       BSE (Notices/RSS)          │
 └──────────────────────┬──────────────────────┬───────────────┘
                        │                      │
                        ▼                      ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                SOURCE COLLECTORS & MONITOR                  │
 │   - Responsible Polling (10-15s interval)                   │
 │   - Header Management & Conditional Requests               │
 └──────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │              DEDUPLICATION & STATE ENGINE                   │
 │   - Persistent SQLite State Store                           │
 │   - Fast Hash & External ID Check (Idempotent)              │
 └──────────────────────────────┬──────────────────────────────┘
                                │ (New Release Detected)
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │             DOCUMENT INGESTION & TEXT EXTRACTOR             │
 │   - PDF Text Extractor (pdfplumber / pypdf)                │
 │   - ZIP Extractor (Auto decompress NSE circulars)          │
 │   - OCR Fallback (pytesseract / pdf2image)                 │
 └──────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                  FAST ALERT PIPELINE (STAGE 1)              │
 │   - Priority Classification (CRITICAL / HIGH / MEDIUM / LOW)│
 │   - Key Summary & Change Extraction (Local AI / NLP)        │
 └──────────────────────┬──────────────────────┬───────────────┘
                        │                      │
                        ▼                      ▼
 ┌─────────────────────────────┐   ┌───────────────────────────┐
 │   TELEGRAM ALERT SENDER     │   │   EXCEL & CSV PERSISTENCE │
 │ - Instant Markdown Alerts   │   │ - openpyxl / pandas       │
 │ - Rate limit & Retry Queue  │   │ - ExchangeWatch_Alerts    │
 └─────────────────────────────┘   └───────────────────────────┘
```

---

## 2. Core Subsystems

### 2.1 Source Collectors (`app/collectors/`)
* **NSE Collector**: Queries `https://www.nseindia.com/api/circulars` with standard browser headers. Parses circular number, title, department, date, and document download link.
* **BSE Collector**: Queries BSE notices feed / HTML table. Parses notice number, subject, category, publish date, and notice document link.
* **Resilience**: Independent execution loop for NSE and BSE. If NSE network fails, BSE continues unimpeded.

### 2.2 Deduplication Engine (`app/storage/`)
* **SQLite Store (`exchangewatch.db`)**: Tracks all processed document IDs (`exchange_id + doc_id`), publication timestamps, hash fingerprints, and alert dispatch status.
* Prevents duplicate alerts even across application restarts, server reboots, or network disconnects.

### 2.3 Document Ingestion & Extractor (`app/ingestion/`)
* Downloads document payloads (PDF, ZIP, HTML).
* Automatically extracts ZIP contents to inspect nested PDF circulars.
* Extracts plaintext using Python libraries (`pypdf` / `pdfplumber`).
* **OCR Fallback**: Invokes `pytesseract` / OCR if PDF contains scanned image pages.

### 2.4 Local AI & NLP Intelligence (`app/ai/`)
* Uses **Local AI Provider** abstraction supporting:
  1. **Ollama / llama.cpp**: Local LLM endpoint (e.g. `llama3.2:1b`, `mistral`, `qwen2.5:1.5b`)
  2. **Fast Heuristic / Rule-based NLP Fallback**: Regex patterns for priority keyword scoring, date parsing, effective date identification, and change summary extraction.
* Ensures 100% notification availability even if local LLM service is temporarily starting or offline.

### 2.5 Telegram Alert Service (`app/notifications/`)
* Formats concise, urgent Telegram alerts in GitHub Markdown style.
* Displays:
  - 🚨 **Priority Header** (CRITICAL / HIGH / MEDIUM / LOW)
  - 🏛️ **Exchange & Department**
  - 📌 **Title / Subject**
  - 📝 **Summary & What Changed**
  - 📅 **Effective Date** (if specified)
  - 🔗 **Direct Official Source Link**
* Built-in retry queue with exponential backoff.

### 2.6 Excel / CSV Storage (`app/storage/excel_writer.py`)
* Automatically appends new alerts to `output/ExchangeWatch_AI_Alerts.xlsx` (and CSV fallback).
* Columns:
  1. `Timestamp` (System detection time)
  2. `Exchange` (NSE / BSE)
  3. `Doc ID / Reference`
  4. `Category / Department`
  5. `Priority`
  6. `Title / Subject`
  7. `Effective Date`
  8. `Summary & Key Changes`
  9. `Official Source URL`

---

## 3. Latency Optimization Strategy
1. **Short-Circuit Alerting**: First alert sends immediately after Fast AI / NLP analysis.
2. **Zero Unnecessary Blocking**: Heavy embeddings, vector indexing, or archival runs asynchronously after the Telegram message is dispatched.
3. **Internal Timestamp Tracking**: Measures latency from `detected_at` to `alert_sent_at` in milliseconds.

---

## 4. Oracle Cloud Always Free Resource Blueprint
* **Compute**: 1 ARM Ampere A1 instance (4 OCPUs, 24 GB RAM) or 1 Micro instance (1 OCPU, 1 GB RAM).
* **OS**: Ubuntu 22.04 LTS / Debian 12 / AlmaLinux.
* **Service Management**: Systemd service (`exchangewatch.service`) for automatic restart on crash or reboot.
* **Total Resource Cost**: **$0.00 / month (100% Free)**.
