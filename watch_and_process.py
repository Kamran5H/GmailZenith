"""
Background Watcher & Auto-Processor for Gmail Zenith Pro
Watches for OAuth token completion and immediately executes full inbox cleanup & triage.
"""

import os
from pathlib import Path
import sys
import time

BASE_DIR = Path(__file__).resolve().parent
TOKEN_PATH = BASE_DIR / "token.json"

sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "backend"))

from auto_process_inbox import run_full_inbox_triage

def watch():
    print("[WATCHER] Waiting for token.json to be created upon Google sign-in...")
    max_wait = 180  # 3 minutes
    start_time = time.time()

    while time.time() - start_time < max_wait:
        if TOKEN_PATH.exists():
            print("\n[OK] token.json detected! Executing automatic inbox triage...")
            time.sleep(1)
            run_full_inbox_triage()
            return True
        time.sleep(2)

    print("[WATCHER] Timed out waiting for token.json. Run auto_process_inbox.py after signing in.")
    return False

if __name__ == "__main__":
    watch()
