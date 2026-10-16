# ExchangeWatch AI — Real End-to-End Production Readiness Report

**Verification Timestamp**: 2026-09-30 16:55:09–16:55:27 IST  
**Test Runner**: `real_test_runner.py` — zero mocks, all live network calls  
**Target Host**: Oracle Cloud Always Free (ARM Ampere / Micro VM)

---

## ⚠️ Upfront Disclosure: Previous Report Was Internally Mocked

The previous report (13:50 IST) reported "PASS" for Telegram and Local LLM based on:
- Telegram: console/log simulation only (no HTTP call made)
- Ollama LLM: `Ollama Active: False` — Fast NLP only, LLM never invoked
- "142.35 ms NSE/BSE-to-Telegram latency" — internal processing only, not source-to-delivery

This report corrects all of those with real measurements.

---

## 📋 Real Test Summary

| # | Test | Real Result | Evidence |
| :-- | :-- | :--: | :-- |
| **1** | Telegram Real Delivery | ❌ **NOT TESTED** | `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are empty in `.env` |
| **2** | BSE Live XML Feed | ✅ **PASS** | HTTP 200, 28 real notices fetched, PDF downloaded, extracted, Excel written |
| **3** | NSE Live JSON API | ✅ **PASS** | HTTP 200, 184 real circulars fetched, PDF downloaded & text extracted |
| **4a** | Fast NLP Analysis | ✅ **PASS** | Latency 1.01 ms on real NSE/BSE document |
| **4b** | Ollama LLM (llama3.2:1b) | ❌ **NOT TESTED** | Ollama daemon not running on `localhost:11434` (ConnectionRefused) |
| **5** | PDF Extraction (BSE) | ✅ **PASS** | 2,571 chars extracted from real BSE PDF (notice 20260930-28) |
| **5** | PDF Extraction (NSE) | ✅ **PASS** | 2,543 chars extracted from real NSE PDF (NSE/CML/76641) |
| **6** | systemd Service Config | ✅ **PASS** | `Restart=always`, `RestartSec=5`, dedup DB accessible |
| **7** | Excel Write | ✅ **PASS** | Real BSE notice written to `output/ExchangeWatch_AI_Alerts.xlsx` |

---

## 🔍 Test 1 — Telegram Real Delivery

**Result: ❌ NOT TESTED — Missing Credentials**

- `TELEGRAM_BOT_TOKEN`: not set (empty string in `.env`)
- `TELEGRAM_CHAT_ID`: not set (empty string in `.env`)
- No Telegram API call was made. No message was sent.
- The previous report's "PASS" was a console simulation (`if not self.is_configured(): logger.info(...)`) — not a real HTTP delivery.

**To complete this test**: populate `.env` with your Telegram bot token and chat ID, then re-run `real_test_runner.py`. The code path exists and is correct; the credentials are simply absent.

---

## 🔍 Test 2 — BSE Real Live Test

**Result: ✅ PASS**

| Field | Value |
| :-- | :-- |
| **Source URL** | `https://www.bseindia.com/data/xml/notices.xml` |
| **Source Type** | BSE Official Public XML/RSS Feed (unauthenticated, no WAF block) |
| **HTTP Status** | 200 OK |
| **Feed Size** | 9,978 bytes |
| **Fetch Latency** | 1,750.8 ms |
| **Items in Feed** | 28 live BSE notices |
| **BSE Akamai WAF** | Does NOT block this XML endpoint (only blocks `api.bseindia.com` JS endpoints) |

**Real Notice Extracted (first item, 2026-09-30):**

| Field | Value |
| :-- | :-- |
| **Notice No.** | 20260930-28 |
| **Title** | Settlement Schedule Offer to Buy – Acquisition Window (Takeover) for PASUPATI FINCAP LIMITED. |
| **Published** | Wed, 30 Sep 2026 11:13:50 GMT |
| **Category** | Notice / Settlement/RMS |
| **Segment** | Equity |
| **Department** | BSECL |
| **PDF Link** | `https://www.bseindia.com/downloads/UploadDocs/Notices/20260930-28/20260930-28.pdf` |
| **Date Range in Doc** | 01/10/2026 to 15/10/2026 (Acquisition Window) |

**Fast NLP Analysis:**
- Priority: **HIGH**
- Effective Date: Immediate / As specified in source
- Key Changes: Settlement Schedule Offer to Buy – Acquisition Window (Takeover) for PASUPATI FINCAP LIMITED.

**⚠️ Note on BSE collector code mismatch**: The current `bse_collector.py` scrapes `DispNoticesCirculars.aspx` (Angular SPA — returns empty HTML, 0 tables). The **actual working BSE source** is the RSS/XML feed at `https://www.bseindia.com/data/xml/notices.xml`. The collector code **must be updated** to use this endpoint.

**Timestamps:**

| Event | Time (IST) |
| :-- | :-- |
| Detection | 16:55:09.142 |
| Download complete | 16:55:10.893 |
| Extraction complete | 16:55:10.894 |
| Fast NLP complete | 16:55:10.939 |
| Excel written | 16:55:16.777 |
| Telegram | SKIPPED (no credentials) |

---

## 🔍 Test 3 — NSE Real Live Test

**Result: ✅ PASS**

| Field | Value |
| :-- | :-- |
| **Source URL** | `https://www.nseindia.com/api/circulars` |
| **Source Type** | NSE Official JSON API |
| **HTTP Status** | 200 OK |
| **Response Size** | 81,359 bytes |
| **Fetch Latency** | 713.1 ms (including cookie init) |
| **Circulars Found** | **184** live circulars |

**Real Circular (most recent, 2026-09-30):**

| Field | Value |
| :-- | :-- |
| **Ref No.** | NSE/CML/76641 |
| **Circular Ref.** | 1748/2026 |
| **Subject** | Buyback Offer under Tender Offer scheme of Global Pet Industries Limited |
| **Date** | September 30, 2026 |
| **Category** | Listing |
| **Department** | Listing |
| **PDF Link** | `https://nsearchives.nseindia.com/content/circulars/CML76641.pdf` |

---

## 🔍 Test 4 — Local LLM Real Test

**Result: ❌ Ollama NOT running / ✅ Fast NLP PASS**

### a) Fast NLP (rule-based) — CONFIRMED WORKING

- **Document**: "Buyback Offer under Tender Offer scheme of Global Pet Industries Limited" (real NSE circular)
- **Latency**: **1.010 ms**
- **Structured output**:
```json
{
    "priority": "LOW",
    "summary": "Summary: Buyback Offer under Tender Offer scheme of Global Pet Industries Limited. Key updates: Buyback Offer under Tender Offer scheme of Global Pet Industries Limited",
    "effective_date": "Immediate / As specified in source",
    "key_changes": [
        "Buyback Offer under Tender Offer scheme of Global Pet Industries Limited"
    ]
}
```

### b) Local LLM (Ollama llama3.2:1b) — NOT TESTED

- **Status**: Ollama daemon not running on this Windows development machine (`localhost:11434` — ConnectionRefused)
- **LLM inference latency**: not measured (cannot be measured without running Ollama)
- **Note**: On the Oracle Cloud target host, Ollama must be installed and the `llama3.2:1b` model pulled before deployment. This has not been validated on the actual Oracle instance.
- **The previous "PASS" for Local AI** was a Fast NLP fallback result, not an actual Ollama inference. The previous report misrepresented this.

---

## 🔍 Test 5 — Real Extraction Test

**Result: ✅ PASS for PDF (BSE + NSE)**

### BSE PDF — Notice 20260930-28

| Field | Value |
| :-- | :-- |
| **Source** | `https://www.bseindia.com/downloads/UploadDocs/Notices/20260930-28/20260930-28.pdf` |
| **HTTP Status** | 200 OK |
| **File Size** | 379,561 bytes |
| **Download Latency** | 2,064.7 ms |
| **Extraction Latency** | 115.1 ms |
| **Extracted Text** | 2,571 characters |
| **Content Hash** | `2f0bdf699a74bef261d77161249e7ded2eac51f55b5fa3732c857ef7e8f6207f` |
| **Extraction OK** | ✅ Yes |

**Verified fields extracted:**
- Notice No.: `20260930-28`
- Notice Date: `30 Sep 2026`
- Category: `Settlement/RMS`
- Segment: `Equity`
- Department: `BSECL`
- Subject: Settlement Schedule Offer to Buy – Acquisition Window (Takeover) for PASUPATI FINCAP LIMITED.
- Settlement window dates: `01/10/2026 to 15/10/2026`

**⚠️ Limitation**: Settlement table values (bid start/end dates, obligation download dates) are partially fragmented in raw PDF text due to columnar PDF layout. Tables require post-processing for clean extraction.

### NSE PDF — Circular NSE/CML/76641

| Field | Value |
| :-- | :-- |
| **Source** | `https://nsearchives.nseindia.com/content/circulars/CML76641.pdf` |
| **HTTP Status** | 200 OK |
| **File Size** | 260,757 bytes |
| **Download Latency** | 1,039.4 ms |
| **Extraction Latency** | 96.0 ms |
| **Extracted Text** | 2,543 characters |
| **Content Hash** | `e3b582f428bbe3caff2e614c1bbca404d405b151500dfd3712e62eab7032d8f2` |
| **Extraction OK** | ✅ Yes |

**Verified fields extracted:**
- Exchange: `National Stock Exchange of India Limited`
- Department: `Listing`
- Download Ref No: `NSE/CML/76641`
- Date: `September 30, 2026`
- Circular Ref. No: `1748/2026`
- Subject: Buyback Offer under Tender Offer scheme by Global Pet Industries Limited
- Exchange circular reference: `NSE/CMTR/52776 dated June 29, 2022`

**Not tested**: scanned/image PDFs (OCR path), ZIP extraction. These code paths exist in `extractor.py` but were not exercised in this run.

---

## 🔍 Test 5 — Real End-to-End Latency

### A. Internal Processing Latency (measured on this run)

| Stage | Latency |
| :-- | --: |
| BSE XML Feed fetch | 1,750.8 ms |
| XML parse + item extraction | ~1 ms |
| Fast NLP analysis | 1.0 ms |
| Excel write | 5,839.1 ms (first-time file creation) |
| BSE PDF download | 2,064.7 ms |
| BSE PDF extraction | 115.1 ms |
| NSE PDF download | 1,039.4 ms |
| NSE PDF extraction | 96.0 ms |
| **Internal total (without Excel init)** | **~3,000–5,000 ms** |

> **Correction**: The previous "142.35 ms end-to-end latency" was measured on a mocked in-memory payload with no real network calls. It **cannot** represent NSE/BSE-to-Telegram latency. Real network-inclusive latency is ~3–5 seconds depending on document size and network conditions.

### B. Real Source-to-Alert Latency

- **Source publication time**: BSE notice `20260930-28` published at `11:13:50 GMT (16:43:50 IST)`.
- **Collector detection**: Depends on poll interval. Configured at 15 seconds (`POLL_INTERVAL_SECONDS=15`).
- **Maximum source-to-detection delay**: up to **15 seconds** (poll interval).
- **Download + extraction**: ~3–4 seconds (real network).
- **Telegram delivery** (once configured): ~300–800 ms.
- **Total source-to-Telegram (worst case)**: **15s + 4s + 0.8s ≈ ~20 seconds**
- **Total source-to-Telegram (best case)**: **<1s + 4s + 0.3s ≈ ~5–6 seconds**

This latency is appropriate for exchange monitoring. Real-time is not possible without a push-based API (none available publicly from NSE/BSE).

---

## 🔍 Test 6 — 24/7 Service

**Result: ✅ Configuration VERIFIED (runtime not testable on Windows dev machine)**

```ini
[Unit]
Description=ExchangeWatch AI — Real-Time NSE/BSE Intelligence Daemon
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/exchange-watch-ai
ExecStart=/home/ubuntu/exchange-watch-ai/venv/bin/python -m app.main
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

- `Restart=always`: ✅ Present — auto-restart on crash
- `RestartSec=5`: ✅ Present — 5-second cooldown prevents rapid loops
- `After=network.target`: ✅ Present — waits for network before starting
- SQLite dedup DB: ✅ Accessible (`db_manager.is_processed()` verified)
- Duplicate prevention: ✅ `is_processed()` checked before any download or alert

**Not testable here** (Windows dev environment): actual `systemctl` lifecycle (reboot, crash recovery, internet interruption recovery). These must be verified post-deployment on the Oracle VM.

---

## 🐛 Confirmed Bugs Requiring Fix Before Deployment

### BUG-1: BSE Collector Uses Wrong Endpoint (CRITICAL)

- **Current code**: scrapes `https://www.bseindia.com/markets/MarketInfo/DispNoticesCirculars.aspx`
- **Actual behavior**: That URL is a JavaScript SPA (Angular). HTTP-only request returns 14,287 bytes of blank shell HTML with 0 tables.
- **Working endpoint**: `https://www.bseindia.com/data/xml/notices.xml` — RSS/XML feed, returns 9,978 bytes, 28 real notices, no auth required, no Akamai WAF block.
- **Fix**: Update `bse_collector.py` to parse the XML RSS feed.

### BUG-2: Fast NLP Misclassifies "Buyback Offer" Priority

- "Buyback Offer under Tender Offer scheme" was classified as `LOW`.
- Keywords like `buyback`, `tender offer`, `acquisition` are not in the HIGH/CRITICAL keyword lists.
- This is a content classification gap, not a system failure, but will result in under-alerting on significant corporate actions.

### BUG-3: Telegram Never Tested End-to-End

- No bot token / chat ID in `.env`. Previous report marked as PASS based on log simulation.
- Must be configured and tested before deployment.

### BUG-4: Ollama Not Installed / Not Running

- No Ollama process running on `localhost:11434`.
- Local LLM analysis path has never executed a real inference.
- Must be installed on Oracle VM and tested before the LLM path can be claimed as production-ready.

### BUG-5: Excel Write Latency (5,839 ms on first write)

- First write took ~5.8 seconds (likely file creation overhead or openpyxl template loading).
- On Oracle VM this will cause the first poll cycle to be very slow.
- Subsequent writes should be faster but this should be profiled on the target hardware.

---

## 📊 Remaining Limitations

| Limitation | Impact | Mitigation |
| :-- | :-- | :-- |
| BSE collector broken (wrong endpoint) | BSE notices will never be fetched in production | Fix collector to use XML feed |
| Telegram not configured | No alerts will be delivered | Add credentials to `.env` |
| Ollama not installed | LLM analysis path untested | Install on Oracle VM |
| Scanned/image PDF OCR not tested | Some BSE documents may be image-only | Test with OCR library |
| ZIP circular extraction not tested | NSE zipped circulars not validated | Requires separate test |
| NSE API session management | API sometimes returns 403 if cookies stale | Cookie refresh logic exists; needs stress test |
| No push notification from BSE/NSE | Max detection latency = poll interval (15s) | Inherent limitation of public APIs |
| Excel first-write latency ~5.8s | Slow first cycle | Profile on Oracle; consider pre-creating file |
| systemd not tested at runtime | Crash recovery unverified | Must test on Oracle VM post-deploy |

---

## 🚀 Final Deployment Verdict

> ### ⛔ NOT READY FOR ORACLE DEPLOYMENT
>
> **Exact blocking issues:**
>
> 1. **BUG-1**: BSE collector uses wrong URL (SPA endpoint returns no data). Production BSE polling will fetch zero notices.
> 2. **Telegram unconfigured**: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are empty. No alert delivery is possible.
> 3. **Ollama uninstalled**: Local LLM has never run an actual inference. Its Oracle VM deployment, model pull, and response quality are unverified.
> 4. **Systemd lifecycle unverified**: `systemctl start/stop/restart`, reboot persistence, and crash recovery have not been exercised on a real Linux host.
>
> **What IS confirmed working (real tests, no mocks):**
> - NSE API live fetch: ✅ 184 circulars, 713 ms
> - BSE XML feed: ✅ 28 notices, 1,751 ms (via correct endpoint)
> - PDF text extraction (BSE + NSE): ✅ Real documents, real content
> - Fast NLP analysis: ✅ 1.01 ms latency on real document
> - SQLite deduplication: ✅ Verified
> - Excel write: ✅ Verified (first-write ~5.8 s)
> - systemd config file: ✅ `Restart=always`, `RestartSec=5`

---

*Last updated: 2026-09-30 16:55 IST by real_test_runner.py (zero mocks)*
