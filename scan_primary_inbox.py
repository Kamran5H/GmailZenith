"""
Prints the most recent inbox messages to the terminal.
Usage: python scan_primary_inbox.py [count] [query]
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from gmail_engine import engine  # noqa: E402


def scan(count: int = 50, query: str = "in:inbox") -> None:
    if not engine.is_authenticated():
        sys.exit("[ERROR] Not signed in. Start the dashboard (python backend/app.py) and connect Gmail first.")
    messages = engine.search_messages(query=query, max_results=count)["messages"]
    print(f"{len(messages)} message(s) for '{query}':\n")
    for idx, m in enumerate(messages, 1):
        flag = "*" if m["unread"] else " "
        print(f"{flag}[{idx:03d}] {m['senderName'][:28]:<28} | {m['subject'][:70]}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    q = " ".join(sys.argv[2:]) or "in:inbox"
    scan(n, q)
