import sys, os, time, json, requests, xml.etree.ElementTree as ET
from datetime import datetime
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

RESULTS = {}
TIMESTAMP = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")

TG_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "").strip()
OLLAMA_URL   = os.getenv("LOCAL_AI_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("LOCAL_AI_MODEL", "llama3.2:1b")

print("="*70)
print("SECTION 0: ENVIRONMENT INVENTORY")
print("="*70)
print(f"  TELEGRAM_BOT_TOKEN configured: {bool(TG_BOT_TOKEN)} (len={len(TG_BOT_TOKEN)})")
print(f"  TELEGRAM_CHAT_ID configured:   {bool(TG_CHAT_ID)} value={repr(TG_CHAT_ID)}")
print(f"  OLLAMA_URL:  {OLLAMA_URL}")
print(f"  OLLAMA_MODEL: {OLLAMA_MODEL}")
RESULTS["env"] = {"telegram_token_set": bool(TG_BOT_TOKEN), "telegram_chat_set": bool(TG_CHAT_ID), "ollama_url": OLLAMA_URL, "ollama_model": OLLAMA_MODEL}

# -- TEST 1: TELEGRAM ------------------------------------------------------
print("\n" + "="*70)
print("TEST 1: TELEGRAM REAL DELIVERY")
print("="*70)
tg_result = {"configured": False, "attempted": False, "delivered": False, "message_id": None}
if TG_BOT_TOKEN and TG_CHAT_ID:
    tg_result["configured"] = True
    tg_result["attempted"] = True
    test_msg = "ExchangeWatch AI REAL DELIVERY TEST\n\nTimestamp: " + TIMESTAMP + "\nThis is a real test message. If you receive this, Telegram delivery is CONFIRMED."
    tg_result["message_text"] = test_msg
    try:
        t0 = time.time()
        res = requests.post(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
                            json={"chat_id": TG_CHAT_ID, "text": test_msg}, timeout=10)
        latency_ms = (time.time()-t0)*1000
        tg_result["api_status"] = res.status_code
        tg_result["api_latency_ms"] = round(latency_ms, 1)
        resp_json = res.json()
        tg_result["api_response"] = resp_json
        if res.status_code == 200 and resp_json.get("ok"):
            msg = resp_json.get("result", {})
            tg_result["delivered"] = True
            tg_result["message_id"] = msg.get("message_id")
            tg_result["chat_id_confirmed"] = msg.get("chat", {}).get("id")
            tg_result["date_delivered_unix"] = msg.get("date")
            print(f"  DELIVERED message_id={msg.get('message_id')} latency={latency_ms:.1f}ms")
        else:
            tg_result["error"] = resp_json.get("description", "Unknown")
            print(f"  FAILED HTTP {res.status_code}: {resp_json}")
    except Exception as e:
        tg_result["exception"] = str(e)
        print(f"  EXCEPTION: {e}")
else:
    print("  SKIPPED - TELEGRAM_BOT_TOKEN and/or TELEGRAM_CHAT_ID not set in .env")
    print("  ACTION REQUIRED: Provide Telegram credentials to test real delivery")
RESULTS["telegram"] = tg_result

# -- TEST 2: BSE LIVE XML FEED ---------------------------------------------
print("\n" + "="*70)
print("TEST 2: BSE REAL LIVE XML FEED")
print("="*70)
bse_result = {"source_url": "https://www.bseindia.com/data/xml/notices.xml", "source_type": "BSE Official Public XML/RSS Feed"}
print(f"  Source: {bse_result['source_url']}")
t_detect = datetime.now()
try:
    t0 = time.time()
    res = requests.get("https://www.bseindia.com/data/xml/notices.xml",
                       headers={"User-Agent": "Mozilla/5.0", "Accept": "text/xml,application/xml,*/*"}, timeout=15)
    fetch_latency = (time.time()-t0)*1000
    bse_result["fetch_status"] = res.status_code
    bse_result["fetch_latency_ms"] = round(fetch_latency, 1)
    bse_result["response_size_bytes"] = len(res.content)
    print(f"  BSE XML Feed: HTTP {res.status_code}, {len(res.content)} bytes, {fetch_latency:.1f}ms")
    if res.status_code == 200:
        t_download = datetime.now()
        root = ET.fromstring(res.content)
        channel = root.find("channel")
        items = channel.findall("item") if channel else root.findall(".//item")
        bse_result["items_found"] = len(items)
        print(f"  Items found in feed: {len(items)}")
        if items:
            item = items[0]
            def gt(el, tag):
                c = el.find(tag)
                return c.text.strip() if c is not None and c.text else ""
            title    = gt(item, "title")
            link     = gt(item, "link")
            pub_date = gt(item, "pubDate")
            desc     = gt(item, "description")
            category = gt(item, "category") or "Notice"
            guid     = gt(item, "guid")
            bse_result["sample_item"] = {"title": title, "link": link, "pub_date": pub_date,
                                          "description": desc[:500], "category": category, "guid": guid}
            bse_result["extraction_ok"] = bool(title)
            t_extraction = datetime.now()
            print("\n  REAL BSE NOTICE (first item from live feed)")
            print(f"  Title:     {title}")
            print(f"  Link:      {link}")
            print(f"  Published: {pub_date}")
            print(f"  Category:  {category}")
            print(f"  GUID:      {guid}")
            print(f"  Desc[:300]:{desc[:300]}")
            # Fast NLP
            t_ai_start = datetime.now()
            try:
                from app.ai.fast_nlp import fast_nlp_provider
                content_text = title + " " + desc
                ai_res = fast_nlp_provider.analyze_document(title, category, content_text)
                t_ai_done = datetime.now()
                bse_result["analysis_ok"] = True
                bse_result["ai_result"] = ai_res
                bse_result["ai_method"] = "Fast NLP (rule-based)"
                bse_result["ai_latency_ms"] = round((t_ai_done-t_ai_start).total_seconds()*1000, 2)
                print(f"\n  Fast NLP: priority={ai_res.get('priority')} eff_date={ai_res.get('effective_date')}")
                print(f"  Summary: {ai_res.get('summary')[:200]}")
                print(f"  Key changes: {ai_res.get('key_changes')}")
            except Exception as e:
                bse_result["ai_error"] = str(e)
                print(f"  Fast NLP error: {e}")
            # Excel
            t_excel_start = datetime.now()
            try:
                from app.storage.excel_writer import excel_writer
                doc_data = {
                    "doc_key": f"BSE_REAL_{guid or title[:20]}", "exchange": "BSE",
                    "doc_id": guid or title[:30], "title": title, "category": category,
                    "department": "BSE Market Operations", "pub_date": pub_date, "doc_url": link,
                    "filename": "", "priority": bse_result.get("ai_result", {}).get("priority", "MEDIUM"),
                    "summary": bse_result.get("ai_result", {}).get("summary", title),
                    "effective_date": bse_result.get("ai_result", {}).get("effective_date", ""),
                    "content_hash": "", "detected_at": t_detect.strftime("%Y-%m-%d %H:%M:%S"),
                    "alert_sent": False, "latency_summary": {"total_latency_ms": round(fetch_latency, 1)},
                }
                excel_writer.append_alert(doc_data)
                t_excel_done = datetime.now()
                bse_result["excel_written"] = True
                bse_result["excel_latency_ms"] = round((t_excel_done-t_excel_start).total_seconds()*1000, 1)
                print(f"\n  Excel written in {bse_result['excel_latency_ms']}ms")
            except Exception as e:
                bse_result["excel_error"] = str(e)
                print(f"  Excel error: {e}")
            # Telegram alert
            t_tg_start = datetime.now()
            if TG_BOT_TOKEN and TG_CHAT_ID:
                try:
                    priority = bse_result.get("ai_result", {}).get("priority", "N/A")
                    alert_msg = f"BSE REAL LIVE TEST\n\nTitle: {title}\nPublished: {pub_date}\nCategory: {category}\nPriority: {priority}\nSource: https://www.bseindia.com/data/xml/notices.xml"
                    tg_res = requests.post(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
                                           json={"chat_id": TG_CHAT_ID, "text": alert_msg}, timeout=10)
                    t_tg_done = datetime.now()
                    bse_result["telegram_sent"] = tg_res.status_code == 200
                    bse_result["telegram_latency_ms"] = round((t_tg_done-t_tg_start).total_seconds()*1000, 1)
                    bse_result["telegram_api_status"] = tg_res.status_code
                    tg_json = tg_res.json()
                    bse_result["telegram_message_id"] = tg_json.get("result", {}).get("message_id")
                    print(f"  Telegram BSE alert: message_id={bse_result['telegram_message_id']} latency={bse_result['telegram_latency_ms']}ms")
                except Exception as e:
                    bse_result["telegram_error"] = str(e)
                    print(f"  Telegram error: {e}")
            else:
                bse_result["telegram_sent"] = False
                bse_result["telegram_skip_reason"] = "Credentials not configured"
                print(f"  Telegram BSE alert: SKIPPED (no credentials)")
            bse_result["timestamps"] = {
                "detection": t_detect.strftime("%Y-%m-%d %H:%M:%S.%f"),
                "download_complete": t_download.strftime("%Y-%m-%d %H:%M:%S.%f"),
                "extraction_complete": t_extraction.strftime("%Y-%m-%d %H:%M:%S.%f"),
                "ai_complete": t_ai_done.strftime("%Y-%m-%d %H:%M:%S.%f") if bse_result.get("analysis_ok") else None,
                "excel_complete": t_excel_done.strftime("%Y-%m-%d %H:%M:%S.%f") if bse_result.get("excel_written") else None,
            }
except Exception as e:
    bse_result["exception"] = str(e)
    print(f"  EXCEPTION: {e}")
    import traceback; traceback.print_exc()
RESULTS["bse"] = bse_result

# -- TEST 3: NSE LIVE API --------------------------------------------------
print("\n" + "="*70)
print("TEST 3: NSE REAL LIVE API")
print("="*70)
nse_result = {"source_url": "https://www.nseindia.com/api/circulars", "source_type": "NSE Official JSON API"}
try:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nseindia.com/resources/exchange-communication-circulars"
    })
    print("  Initializing NSE session cookies...")
    session.get("https://www.nseindia.com", timeout=10)
    t0 = time.time()
    res = session.get("https://www.nseindia.com/api/circulars", timeout=12)
    fetch_latency = (time.time()-t0)*1000
    nse_result["fetch_status"] = res.status_code
    nse_result["fetch_latency_ms"] = round(fetch_latency, 1)
    nse_result["response_size_bytes"] = len(res.content)
    print(f"  NSE API: HTTP {res.status_code}, {fetch_latency:.1f}ms, {len(res.content)} bytes")
    if res.status_code == 200:
        data = res.json()
        items = data.get("data", [])
        nse_result["items_found"] = len(items)
        print(f"  NSE Circulars found: {len(items)}")
        if items:
            item = items[0]
            nse_result["sample_item"] = {
                "circDisplayNo": item.get("circDisplayNo", ""),
                "sub": item.get("sub", ""),
                "cirDisplayDate": item.get("cirDisplayDate", ""),
                "circCategory": item.get("circCategory", ""),
                "circDepartment": item.get("circDepartment", ""),
                "circFilelink": item.get("circFilelink", ""),
            }
            print(f"\n  REAL NSE CIRCULAR (most recent):")
            for k, v in nse_result["sample_item"].items():
                print(f"  {k}: {str(v)[:100]}")
    else:
        nse_result["response_sample"] = res.text[:300]
        print(f"  Response: {res.text[:300]}")
except Exception as e:
    nse_result["exception"] = str(e)
    print(f"  NSE API error: {e}")
RESULTS["nse"] = nse_result

# -- TEST 4: LOCAL LLM -----------------------------------------------------
print("\n" + "="*70)
print("TEST 4: LOCAL LLM (Ollama llama3.2:1b)")
print("="*70)
llm_result = {"ollama_running": False, "model_available": False, "inference_attempted": False, "inference_ok": False}
try:
    r = requests.get("http://localhost:11434/api/tags", timeout=5)
    if r.status_code == 200:
        llm_result["ollama_running"] = True
        models = [m.get("name","") for m in r.json().get("models",[])]
        llm_result["available_models"] = models
        llm_result["model_available"] = any("llama3.2" in m for m in models)
        print(f"  Ollama RUNNING, models: {models}")
    else:
        print(f"  Ollama HTTP {r.status_code}")
except Exception as e:
    llm_result["ollama_error"] = str(e)
    print(f"  Ollama NOT running: ConnectionRefused localhost:11434")

# Real content from live NSE or BSE
real_title, real_category, real_content = "", "", ""
if RESULTS.get("nse", {}).get("sample_item"):
    s = RESULTS["nse"]["sample_item"]
    real_title = s.get("sub", "NSE Circular")
    real_category = s.get("circCategory", "Circular")
    real_content = f"Circular No: {s.get('circDisplayNo','')}. Subject: {real_title}. Date: {s.get('cirDisplayDate','')}."
elif RESULTS.get("bse", {}).get("sample_item"):
    s = RESULTS["bse"]["sample_item"]
    real_title = s.get("title","BSE Notice")
    real_category = s.get("category","Notice")
    real_content = f"Title: {real_title}. Published: {s.get('pub_date','')}. {s.get('description','')}"

print(f"\n  Fast NLP on real document:")
print(f"  Title: {real_title[:100]}")
try:
    from app.ai.fast_nlp import fast_nlp_provider
    t0 = time.time()
    nlp_out = fast_nlp_provider.analyze_document(real_title, real_category, real_content)
    nlp_lat = (time.time()-t0)*1000
    llm_result["fast_nlp_latency_ms"] = round(nlp_lat, 3)
    llm_result["fast_nlp_output"] = nlp_out
    print(f"  Fast NLP latency: {nlp_lat:.3f}ms")
    print(f"  Result: {json.dumps(nlp_out, indent=4)}")
except Exception as e:
    print(f"  Fast NLP error: {e}")

if llm_result["ollama_running"] and llm_result["model_available"]:
    llm_result["inference_attempted"] = True
    prompt = f"Analyze this stock exchange notice and respond only with JSON: Title={real_title} Category={real_category} Content={real_content[:800]}\nJSON schema: priority(CRITICAL/HIGH/MEDIUM/LOW), summary(1-2 sentences), effective_date, key_changes(list)"
    try:
        t0 = time.time()
        r = requests.post(OLLAMA_URL, json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"}, timeout=120)
        inf_lat = (time.time()-t0)*1000
        llm_result["inference_latency_ms"] = round(inf_lat, 1)
        if r.status_code == 200:
            raw = r.json().get("response","")
            llm_result["inference_ok"] = True
            try:
                llm_result["structured_output"] = json.loads(raw)
            except:
                llm_result["raw_response"] = raw[:500]
            print(f"  Ollama latency: {inf_lat:.1f}ms")
            print(f"  Structured output: {json.dumps(llm_result.get('structured_output', llm_result.get('raw_response')), indent=2)}")
    except Exception as e:
        llm_result["inference_error"] = str(e)
        print(f"  LLM inference error: {e}")
else:
    print("\n  Ollama NOT running on localhost:11434")
    print("  Fast NLP is the active analysis fallback")
RESULTS["llm"] = llm_result

# -- TEST 5: EXTRACTION ----------------------------------------------------
print("\n" + "="*70)
print("TEST 5: REAL EXTRACTION TEST")
print("="*70)
extract_result = {"html_test": {}, "pdf_test": {}}

# HTML from BSE
bse_link = RESULTS.get("bse",{}).get("sample_item",{}).get("link","")
if bse_link:
    print(f"  HTML extraction from: {bse_link}")
    try:
        t0 = time.time()
        r = requests.get(bse_link, headers={"User-Agent":"Mozilla/5.0"}, timeout=15)
        dl_lat = (time.time()-t0)*1000
        print(f"  HTTP {r.status_code}, {len(r.content)} bytes, {dl_lat:.1f}ms")
        if r.status_code == 200:
            from app.ingestion.extractor import extractor
            t0 = time.time()
            text, chash = extractor.extract_text(r.content, "notice.html")
            ext_lat = (time.time()-t0)*1000
            extract_result["html_test"] = {"source_url": bse_link, "http_status": r.status_code,
                                            "download_latency_ms": round(dl_lat,1), "extraction_latency_ms": round(ext_lat,1),
                                            "extracted_len_chars": len(text), "content_hash": chash,
                                            "text_sample": text[:500], "extraction_ok": bool(text.strip())}
            print(f"  Extracted: {len(text)} chars, hash={chash}")
            print(f"  Text[:300]: {text[:300]}")
    except Exception as e:
        extract_result["html_test"]["exception"] = str(e)
        print(f"  HTML extraction error: {e}")
else:
    print("  No BSE link for HTML extraction")

# PDF from NSE
nse_filelink = RESULTS.get("nse",{}).get("sample_item",{}).get("circFilelink","")
if nse_filelink:
    pdf_url = nse_filelink if nse_filelink.startswith("http") else f"https://nsearchives.nseindia.com{nse_filelink}"
    print(f"\n  PDF extraction from NSE: {pdf_url}")
    try:
        sess2 = requests.Session()
        sess2.headers.update({"User-Agent":"Mozilla/5.0","Referer":"https://www.nseindia.com"})
        sess2.get("https://www.nseindia.com", timeout=8)
        t0 = time.time()
        r = sess2.get(pdf_url, timeout=15)
        dl_lat = (time.time()-t0)*1000
        print(f"  HTTP {r.status_code}, {len(r.content)} bytes, {dl_lat:.1f}ms, {r.headers.get('Content-Type','')}")
        if r.status_code == 200:
            from app.ingestion.extractor import extractor
            fname = pdf_url.split("/")[-1] or "circular.pdf"
            t0 = time.time()
            text, chash = extractor.extract_text(r.content, fname)
            ext_lat = (time.time()-t0)*1000
            extract_result["pdf_test"] = {"source_url": pdf_url, "http_status": r.status_code,
                                           "download_latency_ms": round(dl_lat,1), "extraction_latency_ms": round(ext_lat,1),
                                           "extracted_len_chars": len(text), "content_hash": chash,
                                           "text_sample": text[:600], "extraction_ok": bool(text.strip())}
            print(f"  Extracted: {len(text)} chars, hash={chash}")
            print(f"  Text[:400]: {text[:400]}")
        else:
            extract_result["pdf_test"]["http_error"] = r.status_code
            extract_result["pdf_test"]["body"] = r.text[:200]
    except Exception as e:
        extract_result["pdf_test"]["exception"] = str(e)
        print(f"  PDF extraction error: {e}")
else:
    print("  No NSE filelink for PDF extraction")
RESULTS["extraction"] = extract_result

# -- TEST 6: SERVICE CONFIG ------------------------------------------------
print("\n" + "="*70)
print("TEST 6: SYSTEMD SERVICE FILE")
print("="*70)
svc_result = {}
try:
    with open("scripts/exchangewatch.service","r") as f:
        svc_content = f.read()
    svc_result["service_file_exists"] = True
    svc_result["has_restart_always"] = "Restart=always" in svc_content
    svc_result["has_restart_sec"] = "RestartSec" in svc_content
    svc_result["service_content"] = svc_content
    print(f"  Service file exists: OK")
    print(f"  Restart=always: {svc_result['has_restart_always']}")
    print(f"  RestartSec set: {svc_result['has_restart_sec']}")
    print(f"  Content:\n{svc_content}")
except Exception as e:
    svc_result["error"] = str(e); print(f"  ERROR: {e}")
try:
    from app.storage.db import db_manager
    svc_result["dedup_working"] = True
    k = "DEDUP_REALTEST_001"
    svc_result["dedup_already_processed"] = db_manager.is_processed(k)
    print(f"  DB dedup check: is_processed('{k}') = {svc_result['dedup_already_processed']}")
except Exception as e:
    svc_result["dedup_error"] = str(e); print(f"  DB error: {e}")
RESULTS["service"] = svc_result

# -- FINAL DUMP -------------------------------------------------------------
print("\n" + "="*70)
print("COMPLETE RESULTS JSON")
print("="*70)
print(json.dumps(RESULTS, indent=2, default=str))
with open("real_test_results.json","w") as f:
    json.dump(RESULTS, f, indent=2, default=str)
print("\nResults saved to real_test_results.json")
