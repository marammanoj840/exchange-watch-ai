import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from app.collectors.base import BaseCollector
from app.core.logger import logger

class BSECollector(BaseCollector):
    @property
    def exchange_name(self) -> str:
        return "BSE"

    # BSE Official Public XML/RSS Feed (unauthenticated, no Akamai WAF block).
    # The Angular SPA at DispNoticesCirculars.aspx returns 0 rows via HTTP-only requests.
    BSE_XML_FEED = "https://www.bseindia.com/data/xml/notices.xml"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/xml,application/xml,application/rss+xml,*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.bseindia.com",
        })

    def _get_text(self, element, tag: str) -> str:
        child = element.find(tag)
        return child.text.strip() if child is not None and child.text else ""

    def fetch_latest_releases(self) -> List[Dict[str, Any]]:
        releases = []
        try:
            res = self.session.get(self.BSE_XML_FEED, timeout=15)
            if res.status_code != 200:
                logger.warning(f"BSE XML feed returned HTTP {res.status_code}")
                return releases

            root = ET.fromstring(res.content)
            channel = root.find("channel")
            items = channel.findall("item") if channel else root.findall(".//item")

            for item in items:
                title    = self._get_text(item, "title")
                link     = self._get_text(item, "link")
                pub_date = self._get_text(item, "pubDate")
                desc     = self._get_text(item, "description")
                category = self._get_text(item, "category") or "Notice"
                guid     = self._get_text(item, "guid")

                if not title:
                    continue

                doc_url = link or guid
                # Derive notice ID from URL path (e.g. 20260930-28 from .../Notices/20260930-28/...)
                notice_id = ""
                if doc_url:
                    parts = [p for p in doc_url.split("/") if p and not p.endswith(".pdf")]
                    notice_id = parts[-1] if parts else doc_url.split("/")[-1].replace(".pdf","")

                doc_key = f"BSE_{notice_id or title[:30]}"

                releases.append({
                    "doc_key": doc_key,
                    "exchange": "BSE",
                    "doc_id": notice_id or title[:40],
                    "title": title,
                    "category": category,
                    "department": "BSE Market Operations",
                    "pub_date": pub_date,
                    "doc_url": doc_url,
                    "filename": doc_url.split("/")[-1] if doc_url else f"{notice_id}.pdf",
                    "description": desc,
                })

        except ET.ParseError as e:
            logger.error(f"BSE XML feed parse error: {e}")
        except Exception as e:
            logger.error(f"Error fetching BSE notices from XML feed: {e}")

        return releases

bse_collector = BSECollector()
