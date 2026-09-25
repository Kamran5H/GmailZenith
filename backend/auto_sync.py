"""
Auto-Clean rules for Gmail Zenith.

A rule is a Gmail search query plus an action (trash / archive / read).
Rules run from the dashboard ("Run now") or on a timer via `auto_sync.py`
at the repo root. Starred mail is never touched.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "auto_sync_config.json"
HISTORY_PATH = BASE_DIR / "auto_sync_log.json"
HISTORY_LIMIT = 200

RULE_ACTIONS = ("trash", "archive", "read")

DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "interval_minutes": 15,
    "max_per_rule": 500,
    "rules": [
        {"name": "Promotions in inbox", "query": "in:inbox category:promotions", "action": "trash", "enabled": True},
        {"name": "Social in inbox", "query": "in:inbox category:social", "action": "trash", "enabled": True},
        {"name": "Spam folder", "query": "in:spam", "action": "trash", "enabled": True},
        {"name": "Quora & digests", "query": "(quora OR quoradigest) in:inbox", "action": "trash", "enabled": True},
        {"name": "OctaFX trading", "query": "octafx in:inbox", "action": "trash", "enabled": True},
        {"name": "Askari Bank alerts", "query": "(askari OR askaribank) in:inbox", "action": "trash", "enabled": True},
        {"name": "Snapchat alerts", "query": "(snapchat OR from:snapchat.com) in:inbox", "action": "trash", "enabled": True},
        {"name": "Booking / tickets", "query": "(from:bookmepk.com OR from:faisalmovers.com) in:inbox",
         "action": "trash", "enabled": True},
    ],
}

_run_lock = threading.Lock()
_status: Dict[str, Any] = {"running": False, "startedAt": None}


def _migrate(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Converts the v1 format (purge_* flags + custom_rules) to a single rules list."""
    if "rules" in cfg:
        return cfg
    rules: List[Dict[str, Any]] = []
    for flag, name, query in (
        ("purge_promotions", "Promotions in inbox", "in:inbox category:promotions"),
        ("purge_social", "Social in inbox", "in:inbox category:social"),
        ("purge_spam", "Spam folder", "in:spam"),
    ):
        rules.append({"name": name, "query": query, "action": "trash", "enabled": bool(cfg.get(flag, True))})
    for r in cfg.get("custom_rules", []):
        rules.append({"name": r.get("name", "Rule"), "query": r.get("query", ""), "action": "trash",
                      "enabled": bool(r.get("enabled", True))})
    return {
        "enabled": cfg.get("enabled", True),
        "interval_minutes": cfg.get("interval_minutes", 15),
        "max_per_rule": cfg.get("max_per_rule", 500),
        "rules": rules,
    }


def validate_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Normalises a config dict, raising ValueError on bad input."""
    if not isinstance(cfg, dict):
        raise ValueError("Config must be an object.")
    cfg = _migrate(copy.deepcopy(cfg))
    try:
        interval = int(cfg.get("interval_minutes", 15))
        max_per_rule = int(cfg.get("max_per_rule", 500))
    except (TypeError, ValueError):
        raise ValueError("interval_minutes and max_per_rule must be numbers.")
    if not 5 <= interval <= 1440:
        raise ValueError("Interval must be between 5 and 1440 minutes.")
    if not 1 <= max_per_rule <= 5000:
        raise ValueError("Max per rule must be between 1 and 5000.")
    rules = []
    for i, r in enumerate(cfg.get("rules") or []):
        if not isinstance(r, dict):
            raise ValueError(f"Rule {i + 1} is invalid.")
        query = str(r.get("query", "")).strip()
        if not query:
            raise ValueError(f"Rule {i + 1} needs a Gmail search query.")
        action = r.get("action", "trash")
        if action not in RULE_ACTIONS:
            raise ValueError(f"Rule {i + 1}: action must be one of {', '.join(RULE_ACTIONS)}.")
        rules.append({
            "name": str(r.get("name") or query)[:80],
            "query": query,
            "action": action,
            "enabled": bool(r.get("enabled", True)),
        })
    return {"enabled": bool(cfg.get("enabled", True)), "interval_minutes": interval,
            "max_per_rule": max_per_rule, "rules": rules}


def load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        try:
            return validate_config(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"[AutoSync] Ignoring unreadable config ({e}); using defaults.")
    return copy.deepcopy(DEFAULT_CONFIG)


def save_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    cfg = validate_config(cfg)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg


def load_history() -> List[Dict[str, Any]]:
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _append_history(entry: Dict[str, Any]) -> None:
    history = load_history()
    history.append(entry)
    HISTORY_PATH.write_text(json.dumps(history[-HISTORY_LIMIT:], indent=2), encoding="utf-8")


def status() -> Dict[str, Any]:
    return dict(_status)


def run_rules(engine, cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Runs every enabled rule once and records the outcome in the history log."""
    if not _run_lock.acquire(blocking=False):
        raise RuntimeError("An auto-clean run is already in progress.")
    _status.update(running=True, startedAt=time.strftime("%Y-%m-%d %H:%M:%S"))
    try:
        cfg = cfg or load_config()
        start = time.time()
        details: Dict[str, int] = {}
        errors: Dict[str, str] = {}
        for rule in cfg["rules"]:
            if not rule["enabled"]:
                continue
            try:
                res = engine.apply_action_to_query(rule["query"], rule["action"], limit=cfg["max_per_rule"])
                details[rule["name"]] = res["count"]
            except Exception as e:
                errors[rule["name"]] = str(e)
        try:
            remaining = engine.get_inbox_stats()["counts"]["inbox"]
        except Exception:
            remaining = None
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "totalCleaned": sum(details.values()),
            "durationSeconds": round(time.time() - start, 1),
            "details": details,
            "errors": errors,
            "inboxMessagesRemaining": remaining,
        }
        _append_history(entry)
        return entry
    finally:
        _status.update(running=False)
        _run_lock.release()
