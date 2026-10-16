from dotenv import load_dotenv
load_dotenv()
import os, requests

token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
r = requests.get("https://api.telegram.org/bot" + token + "/getUpdates", timeout=10)

print("HTTP status:", r.status_code)
data = r.json()
print("Telegram ok:", data.get("ok"))

results = data.get("result", [])
print("Updates found:", len(results))

seen = set()
for upd in results:
    for key in ("message", "edited_message", "channel_post", "my_chat_member", "chat_member"):
        msg = upd.get(key)
        if msg:
            chat = msg.get("chat", {})
            cid = chat.get("id")
            if cid and cid not in seen:
                seen.add(cid)
                ctype = chat.get("type", "")
                cname = chat.get("first_name") or chat.get("title") or chat.get("username") or ""
                print("  Chat ID:  ", cid)
                print("  Chat type:", ctype)
                print("  Chat name:", cname)
            break

if not results:
    print("No updates found. Ensure you sent /start to @ExchangeWatchMonitor_bot in Telegram, then retry.")
