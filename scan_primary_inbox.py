"""
Deep scan and analysis of user's inbox
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "backend"))

from gmail_engine import engine

def scan():
    if not engine.is_authenticated():
        print("[ERROR] Not authenticated.")
        return

    res = engine.search_messages(query="in:inbox", max_results=100)
    messages = res.get("messages", [])
    print(f"Retrieved {len(messages)} messages from Inbox:\n")

    for idx, m in enumerate(messages, 1):
        s_name = m.get("senderName", "")
        s_email = m.get("senderEmail", "")
        subj = m.get("subject", "")
        date = m.get("date", "")
        labels = m.get("labelIds", [])
        print(f"[{idx:02d}] {s_name} <{s_email}> | Subj: {subj} | Date: {date} | Labels: {labels}")

if __name__ == "__main__":
    scan()
