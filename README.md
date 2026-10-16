# ExchangeWatch AI — Real-Time NSE/BSE Information Intelligence & Alerting System

**ExchangeWatch AI** continuously monitors permitted, publicly available regulatory and market releases published by India's National Stock Exchange (NSE) and Bombay Stock Exchange (BSE). It detects new or updated circulars and notices, extracts content, analyzes importance using local open-source AI or deterministic Fast NLP, appends structured audit records to SQLite and Excel, and dispatches near-real-time alerts to private Telegram chats and public channels.

---

## 🌟 Key Features

1. **Permitted Public Data Monitoring**: Responsible, low-latency monitoring of official NSE circulars (`https://www.nseindia.com/api/circulars`) and BSE notices (`https://www.bseindia.com/data/xml/notices.xml`).
2. **Zero Paid APIs / 100% Free**: Operates using open-source local AI (Ollama / llama.cpp) and deterministic rule-based Fast NLP fallback.
3. **Smart Materiality & Taxonomy Classification**: 15 distinct disclosure categories with deterministic rules that prioritize critical events (management changes, defaults, trading halts, M&A) while suppressing routine administrative filings.
4. **Dual Telegram Alerting**: Dispatches structured, actionable alerts with official source links to both private administrator chats and broadcast channels.
5. **Persistent Deduplication & Revision Tracking**: SQLite state manager prevents duplicate alerts across application restarts and accurately flags amendments, revisions, and corrigenda.
6. **Excel & CSV Audit Trail**: Automatically logs every processed filing with latency breakdowns, key facts, and analysis mode to `output/ExchangeWatch_AI_Alerts.xlsx` and `output/ExchangeWatch_AI_Alerts.csv`.
7. **End-to-End Latency Tracking**: Tracks detection, download, extraction, AI analysis, and notification latency in milliseconds.
8. **Cloud & Local Deployment**: Runs seamlessly on local Windows/Linux machines or 24/7 on lightweight cloud instances such as Oracle Cloud Always Free ($0.00/month).

---

## 📂 Project Structure

```text
exchange-watch-ai/
├── app/
│   ├── ai/                      # Intelligence layer
│   │   ├── analysis_schema.py   # Normalized event taxonomy & schema definitions
│   │   ├── fast_nlp.py          # Deterministic heuristic NLP engine (<5ms)
│   │   ├── importance.py        # 100-point importance scoring & suppression rules
│   │   ├── local_llm.py         # Ollama / llama.cpp local LLM client
│   │   ├── materiality.py       # Regulatory materiality criteria & evidence rules
│   │   ├── provider.py          # Abstract AI provider interface
│   │   ├── taxonomy.py          # Event classification & keyword mappings
│   │   └── validator.py         # Deterministic fact verification & conflict resolution
│   ├── collectors/              # Data ingestion collectors
│   │   ├── base.py              # Base collector interface
│   │   ├── bse_collector.py     # BSE official XML/RSS notices collector
│   │   └── nse_collector.py     # NSE official JSON circulars collector
│   ├── config/
│   │   └── settings.py          # Environment settings & configuration loading
│   ├── core/
│   │   ├── latency_tracker.py   # Latency benchmarking & stage tracking
│   │   └── logger.py            # Unified structured logging
│   ├── ingestion/
│   │   ├── extractor.py         # PDF text & ZIP archive decompression
│   │   └── ocr.py               # Tesseract OCR fallback engine
│   ├── notifications/
│   │   └── telegram.py          # Telegram private chat & channel alert formatting
│   ├── storage/
│   │   ├── db.py                # SQLite state manager & deduplication store
│   │   └── excel_writer.py      # Thread-safe atomic Excel (.xlsx) & CSV writer
│   └── main.py                  # 24/7 master service daemon orchestrator
├── docs/                        # Architecture & compliance specifications
│   ├── ARCHITECTURE.md          # Architectural blueprints & dataflow
│   ├── DATA_SOURCES.md          # Permitted public data source guidelines
│   ├── PRODUCTION_READINESS.md  # Production hardening report
│   ├── ROADMAP.md               # Feature implementation milestones
│   └── TEST_REPORT.md           # Test evaluation & verification report
├── scripts/                     # Automation & deployment scripts
│   ├── exchangewatch.service    # Systemd 24/7 Linux daemon definition
│   ├── flush_pending_alerts.py  # Utility to dispatch queued publishable alerts
│   └── setup_oracle_free.sh     # One-click Ubuntu/Oracle Linux deployment script
├── tests/                       # Comprehensive automated test suite
│   ├── fixtures/                # 50-sample labeled market disclosure evaluation set
│   ├── test_all.py              # Core unit tests
│   ├── test_e2e_pipeline.py     # Full end-to-end pipeline & revision tests
│   ├── test_hardening.py        # Error recovery & boundary tests
│   ├── test_labeled_evaluation.py # 100% precision & recall verification
│   ├── test_phase6.py           # Structured schema & channel dispatch tests
│   └── test_taxonomy_and_importance.py # Importance scoring & suppression tests
├── .env.example                 # Environment configuration template
├── .gitignore                   # Security rules excluding credentials & databases
├── pytest.ini                   # Pytest test configuration
├── README.md                    # Project documentation
└── requirements.txt             # Dependency manifest
```

---

## 🛠️ Requirements

- **Python**: Version 3.9, 3.10, 3.11, or 3.12 (Python 3.11 recommended)
- **Git**: Version 2.20+
- **Operating System**: Windows 10/11, Linux (Ubuntu/Debian/RHEL/Oracle Linux), or macOS
- **Optional**:
  - [Ollama](https://ollama.com/) (for local neural inference with `llama3.2:1b`)
  - [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (for scanned image PDF extraction)

---

## 🚀 Setup & Installation (Windows PowerShell)

### 1. Clone the Repository
```powershell
git clone https://github.com/marammanoj840/exchange-watch-ai.git
Set-Location "exchange-watch-ai"
```

### 2. Set Up Python Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```

Open `.env` in your text editor and configure:
```env
# Telegram Configuration
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
TELEGRAM_CHAT_ID=your_numeric_chat_id

# Optional: Telegram Channel Feed
TELEGRAM_CHANNEL_ENABLED=true
TELEGRAM_CHANNEL_ID=-1001234567890

# Polling Interval (seconds)
POLL_INTERVAL_SECONDS=15

# Local AI Configuration (Ollama)
LOCAL_AI_ENABLED=true
LOCAL_AI_URL=http://localhost:11434/api/generate
LOCAL_AI_MODEL=llama3.2:1b
LOCAL_AI_SELECTIVE=true
AI_PROCESSING_MODE=FAST_NLP_FIRST

# Storage Paths
DATABASE_PATH=data/exchangewatch.db
EXCEL_OUTPUT_PATH=output/ExchangeWatch_AI_Alerts.xlsx
CSV_OUTPUT_PATH=output/ExchangeWatch_AI_Alerts.csv
```

### 4. Running the Test Suite
Verify that all 72 tests pass:
```powershell
python -m pytest tests/ -v
```

### 5. Running the 24/7 Monitoring Daemon
```powershell
python -m app.main
```

---

## 📱 Telegram Configuration

### Private Bot Chat:
1. Message `@BotFather` on Telegram to create a bot and receive your `TELEGRAM_BOT_TOKEN`.
2. Start a chat with your bot and send `/start`.
3. Run the helper script to detect your numeric chat ID:
   ```powershell
   python get_chat_id.py
   ```
4. Set `TELEGRAM_CHAT_ID` in `.env`.

### Public/Private Channel:
1. Create a Telegram Channel.
2. Add your bot to the channel as an **Administrator** with **Post Messages** permission.
3. Set `TELEGRAM_CHANNEL_ENABLED=true`.
4. Set `TELEGRAM_CHANNEL_ID` to your channel username (e.g., `@mychannel`) or channel ID (e.g., `-100...`).

---

## 🗄️ Database & Excel Behavior

- **SQLite Database (`data/exchangewatch.db`)**:
  - Tracks all processed document keys (`doc_key`), timestamps, deduplication hashes, and alert states.
  - Automatically handles cross-exchange matching between NSE and BSE releases.
  - Excluded from Git version control to protect runtime state.
- **Excel & CSV Audit Trail (`output/ExchangeWatch_AI_Alerts.xlsx`)**:
  - Appends every processed disclosure with structured metadata, priority, latency, and full analysis.
  - Writes atomically to prevent file corruption.
  - Excluded from Git version control.

---

## 🔒 Security Precautions

- **Never commit `.env` or production databases**: The repository `.gitignore` strictly protects `.env`, `.db`, `.xlsx`, and log files.
- **Zero Ingestion of Paid Remote APIs**: All AI inference is performed locally or deterministically; no proprietary disclosure data is sent to external AI servers.
- **Responsible Polling**: Adheres to exchange bandwidth policies with polite polling headers and exponential retry backoffs.

---

## ⚠️ Known Limitations

1. **Scanned PDF OCR**: While text-based PDFs extract instantly (<20ms), scanned image documents depend on system-installed `tesseract`. If Tesseract is not installed, the system falls back to headline and metadata parsing without interrupting the pipeline.
2. **Disclaimer**: ExchangeWatch AI is an informational alert and compliance tool. It is not an automated trading execution platform and does not offer financial advice.

---

## 📄 License

This project is licensed under the Apache 2.0 License.
