import requests
from typing import List, Dict, Any
from app.collectors.base import BaseCollector
from app.core.logger import logger

class NSECollector(BaseCollector):
    @property
    def exchange_name(self) -> str:
        return "NSE"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.nseindia.com/resources/exchange-communication-circulars'
        })
        self._init_cookies()

    def _init_cookies(self) -> None:
        try:
            # Touch home page to initialize session cookies
            self.session.get('https://www.nseindia.com', timeout=8)
        except Exception as e:
            logger.debug(f"NSE cookie init warning: {e}")

    def fetch_latest_releases(self) -> List[Dict[str, Any]]:
        releases = []
        try:
            url = "https://www.nseindia.com/api/circulars"
            res = self.session.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                items = data.get("data", [])
                for item in items:
                    circ_num = str(item.get("circNumber", "") or item.get("circDisplayNo", ""))
                    if not circ_num:
                        continue

                    doc_key = f"NSE_{circ_num}"
                    doc_url = item.get("circFilelink", "")
                    if doc_url and not doc_url.startswith("http"):
                        doc_url = f"https://nsearchives.nseindia.com{doc_url}"

                    releases.append({
                        "doc_key": doc_key,
                        "exchange": "NSE",
                        "doc_id": item.get("circDisplayNo", circ_num),
                        "title": item.get("sub", "NSE Circular"),
                        "category": item.get("circCategory", "General"),
                        "department": item.get("circDepartment", item.get("fileDept", "NSE")),
                        "pub_date": item.get("cirDisplayDate", item.get("cirDate", "")),
                        "doc_url": doc_url,
                        "filename": item.get("circFilename", f"{circ_num}.zip")
                    })
            else:
                logger.warning(f"NSE Collector API returned status {res.status_code}")
                # Refresh session cookies on failure
                self._init_cookies()
        except Exception as e:
            logger.error(f"Error fetching NSE circulars: {e}")

        return releases

nse_collector = NSECollector()
