"""
Gmail Engine - core Gmail API service for Gmail Zenith.

Handles OAuth2 (with PKCE), exact message counts, batched metadata fetches,
bulk actions (trash / archive / mark read / restore), sender analysis,
one-click unsubscribe and GitHub notification triage.
"""

from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse
import urllib.request

import httplib2
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
]
# Google may return previously granted scopes too; don't treat that as an error.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = BASE_DIR / "credentials.json"
TOKEN_PATH = BASE_DIR / "token.json"

# Gmail's batchModify accepts at most 1000 IDs per call.
GMAIL_BATCH_LIMIT = 1000
# Sub-requests per HTTP batch. Google recommends <= 50 to avoid per-user rate limits.
FETCH_BATCH_SIZE = 50
# Upper bound on how many messages a single bulk action / count will touch.
DEFAULT_ACTION_CAP = 5000
COUNT_CAP = 10000

METADATA_HEADERS = [
    "Subject", "From", "To", "Date",
    "List-Unsubscribe", "List-Unsubscribe-Post", "X-GitHub-Reason",
]

GITHUB_QUERY = "in:inbox from:(notifications@github.com OR noreply@github.com)"

# Label changes applied via batchModify. The first three are user actions;
# the rest exist so every user action can be undone exactly.
ACTIONS: Dict[str, Dict[str, List[str]]] = {
    "trash": {"add": ["TRASH"], "remove": ["INBOX", "SPAM"]},
    "archive": {"add": [], "remove": ["INBOX"]},
    "read": {"add": [], "remove": ["UNREAD"]},
    "unread": {"add": ["UNREAD"], "remove": []},
    "unarchive": {"add": ["INBOX"], "remove": []},
    "untrash": {"add": [], "remove": ["TRASH"]},
    "restore": {"add": ["INBOX"], "remove": ["TRASH"]},
    "respam": {"add": ["SPAM"], "remove": ["TRASH"]},
}
USER_ACTIONS = ("trash", "archive", "read")

# One-click cleaners. Starred mail is always protected (see protect_query).
PRESETS: Dict[str, Dict[str, str]] = {
    "promotions": {
        "title": "Promotions",
        "description": "Marketing emails, deals and store newsletters.",
        "query": "category:promotions",
        "color": "rose",
    },
    "social": {
        "title": "Social",
        "description": "Notifications from social networks and dating/community sites.",
        "query": "category:social",
        "color": "violet",
    },
    "updates": {
        "title": "Old updates",
        "description": "Automated notices, receipts and alerts older than 3 months.",
        "query": "category:updates older_than:3m",
        "color": "blue",
    },
    "forums": {
        "title": "Forums & lists",
        "description": "Mailing lists and discussion groups older than 1 month.",
        "query": "category:forums older_than:1m",
        "color": "cyan",
    },
    "large_files": {
        "title": "Large attachments",
        "description": "Emails over 10 MB — the fastest way to free storage.",
        "query": "larger:10M",
        "color": "emerald",
    },
    "old_clutter": {
        "title": "Clutter over 1 year",
        "description": "Promotions, social and updates older than 12 months.",
        "query": "older_than:1y (category:promotions OR category:social OR category:updates)",
        "color": "amber",
    },
    "spam": {
        "title": "Spam folder",
        "description": "Everything Gmail already flagged as spam.",
        "query": "in:spam",
        "color": "rose",
    },
}


class NotAuthenticated(Exception):
    """Raised when a Gmail call is attempted without a usable token."""


def protect_query(query: str) -> str:
    """Wraps a query so starred mail is never touched by bulk cleanups."""
    query = (query or "").strip()
    if not query:
        raise ValueError("Query must not be empty.")
    return f"({query}) -is:starred"


def wants_spam_trash(query: str) -> bool:
    """Gmail only searches Spam/Trash when explicitly asked to."""
    q = (query or "").lower()
    return any(tok in q for tok in ("in:spam", "is:spam", "in:trash", "is:trash", "label:spam", "label:trash"))


def parse_from(from_str: str) -> Tuple[str, str]:
    """Splits 'John Doe <john@example.com>' into (name, email)."""
    if not from_str:
        return "Unknown", ""
    s = from_str.strip()
    match = re.match(r"^(.*?)\s*<([^>]+)>\s*$", s)
    if match:
        name = match.group(1).strip(" \"'")
        addr = match.group(2).strip().lower()
        return (name or addr), addr
    s = s.strip(" \"'")
    return s, (s.lower() if "@" in s else "")


def parse_unsubscribe(header: str, post_header: str = "") -> Dict[str, Any]:
    """Parses List-Unsubscribe (RFC 2369) and List-Unsubscribe-Post (RFC 8058)."""
    links = re.findall(r"<([^>]+)>", header or "")
    https = next((l.strip() for l in links if l.strip().lower().startswith("https://")), None)
    mailto = next((l.strip() for l in links if l.strip().lower().startswith("mailto:")), None)
    one_click = bool(https) and "list-unsubscribe=one-click" in (post_header or "").lower()
    return {"url": https, "mailto": mailto, "oneClick": one_click}


def classify_github(subject: str, reason: str = "") -> Dict[str, Any]:
    """Classifies a GitHub notification email by X-GitHub-Reason and subject conventions.

    GitHub subjects look like:
      [owner/repo] Title (PR #12)          [owner/repo] Title (Issue #7)
      [owner/repo] Run failed: CI - main   [owner/repo] Release v1.2.0 - Name
    """
    subj = subject or ""
    s = subj.lower()
    reason = (reason or "").lower()

    repo_match = re.search(r"\[([\w.-]+/[\w.-]+)\]", subj)
    repo = repo_match.group(1) if repo_match else None
    pr_match = re.search(r"\(pr #(\d+)\)", s) or re.search(r"pull request #(\d+)", s)
    issue_match = re.search(r"\(issue #(\d+)\)", s)

    if reason == "security_alert" or "dependabot" in s or "security advisor" in s or "vulnerab" in s:
        category, badge = "security", "Security"
    elif reason == "ci_activity" or re.search(r"\brun (failed|cancelled|succeeded)\b|workflow run|\[workflow\]", s):
        category, badge = "ci_cd", "CI / Actions"
    elif pr_match or reason == "review_requested" or "pull request" in s:
        category, badge = "pull_requests", "Pull request"
    elif issue_match:
        category, badge = "issues", "Issue"
    elif re.search(r"\brelease\b|\breleased\b", s):
        category, badge = "releases", "Release"
    else:
        category, badge = "general", "Notification"

    url = "https://github.com/notifications"
    if repo:
        base = f"https://github.com/{repo}"
        if pr_match:
            url = f"{base}/pull/{pr_match.group(1)}"
        elif issue_match:
            url = f"{base}/issues/{issue_match.group(1)}"
        elif category == "ci_cd":
            url = f"{base}/actions"
        elif category == "releases":
            url = f"{base}/releases"
        elif category == "security":
            url = f"{base}/security"
        else:
            url = base

    return {"category": category, "badge": badge, "repo": repo, "url": url, "reason": reason or None}


def format_size(size_bytes: float) -> str:
    size = float(size_bytes or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _is_public_host(host: str) -> bool:
    """Blocks unsubscribe requests aimed at localhost / private networks."""
    try:
        infos = socket.getaddrinfo(host, 443)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


class GmailEngine:
    def __init__(self):
        self.creds: Optional[Credentials] = None
        self.service = None
        self._profile: Optional[Dict[str, Any]] = None
        self._local = threading.local()
        self._lock = threading.RLock()
        self._pending_flows: Dict[str, Flow] = {}
        self.load_credentials()

    # ------------------------------------------------------------------ auth
    def load_credentials(self) -> bool:
        """Loads token.json, refreshing it if the access token has expired."""
        with self._lock:
            self.creds, self.service, self._profile = None, None, None
            if not TOKEN_PATH.exists():
                return False
            try:
                creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
            except Exception as e:
                print(f"[GmailEngine] Could not read token.json: {e}")
                return False
            self.creds = creds
            if not self._ensure_fresh():
                return False
            self.service = build("gmail", "v1", credentials=self.creds, cache_discovery=False)
            return True

    def _save_token(self) -> None:
        TOKEN_PATH.write_text(self.creds.to_json(), encoding="utf-8")

    def _ensure_fresh(self) -> bool:
        """Refreshes an expired access token. Returns False if the token is unusable."""
        creds = self.creds
        if creds is None:
            return False
        if creds.valid:
            return True
        if creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_token()
                return True
            except RefreshError as e:
                print(f"[GmailEngine] Token refresh rejected (revoked or expired): {e}")
            except Exception as e:
                print(f"[GmailEngine] Token refresh failed: {e}")
        self.creds, self.service = None, None
        return False

    def is_authenticated(self) -> bool:
        with self._lock:
            return self.service is not None and self._ensure_fresh()

    def _require_auth(self) -> None:
        if not self.is_authenticated():
            raise NotAuthenticated("Gmail is not connected.")

    def save_credentials_file(self, content: Any) -> None:
        """Validates and stores an OAuth client JSON downloaded from Google Cloud Console."""
        if isinstance(content, (bytes, bytearray)):
            content = content.decode("utf-8")
        parsed = json.loads(content) if isinstance(content, str) else content
        if not isinstance(parsed, dict):
            raise ValueError("Credentials must be a JSON object.")
        client = parsed.get("installed") or parsed.get("web")
        if not client or not client.get("client_id") or not client.get("client_secret"):
            raise ValueError(
                "This is not an OAuth client file. Download the JSON for an OAuth client ID "
                "(type: Desktop app) from Google Cloud Console > APIs & Services > Credentials."
            )
        CREDENTIALS_PATH.write_text(json.dumps(parsed, indent=2), encoding="utf-8")

    def client_type(self) -> Optional[str]:
        try:
            data = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
            return "desktop" if "installed" in data else ("web" if "web" in data else None)
        except Exception:
            return None

    def get_authorization_url(self, redirect_uri: str) -> str:
        """Builds the Google consent URL. The flow is kept so its PKCE verifier survives."""
        if not CREDENTIALS_PATH.exists():
            raise FileNotFoundError("credentials.json not found. Upload it on the Setup tab first.")
        flow = Flow.from_client_secrets_file(str(CREDENTIALS_PATH), scopes=SCOPES, redirect_uri=redirect_uri)
        auth_url, state = flow.authorization_url(access_type="offline", prompt="consent")
        with self._lock:
            # Keep only a handful of in-flight logins.
            if len(self._pending_flows) > 5:
                self._pending_flows.pop(next(iter(self._pending_flows)))
            self._pending_flows[state] = flow
        return auth_url

    def exchange_code_for_token(self, code: str, state: str) -> Dict[str, Any]:
        with self._lock:
            flow = self._pending_flows.pop(state, None)
        if flow is None:
            raise ValueError("Sign-in session expired or was already used. Please start sign-in again.")
        flow.fetch_token(code=code)
        creds = flow.credentials
        if not creds.refresh_token:
            raise ValueError("Google did not return a refresh token. Remove the app's access at "
                             "myaccount.google.com/permissions and sign in again.")
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        self.load_credentials()
        return self.get_profile(force_refresh=True)

    def logout(self) -> None:
        with self._lock:
            if TOKEN_PATH.exists():
                TOKEN_PATH.unlink()
            self.creds, self.service, self._profile = None, None, None

    # ------------------------------------------------------------ transport
    def _http(self) -> AuthorizedHttp:
        """Per-thread authorized HTTP client (httplib2 is not thread-safe)."""
        local = self._local
        if getattr(local, "creds", None) is not self.creds:
            local.http = AuthorizedHttp(self.creds, http=httplib2.Http(timeout=60))
            local.creds = self.creds
        return local.http

    def _exec(self, request) -> Any:
        return request.execute(http=self._http(), num_retries=3)

    @property
    def _messages(self):
        return self.service.users().messages()

    # -------------------------------------------------------------- profile
    def get_profile(self, force_refresh: bool = False) -> Dict[str, Any]:
        self._require_auth()
        if self._profile and not force_refresh:
            return self._profile
        profile = self._exec(self.service.users().getProfile(userId="me"))
        self._profile = {
            "email": profile.get("emailAddress", ""),
            "messagesTotal": int(profile.get("messagesTotal", 0)),
            "threadsTotal": int(profile.get("threadsTotal", 0)),
        }
        return self._profile

    # ------------------------------------------------------------- counting
    def list_ids(self, query: str, cap: int = DEFAULT_ACTION_CAP) -> Tuple[List[str], bool]:
        """Returns up to `cap` message IDs matching `query` and whether more exist."""
        self._require_auth()
        ids: List[str] = []
        token = None
        include = wants_spam_trash(query)
        while len(ids) < cap:
            res = self._exec(self._messages.list(
                userId="me", q=query, maxResults=min(500, cap - len(ids)), pageToken=token,
                includeSpamTrash=include, fields="messages/id,nextPageToken",
            ))
            ids.extend(m["id"] for m in res.get("messages", []))
            token = res.get("nextPageToken")
            if not token:
                return ids, False
        return ids, True

    def count(self, query: str, cap: int = COUNT_CAP) -> Dict[str, Any]:
        """Exact count of matching messages (up to `cap`)."""
        ids, more = self.list_ids(query, cap=cap)
        return {"count": len(ids), "capped": more}

    def _label_counts(self, label_id: str) -> Dict[str, int]:
        lbl = self._exec(self.service.users().labels().get(userId="me", id=label_id))
        return {"total": int(lbl.get("messagesTotal", 0)), "unread": int(lbl.get("messagesUnread", 0))}

    def get_inbox_stats(self) -> Dict[str, Any]:
        """Exact inbox breakdown. Label totals are exact; category splits are counted by paging IDs."""
        self._require_auth()
        inbox = self._label_counts("INBOX")
        spam = self._label_counts("SPAM")
        trash = self._label_counts("TRASH")
        counts: Dict[str, Any] = {
            "inbox": inbox["total"],
            "unread": inbox["unread"],
            "spam": spam["total"],
            "trash": trash["total"],
        }
        capped: List[str] = []
        for key, query in {
            "promotions": "in:inbox category:promotions",
            "social": "in:inbox category:social",
            "updates": "in:inbox category:updates",
            "forums": "in:inbox category:forums",
            "github": GITHUB_QUERY,
            "largeFiles": "larger:5M",
        }.items():
            c = self.count(query)
            counts[key] = c["count"]
            if c["capped"]:
                capped.append(key)
        counts["primary"] = max(0, counts["inbox"] - counts["promotions"] - counts["social"]
                                - counts["updates"] - counts["forums"])
        return {"profile": self.get_profile(), "counts": counts, "capped": capped}

    def preset_counts(self) -> Dict[str, Dict[str, Any]]:
        self._require_auth()
        return {key: self.count(protect_query(p["query"])) for key, p in PRESETS.items()}

    # ------------------------------------------------------------- fetching
    def _fetch_metadata(self, ids: List[str], headers: Iterable[str] = METADATA_HEADERS,
                        fmt: str = "metadata") -> List[Dict[str, Any]]:
        """Fetches message metadata with batched HTTP requests (50 per round trip)."""
        headers = list(headers)
        extra = {"metadataHeaders": headers} if fmt == "metadata" else {}
        results: Dict[str, Dict[str, Any]] = {}
        pending = list(dict.fromkeys(ids))
        for attempt in range(4):
            retry: List[str] = []

            def callback(request_id, response, exception):
                if exception is None:
                    results[request_id] = response
                elif isinstance(exception, HttpError) and exception.resp.status in (429, 500, 503):
                    retry.append(request_id)
                # 404s (message deleted meanwhile) are silently skipped.

            for i in range(0, len(pending), FETCH_BATCH_SIZE):
                batch = self.service.new_batch_http_request(callback=callback)
                for mid in pending[i:i + FETCH_BATCH_SIZE]:
                    batch.add(
                        self._messages.get(userId="me", id=mid, format=fmt, **extra),
                        request_id=mid,
                    )
                batch.execute(http=self._http())
            if not retry:
                break
            pending = retry
            time.sleep(1.5 * (attempt + 1))
        return [results[i] for i in ids if i in results]

    def _to_item(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        headers = {h.get("name", "").lower(): h.get("value", "")
                   for h in msg.get("payload", {}).get("headers", [])}
        name, addr = parse_from(headers.get("from", ""))
        labels = msg.get("labelIds", [])
        email_addr = (self._profile or {}).get("email", "")
        return {
            "id": msg.get("id"),
            "threadId": msg.get("threadId"),
            "subject": headers.get("subject") or "(no subject)",
            "senderName": name,
            "senderEmail": addr,
            "date": headers.get("date", ""),
            "timestamp": int(msg.get("internalDate", 0)),
            "snippet": msg.get("snippet", ""),
            "labelIds": labels,
            "unread": "UNREAD" in labels,
            "starred": "STARRED" in labels,
            "sizeEstimate": msg.get("sizeEstimate", 0),
            "unsubscribe": parse_unsubscribe(headers.get("list-unsubscribe", ""),
                                             headers.get("list-unsubscribe-post", "")),
            "githubReason": headers.get("x-github-reason", ""),
            "gmailUrl": f"https://mail.google.com/mail/?authuser={email_addr}#all/{msg.get('threadId')}",
        }

    def search_messages(self, query: str, max_results: int = 50, page_token: Optional[str] = None) -> Dict[str, Any]:
        self._require_auth()
        self.get_profile()
        res = self._exec(self._messages.list(
            userId="me", q=query, maxResults=max(1, min(max_results, 500)), pageToken=page_token,
            includeSpamTrash=wants_spam_trash(query),
        ))
        ids = [m["id"] for m in res.get("messages", [])]
        return {
            "messages": [self._to_item(m) for m in self._fetch_metadata(ids)],
            "nextPageToken": res.get("nextPageToken"),
            "resultSizeEstimate": res.get("resultSizeEstimate", len(ids)),
        }

    # -------------------------------------------------------------- actions
    def _modify(self, ids: List[str], action: str) -> int:
        spec = ACTIONS[action]
        for i in range(0, len(ids), GMAIL_BATCH_LIMIT):
            self._exec(self._messages.batchModify(
                userId="me",
                body={"ids": ids[i:i + GMAIL_BATCH_LIMIT], "addLabelIds": spec["add"], "removeLabelIds": spec["remove"]},
            ))
        return len(ids)

    @staticmethod
    def _undo_ops(action: str, ids: List[str], inbox: set, spam: set) -> List[Dict[str, Any]]:
        """Label operations that exactly reverse `action` on `ids`."""
        if action == "read":
            ops = [("unread", ids)]
        elif action == "archive":
            ops = [("unarchive", ids)]
        else:  # trash: put each message back where it was
            ops = [("restore", [i for i in ids if i in inbox]),
                   ("respam", [i for i in ids if i in spam and i not in inbox]),
                   ("untrash", [i for i in ids if i not in inbox and i not in spam])]
        return [{"action": a, "ids": x} for a, x in ops if x]

    def run_ops(self, ops: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Applies raw label operations (used by Undo)."""
        self._require_auth()
        total = 0
        for op in ops:
            if op.get("action") not in ACTIONS:
                raise ValueError(f"Unknown action '{op.get('action')}'.")
            total += self._modify(list(dict.fromkeys(i for i in op.get("ids", []) if i)), op["action"])
        return {"success": True, "count": total}

    def apply_action(self, message_ids: List[str], action: str) -> Dict[str, Any]:
        """Trash / archive / mark read specific messages, returning undo operations."""
        self._require_auth()
        if action not in USER_ACTIONS:
            raise ValueError(f"Unknown action '{action}'. Use one of: {', '.join(USER_ACTIONS)}")
        ids = list(dict.fromkeys(i for i in message_ids if i))
        labels = {m["id"]: set(m.get("labelIds", [])) for m in self._fetch_metadata(ids, fmt="minimal")}
        ids = [i for i in ids if i in labels]  # drop IDs that no longer exist
        if action == "read":
            ids = [i for i in ids if "UNREAD" in labels[i]]
        elif action == "archive":
            ids = [i for i in ids if "INBOX" in labels[i]]
        inbox = {i for i in ids if "INBOX" in labels[i]}
        spam = {i for i in ids if "SPAM" in labels[i]}
        count = self._modify(ids, action) if ids else 0
        return {"success": True, "action": action, "count": count,
                "undo": self._undo_ops(action, ids, inbox, spam)}

    def apply_action_to_query(self, query: str, action: str, limit: int = DEFAULT_ACTION_CAP,
                              protect_starred: bool = True) -> Dict[str, Any]:
        """Runs an action on everything matching a query (up to `limit`), returning undo operations."""
        self._require_auth()
        if action not in USER_ACTIONS:
            raise ValueError(f"Unknown action '{action}'. Use one of: {', '.join(USER_ACTIONS)}")
        q = protect_query(query) if protect_starred else query
        # Only touch messages the action actually changes, so undo is exact.
        scoped = {"read": f"({q}) is:unread", "archive": f"({q}) in:inbox"}.get(action, q)
        ids, more = self.list_ids(scoped, cap=limit)
        inbox: set = set()
        spam: set = set()
        if action == "trash" and ids:
            inbox = set(self.list_ids(f"({q}) in:inbox", cap=limit)[0])
            if wants_spam_trash(q):
                spam = set(self.list_ids(f"({q}) in:spam", cap=limit)[0])
        count = self._modify(ids, action) if ids else 0
        return {"success": True, "action": action, "count": count, "query": q, "more": more,
                "undo": self._undo_ops(action, ids, inbox, spam)}

    def preview(self, query: str, protect_starred: bool = True, sample_size: int = 25) -> Dict[str, Any]:
        """Dry run: exact match count, sample messages and an estimated size."""
        q = protect_query(query) if protect_starred else query
        c = self.count(q)
        sample = self.search_messages(q, max_results=sample_size)["messages"] if c["count"] else []
        avg = (sum(m["sizeEstimate"] for m in sample) / len(sample)) if sample else 0
        est = avg * c["count"]
        return {
            "query": q,
            "count": c["count"],
            "capped": c["capped"],
            "estimatedSizeBytes": int(est),
            "estimatedSize": format_size(est),
            "sample": sample[:10],
        }

    # -------------------------------------------------------------- senders
    def get_top_senders(self, scan_limit: int = 300, top: int = 15) -> Dict[str, Any]:
        """Groups the most recent inbox messages by sender."""
        self._require_auth()
        ids, _ = self.list_ids("in:inbox", cap=scan_limit)
        msgs = self._fetch_metadata(ids, headers=["From", "List-Unsubscribe", "List-Unsubscribe-Post"])
        senders: Dict[str, Dict[str, Any]] = {}
        for msg in msgs:
            headers = {h.get("name", "").lower(): h.get("value", "")
                       for h in msg.get("payload", {}).get("headers", [])}
            name, addr = parse_from(headers.get("from", ""))
            key = addr or name
            entry = senders.setdefault(key, {
                "name": name, "email": addr, "count": 0, "unread": 0, "sizeBytes": 0,
                "unsubscribe": {"url": None, "mailto": None, "oneClick": False}, "sampleId": msg.get("id"),
            })
            entry["count"] += 1
            entry["sizeBytes"] += msg.get("sizeEstimate", 0)
            if "UNREAD" in msg.get("labelIds", []):
                entry["unread"] += 1
            unsub = parse_unsubscribe(headers.get("list-unsubscribe", ""), headers.get("list-unsubscribe-post", ""))
            if (unsub["url"] or unsub["mailto"]) and not (entry["unsubscribe"]["url"] or entry["unsubscribe"]["mailto"]):
                entry["unsubscribe"] = unsub
                entry["sampleId"] = msg.get("id")
        ranked = sorted(senders.values(), key=lambda s: (s["count"], s["sizeBytes"]), reverse=True)[:top]
        for s in ranked:
            s["size"] = format_size(s["sizeBytes"])
        return {"scanned": len(msgs), "senders": ranked}

    def unsubscribe(self, message_id: str) -> Dict[str, Any]:
        """Performs an RFC 8058 one-click unsubscribe when the sender supports it;
        otherwise returns the link/mailto for the user to open."""
        self._require_auth()
        msgs = self._fetch_metadata([message_id], headers=["List-Unsubscribe", "List-Unsubscribe-Post"])
        if not msgs:
            raise ValueError("Message not found.")
        headers = {h.get("name", "").lower(): h.get("value", "")
                   for h in msgs[0].get("payload", {}).get("headers", [])}
        info = parse_unsubscribe(headers.get("list-unsubscribe", ""), headers.get("list-unsubscribe-post", ""))
        if info["oneClick"]:
            host = urlparse(info["url"]).hostname or ""
            if not _is_public_host(host):
                raise ValueError("Unsubscribe link points to a private address; refusing to call it.")
            req = urllib.request.Request(
                info["url"], data=b"List-Unsubscribe=One-Click", method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "GmailZenith/2.0"},
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if 200 <= resp.status < 300:
                        return {"success": True, "method": "one-click", "url": info["url"]}
            except Exception as e:
                print(f"[GmailEngine] One-click unsubscribe failed, falling back to link: {e}")
        if info["url"] or info["mailto"]:
            return {"success": False, "method": "link", "url": info["url"], "mailto": info["mailto"]}
        raise ValueError("This sender does not offer an unsubscribe link.")

    # --------------------------------------------------------------- github
    def get_github_triage(self, max_results: int = 100) -> Dict[str, Any]:
        res = self.search_messages(GITHUB_QUERY, max_results=max_results)
        categorized: Dict[str, List[Dict[str, Any]]] = {
            k: [] for k in ("pull_requests", "issues", "ci_cd", "security", "releases", "general")
        }
        for m in res["messages"]:
            m["githubMeta"] = classify_github(m["subject"], m.get("githubReason", ""))
            categorized[m["githubMeta"]["category"]].append(m)
        return {"total": len(res["messages"]), "categorized": categorized, "all": res["messages"],
                "more": bool(res.get("nextPageToken"))}


# Global singleton engine
engine = GmailEngine()
