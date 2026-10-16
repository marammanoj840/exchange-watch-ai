# ExchangeWatch AI — Permitted Public Data Sources Specification

## 1. Overview
ExchangeWatch AI monitors publicly available regulatory, operational, trading, and compliance releases from India's primary stock exchanges:
* **NSE (National Stock Exchange of India)**
* **BSE (BSE Limited / Bombay Stock Exchange)**

This document establishes the verified public endpoints, metadata structures, access rules, polling guidelines, and legal/ethical compliance guidelines for data ingestion.

---

## 2. NSE (National Stock Exchange of India)

### Source Overview
* **Source Name**: NSE Official Public Circulars & Exchange Communications
* **Primary URL**: `https://www.nseindia.com/resources/exchange-communication-circulars`
* **JSON API Endpoint**: `https://www.nseindia.com/api/circulars`
* **Archives Storage**: `https://nsearchives.nseindia.com/content/circulars/`
* **Access Mechanism**: HTTP GET requests with standard web browser headers (`User-Agent`, `Referer`, `Accept`)
* **Update Frequency**: Real-time / As published (Typically multiple times per hour during market hours)

### Available Metadata Fields
| Field Name | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `circNumber` | String / Number | Unique identifier for circular | `"76628"` |
| `circDisplayNo` | String | Official display reference number | `"NSE/CML/76628"` |
| `sub` | String | Title / Subject of the circular | `"Listing of Equity Shares of Swastika Infra Limited (IPO)"` |
| `circCategory` | String | Category classification | `"Listing"`, `"Trading"`, `"Surveillance"` |
| `circDepartment` | String | Originating department | `"Listing"`, `"CML"`, `"SURV"`, `"INSP"` |
| `cirDate` | String (YYYYMMDD) | Publication date code | `"20260929"` |
| `cirDisplayDate` | String | Human readable publication date | `"September 29, 2026"` |
| `circFilelink` | String (URL) | Direct download link for document | `"https://nsearchives.nseindia.com/content/circulars/CML76628.zip"` |
| `circFilename` | String | Document filename | `"CML76628.zip"` |
| `fileExt` | String | Document file extension | `"zip"`, `"pdf"` |
| `circFileSize` | String | Formatted file size | `"1.43 MB"` |

### Document Formats
* **ZIP archives** containing official PDF documents.
* **Direct PDF files**.

### Deduplication Strategy
* Unique Key: `NSE_` + `circNumber` (e.g. `NSE_76628`) or `circDisplayNo`.
* Secondary validation: Content hash (SHA-256) of extracted document text.

---

## 3. BSE (Bombay Stock Exchange)

### Source Overview
* **Source Name**: BSE Official Public Notices & Circulars
* **Primary Portal**: `https://www.bseindia.com/markets/MarketInfo/DispNoticesCirculars.aspx`
* **Official RSS Feed**: `https://www.bseindia.com/rss/notices.xml`
* **Access Mechanism**: HTTP GET requests with browser headers
* **Update Frequency**: Real-time / As published

### Available Metadata Fields
| Field Name | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `NoticeNo` | String | Official Notice Number | `"20260929-12"` |
| `Subject` | String | Title / Description | `"Trading Details of New Equity Shares"` |
| `Category` | String | Category / Segment | `"Company Data"`, `"Trading"`, `"Settlement"` |
| `NoticeDate` | String | Publication Timestamp | `"29 Sep 2026 18:30"` |
| `AttachmentUrl` | String | Direct PDF download link | `"https://www.bseindia.com/markets/MarketInfo/DownloadNotice.aspx?file=..."` |

### Document Formats
* Direct PDF documents.
* Embedded HTML table / text announcements.

### Deduplication Strategy
* Unique Key: `BSE_` + `NoticeNo` (e.g. `BSE_20260929-12`).
* Secondary validation: URL hash + Title hash.

---

## 4. Operational & Legal Compliance Rules

1. **Permitted Public Access Only**: The system strictly consumes publicly accessible RSS feeds, JSON endpoints, and HTML notices provided for public information.
2. **Zero Bypass Policy**:
   - NO CAPTCHA bypassing
   - NO anti-bot circumvention
   - NO authentication credential sharing or unauthorized proxy usage
   - NO rate limit violation
3. **Responsible Polling Rate**:
   - Normal Market Hours (08:00 - 18:00 IST): Every 10–15 seconds
   - Off-Market Hours (18:00 - 08:00 IST): Every 30–60 seconds
   - Polling requests utilize HTTP `If-Modified-Since` and `ETag` headers where supported to minimize bandwidth.
4. **Local Processing**:
   - All text extraction, OCR fallback, AI classification, and change detection run 100% locally on the host server.
   - Zero outbound transmission of document contents to paid third-party AI APIs.
