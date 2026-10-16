import urllib.request
import json
import ssl
import re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://www.bseindia.com/markets/MarketInfo/DispNoticesCirculars.aspx',
    'Origin': 'https://www.bseindia.com'
}

# Test BSE AJAX / REST endpoints used on the site
urls_to_test = [
    "https://api.bseindia.com/BseIndiaAPI/api/Notice/w?scripcode=&strCat=-1&strPrevDate=&strToDate=&strSearch=",
    "https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w?strCat=-1&strPrevDate=&strToDate=&strScrip=&strSearch=",
    "https://www.bseindia.com/markets/MarketInfo/NoticesCirculars.aspx",
    "https://api.bseindia.com/BseIndiaAPI/api/GetNotices/w?dt="
]

for u in urls_to_test:
    try:
        req = urllib.request.Request(u, headers=headers)
        res = urllib.request.urlopen(req, context=ctx, timeout=10)
        content = res.read().decode('utf-8', errors='ignore')
        print(f"URL: {u} | Status: {res.status} | Length: {len(content)}")
        if content.startswith('{') or content.startswith('['):
            data = json.loads(content)
            print(" JSON keys/sample:", str(data)[:200])
        else:
            print(" Content snippet:", content[:200].replace('\n', ' '))
    except Exception as e:
        print(f"URL: {u} | Error: {e}")
