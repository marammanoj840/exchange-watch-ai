import urllib.request
import json
import ssl
import re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

# 1. NSE Circulars API
print("--- TESTING NSE CIRCULARS API ---")
try:
    url = "https://www.nseindia.com/api/circulars"
    req = urllib.request.Request(url, headers=headers)
    res = urllib.request.urlopen(req, context=ctx, timeout=10)
    data = json.loads(res.read().decode('utf-8'))
    print("NSE API Status:", res.status)
    print("NSE Total Circulars retrieved:", len(data.get('data', [])))
    if data.get('data'):
        print("NSE Sample Circular:", json.dumps(data['data'][0], indent=2))
except Exception as e:
    print("NSE API Error:", e)

# 2. BSE Notices Page
print("\n--- TESTING BSE NOTICES PUBLIC PAGE ---")
try:
    url = "https://www.bseindia.com/markets/MarketInfo/DispNoticesCirculars.aspx"
    req = urllib.request.Request(url, headers=headers)
    res = urllib.request.urlopen(req, context=ctx, timeout=10)
    html = res.read().decode('utf-8', errors='ignore')
    print("BSE Page Status:", res.status)
    print("BSE Page Length:", len(html))
    
    # Extract links
    pdf_links = re.findall(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', html, re.IGNORECASE)
    print("BSE PDF links found:", len(pdf_links), pdf_links[:5])
    
    notice_nos = re.findall(r'(\d{8}-\d+|\d{10})', html)
    print("BSE Notice Numbers found:", len(notice_nos), notice_nos[:5])
except Exception as e:
    print("BSE Page Error:", e)
