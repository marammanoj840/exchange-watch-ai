"""
Flush and dispatch pending publishable alerts to Telegram.
"""
import time
from app.storage.db import db_manager
from app.notifications.telegram import telegram_notifier
from app.core.logger import logger

def flush():
    alerts = db_manager.get_pending_alerts(limit=50)
    print(f"Found {len(alerts)} pending publishable alerts to dispatch.")
    for idx, doc in enumerate(alerts, start=1):
        doc_key = doc.get("doc_key")
        title = doc.get("title", "")
        print(f"[{idx}/{len(alerts)}] Dispatching {doc_key}: {title[:60]}...")
        try:
            sent = telegram_notifier.send_alert(doc)
            if sent:
                db_manager.mark_alert_sent(doc_key, True)
                print(f"  -> Delivered {doc_key}")
            else:
                print(f"  -> Failed {doc_key}")
        except Exception as e:
            print(f"  -> Error for {doc_key}: {e}")
        time.sleep(1.2)
    print("All pending alerts processed.")

if __name__ == "__main__":
    flush()
