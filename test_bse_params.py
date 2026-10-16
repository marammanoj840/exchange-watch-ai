import urllib.request
import json
import ssl
from datetime import datetime

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://www.bseindia.com/'
}

today_str = datetime.now().strftime('%Y%m%d') # e.g. 20260930 or 20260929
print("Today str:", today_str)

params_list = [
    f"https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w?Cat=-1&PrevDate={today_str}&ScripCode=&Searchstr=&ToDate={today_str}&strCat=-1&strPrevDate={today_str}&strScripCode=&strSearchstr=&strToDate={today_str}",
    "https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w?Cat=-1&PrevDate=&ScripCode=&Searchstr=&ToDate=&strCat=-1&strPrevDate=&strToDate=&strScripCode=&strSearchstr=",
    "https://api.bseindia.com/BseIndiaAPI/api/GetNoticeSearch/w?strCat=-1&strSubCat=-1&strFDate=&strTDate=&strSearch=&strScripCode=",
    "https://api.bseindia.com/BseIndiaAPI/api/NoticeData/w?cat=-1&subcat=-1&fdate=&tdate=&search=&scripcode="
]

for url in params_list:
    try:
        req = urllib.request.Request(url, headers=headers)
        res = urllib.request.urlopen(req, context=ctx, timeout=10)
        data_bytes = res.read()
        print("URL:", url[:80], "...")
        print("Status:", res.status, "Length:", len(data_bytes))
        try:
            data = json.loads(data_bytes.decode('utf-8'))
            if isinstance(data, dict):
                print("  Keys:", list(data.keys()))
                if 'Table' in data and len(data['Table']) > 0:
                    print("  Sample item:", data['Table'][0])
                elif 'Table1' in data and len(data['Table1']) > 0:
                    print("  Sample item:", data['Table1'][0])
            elif isinstance(data, list) and len(data) > 0:
                print("  Sample item:", data[0])
            else:
                print("  Data:", str(data)[:150])
        except Exception as je:
            print("  Raw:", data_bytes[:150])
    except Exception as e:
        print("  Error:", e)
