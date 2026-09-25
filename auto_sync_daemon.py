"""
Gmail Zenith - background Auto-Clean daemon.

Runs the Auto-Clean rules (configured on the dashboard's Auto-Clean tab)
every `interval_minutes`. Waits quietly until you have signed in.

Usage:
    python auto_sync_daemon.py          # run forever
    python auto_sync_daemon.py --once   # run the rules once and exit
"""

from __future__ import annotations

from pathlib import Path
import sys
import time

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "backend"))

import auto_sync  # noqa: E402
from gmail_engine import engine  # noqa: E402


def run_once() -> bool:
    if not engine.is_authenticated() and not engine.load_credentials():
        print("[AutoSync] Not signed in yet - open the dashboard and connect Gmail.")
        return False
    entry = auto_sync.run_rules(engine)
    print(f"[AutoSync] {entry['timestamp']}: cleaned {entry['totalCleaned']} message(s) "
          f"in {entry['durationSeconds']}s. Inbox now {entry['inboxMessagesRemaining']}.")
    for name, err in entry["errors"].items():
        print(f"[AutoSync]   ! {name}: {err}")
    return True


def main() -> None:
    if "--once" in sys.argv:
        sys.exit(0 if run_once() else 1)

    print("[AutoSync] Daemon started. Press Ctrl+C to stop.")
    while True:
        cfg = auto_sync.load_config()
        if cfg["enabled"]:
            try:
                run_once()
            except Exception as e:
                print(f"[AutoSync] Run failed: {e}")
        time.sleep(max(5, cfg["interval_minutes"]) * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[AutoSync] Stopped.")
