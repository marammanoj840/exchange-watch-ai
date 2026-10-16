from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseCollector(ABC):
    @property
    @abstractmethod
    def exchange_name(self) -> str:
        pass

    @abstractmethod
    def fetch_latest_releases(self) -> List[Dict[str, Any]]:
        """
        Fetches permitted public releases from the exchange.
        Returns a list of dictionaries with standard keys:
        {
            "doc_key": "NSE_76628",
            "exchange": "NSE",
            "doc_id": "76628",
            "title": "Listing of Equity Shares...",
            "category": "Listing",
            "department": "Listing",
            "pub_date": "2026-09-29",
            "doc_url": "https://nsearchives.nseindia.com/...",
            "filename": "CML76628.zip"
        }
        """
        pass
