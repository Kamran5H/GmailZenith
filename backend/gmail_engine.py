"""
Gmail Engine - Core Gmail API Service for Gmail Zenith Pro
Provides OAuth2 authentication, batch message querying, trashing, label modification,
GitHub triage categorization, storage analysis, and safe dry-run preview mode.
"""

from __future__ import annotations

import base64
import email
from email.utils import parsedate_to_datetime
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    pass

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
]

BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = BASE_DIR / "credentials.json"
TOKEN_PATH = BASE_DIR / "token.json"


class GmailEngine:
    def __init__(self):
        self.creds: Optional[Credentials] = None
        self.service = None
        self._user_profile: Optional[Dict[str, Any]] = None
        self.load_credentials()

    def load_credentials(self) -> bool:
        """Loads saved credentials from token.json if present and valid."""
        self.creds = None
        self.service = None
        self._user_profile = None

        if TOKEN_PATH.exists():
            try:
                self.creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
            except Exception as e:
                print(f"[GmailEngine] Error loading token: {e}")
                self.creds = None

        if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                with open(TOKEN_PATH, "w", encoding="utf-8") as f:
                    f.write(self.creds.to_json())
            except Exception as e:
                print(f"[GmailEngine] Token refresh failed: {e}")
                self.creds = None

        if self.creds and self.creds.valid:
            try:
                self.service = build("gmail", "v1", credentials=self.creds, cache_discovery=False)
                return True
            except Exception as e:
                print(f"[GmailEngine] Error building service: {e}")
                self.service = None
                return False
        return False

    def is_authenticated(self) -> bool:
        """Checks if valid authenticated service is ready."""
        return self.service is not None and self.creds is not None and self.creds.valid

    def save_credentials_file(self, content_or_dict: Any) -> bool:
        """Saves uploaded credentials.json file content."""
        try:
            if isinstance(content_or_dict, str):
                parsed = json.loads(content_or_dict)
            elif isinstance(content_or_dict, dict):
                parsed = content_or_dict
            else:
                parsed = json.loads(content_or_dict.decode("utf-8"))

            with open(CREDENTIALS_PATH, "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=2)
            return True
        except Exception as e:
            print(f"[GmailEngine] Failed to save credentials.json: {e}")
            return False

    def get_authorization_url(self, redirect_uri: str = "http://127.0.0.1:8765/oauth2callback") -> str:
        """Generates Google OAuth2 consent URL."""
        if not CREDENTIALS_PATH.exists():
            raise FileNotFoundError("credentials.json not found. Please upload it first.")

        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_PATH),
            scopes=SCOPES,
            redirect_uri=redirect_uri,
        )
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return auth_url

    def exchange_code_for_token(
        self, code: str, redirect_uri: str = "http://127.0.0.1:8765/oauth2callback"
    ) -> Dict[str, Any]:
        """Exchanges auth code for access & refresh tokens."""
        if not CREDENTIALS_PATH.exists():
            return {"success": False, "error": "credentials.json not found."}

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH),
                scopes=SCOPES,
                redirect_uri=redirect_uri,
            )
            flow.fetch_token(code=code)
            creds = flow.credentials

            with open(TOKEN_PATH, "w", encoding="utf-8") as f:
                f.write(creds.to_json())

            self.load_credentials()
            profile = self.get_profile(force_refresh=True)
            return {"success": True, "profile": profile}
        except Exception as e:
            print(f"[GmailEngine] Exchange code error: {e}")
            return {"success": False, "error": str(e)}

    def authenticate_interactive(self) -> Dict[str, Any]:
        """Runs the interactive browser OAuth2 flow."""
        if not CREDENTIALS_PATH.exists():
            return {
                "success": False,
                "error": "credentials.json not found. Please upload or configure your Google Cloud OAuth Client credentials.",
            }

        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(
                port=0,
                prompt="consent",
                authorization_prompt_message="Opening browser for Google Authentication...",
                success_message="Authentication successful! You can return to Gmail Zenith Pro.",
            )
            with open(TOKEN_PATH, "w", encoding="utf-8") as token_file:
                token_file.write(creds.to_json())

            self.load_credentials()
            profile = self.get_profile()
            return {"success": True, "profile": profile}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def logout(self) -> bool:
        """Removes local token and resets service."""
        try:
            if TOKEN_PATH.exists():
                TOKEN_PATH.unlink()
            self.creds = None
            self.service = None
            self._user_profile = None
            return True
        except Exception as e:
            print(f"[GmailEngine] Logout error: {e}")
            return False

    def get_profile(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Fetches profile info (email address, total messages, threads)."""
        if not self.is_authenticated():
            return {
                "authenticated": False,
                "email": None,
                "messagesTotal": 0,
                "threadsTotal": 0,
                "historyId": 0,
            }

        if self._user_profile and not force_refresh:
            return self._user_profile

        try:
            profile = self.service.users().getProfile(userId="me").execute()
            self._user_profile = {
                "authenticated": True,
                "email": profile.get("emailAddress", ""),
                "messagesTotal": int(profile.get("messagesTotal", 0)),
                "threadsTotal": int(profile.get("threadsTotal", 0)),
                "historyId": profile.get("historyId", ""),
            }
            return self._user_profile
        except Exception as e:
            print(f"[GmailEngine] get_profile error: {e}")
            return {"authenticated": False, "error": str(e)}

    def get_inbox_stats(self) -> Dict[str, Any]:
        """Gathers counts and estimates for various categories."""
        if not self.is_authenticated():
            return {"authenticated": False}

        profile = self.get_profile()

        # Queries to check
        categories = {
            "inbox": "in:inbox",
            "unread": "is:unread in:inbox",
            "promotions": "category:promotions",
            "social": "category:social",
            "updates": "category:updates",
            "spam": "is:spam",
            "trash": "is:trash",
            "github": "from:notifications@github.com OR from:github.com",
            "largeFiles": "has:attachment larger:5M",
            "olderThan1Year": "older_than:1y in:inbox",
        }

        counts: Dict[str, int] = {}
        for cat_name, query in categories.items():
            try:
                res = self.service.users().messages().list(
                    userId="me", q=query, maxResults=1, includeSpamTrash=True if cat_name in ("spam", "trash") else False
                ).execute()
                counts[cat_name] = res.get("resultSizeEstimate", 0)
            except Exception:
                counts[cat_name] = 0

        return {
            "authenticated": True,
            "profile": profile,
            "counts": counts,
        }

    def _parse_message_headers(self, msg_payload: Dict[str, Any]) -> Dict[str, str]:
        """Extracts standard email headers (Subject, From, To, Date, Message-ID, etc.)."""
        headers = {}
        if not msg_payload or "headers" not in msg_payload:
            return headers

        for h in msg_payload["headers"]:
            name = h.get("name", "").lower()
            val = h.get("value", "")
            if name in ("subject", "from", "to", "date", "message-id", "list-unsubscribe", "x-github-reason"):
                headers[name] = val
        return headers

    def _clean_from_field(self, from_str: str) -> Tuple[str, str]:
        """Separates display name and email address from 'From: John Doe <john@example.com>'."""
        if not from_str:
            return "Unknown", ""
        match = re.match(r"^(.*?)\s*<([^>]+)>$", from_str.strip())
        if match:
            name = match.group(1).strip(' "\'')
            email_addr = match.group(2).strip()
            return name if name else email_addr, email_addr
        return from_str.strip(' "\''), from_str.strip()

    def search_messages(
        self,
        query: str,
        max_results: int = 50,
        page_token: Optional[str] = None,
        include_spam_trash: bool = False,
    ) -> Dict[str, Any]:
        """Executes a search query and returns parsed message items."""
        if not self.is_authenticated():
            return {"authenticated": False, "messages": [], "nextPageToken": None}

        try:
            list_res = self.service.users().messages().list(
                userId="me",
                q=query,
                maxResults=min(max_results, 200),
                pageToken=page_token,
                includeSpamTrash=include_spam_trash,
            ).execute()

            msg_stubs = list_res.get("messages", [])
            next_page = list_res.get("nextPageToken")
            result_size_estimate = list_res.get("resultSizeEstimate", len(msg_stubs))

            if not msg_stubs:
                return {
                    "authenticated": True,
                    "messages": [],
                    "nextPageToken": None,
                    "resultSizeEstimate": 0,
                }

            detailed_messages = []
            for stub in msg_stubs:
                try:
                    msg = self.service.users().messages().get(
                        userId="me",
                        id=stub["id"],
                        format="metadata",
                        metadataHeaders=["Subject", "From", "To", "Date", "List-Unsubscribe", "X-GitHub-Reason"],
                    ).execute()

                    payload = msg.get("payload", {})
                    headers = self._parse_message_headers(payload)
                    sender_name, sender_email = self._clean_from_field(headers.get("from", ""))

                    item = {
                        "id": msg.get("id"),
                        "threadId": msg.get("threadId"),
                        "subject": headers.get("subject", "(No Subject)"),
                        "senderName": sender_name,
                        "senderEmail": sender_email,
                        "fromRaw": headers.get("from", ""),
                        "to": headers.get("to", ""),
                        "date": headers.get("date", ""),
                        "snippet": msg.get("snippet", ""),
                        "labelIds": msg.get("labelIds", []),
                        "sizeEstimate": msg.get("sizeEstimate", 0),
                        "hasAttachment": any(
                            part.get("filename") for part in payload.get("parts", []) if isinstance(part, dict)
                        ),
                        "unsubscribe": headers.get("list-unsubscribe", ""),
                        "githubReason": headers.get("x-github-reason", ""),
                    }
                    detailed_messages.append(item)
                except Exception as e:
                    print(f"[GmailEngine] Error fetching message {stub.get('id')}: {e}")

            return {
                "authenticated": True,
                "messages": detailed_messages,
                "nextPageToken": next_page,
                "resultSizeEstimate": result_size_estimate,
            }
        except Exception as e:
            print(f"[GmailEngine] search_messages error: {e}")
            return {"authenticated": True, "error": str(e), "messages": []}

    def get_github_triage(self, max_results: int = 50) -> Dict[str, Any]:
        """Specialized triage for GitHub emails, auto-detecting PRs, Issues, Actions, and Security alerts."""
        query = "from:notifications@github.com OR from:github.com"
        raw_res = self.search_messages(query=query, max_results=max_results)
        messages = raw_res.get("messages", [])

        categorized = {
            "pull_requests": [],
            "issues": [],
            "ci_cd": [],
            "security": [],
            "releases": [],
            "general": [],
        }

        for m in messages:
            subj = m["subject"].lower()
            snip = m["snippet"].lower()

            if "[security]" in subj or "dependabot" in subj or "security alert" in snip:
                cat = "security"
                badge = "Dependabot Alert"
                icon = "shield-alert"
            elif "[workflow]" in subj or "run failed" in subj or "workflow run" in subj or "github actions" in snip:
                cat = "ci_cd"
                badge = "CI/CD Action"
                icon = "terminal"
            elif "pull request" in subj or "pull request" in snip or "pr" in subj or "review requested" in snip:
                cat = "pull_requests"
                badge = "Pull Request"
                icon = "git-pull-request"
            elif "issue" in subj or "issue #" in subj or "assigned" in snip or "commented" in snip:
                cat = "issues"
                badge = "Issue"
                icon = "circle-dot"
            elif "release" in subj or "tag" in subj or "published" in snip:
                cat = "releases"
                badge = "Release"
                icon = "tag"
            else:
                cat = "general"
                badge = "GitHub Notification"
                icon = "github"

            repo_match = re.search(r"\[([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)\]", m["subject"])
            repo_name = repo_match.group(1) if repo_match else None
            github_url = f"https://github.com/{repo_name}" if repo_name else "https://github.com/notifications"

            m["githubMeta"] = {
                "category": cat,
                "badge": badge,
                "icon": icon,
                "repo": repo_name,
                "url": github_url,
            }
            categorized[cat].append(m)

        return {
            "authenticated": True,
            "total": len(messages),
            "categorized": categorized,
            "all": messages,
        }

    def get_top_clutter_senders(self, scan_limit: int = 150) -> List[Dict[str, Any]]:
        """Finds who sends the most emails in the inbox."""
        if not self.is_authenticated():
            return []

        try:
            list_res = self.service.users().messages().list(
                userId="me", q="in:inbox", maxResults=min(scan_limit, 200)
            ).execute()

            messages = list_res.get("messages", [])
            sender_counts: Dict[str, Dict[str, Any]] = {}

            for m in messages:
                try:
                    meta = self.service.users().messages().get(
                        userId="me", id=m["id"], format="metadata", metadataHeaders=["From"]
                    ).execute()
                    headers = self._parse_message_headers(meta.get("payload", {}))
                    raw_from = headers.get("from", "Unknown")
                    name, email_addr = self._clean_from_field(raw_from)
                    key = email_addr if email_addr else name

                    if key not in sender_counts:
                        sender_counts[key] = {
                            "name": name,
                            "email": email_addr,
                            "count": 0,
                            "sampleId": m["id"],
                        }
                    sender_counts[key]["count"] += 1
                except Exception:
                    continue

            sorted_senders = sorted(sender_counts.values(), key=lambda x: x["count"], reverse=True)
            return sorted_senders[:12]
        except Exception as e:
            print(f"[GmailEngine] get_top_clutter_senders error: {e}")
            return []

    def simulate_clean(self, query: str, max_scan: int = 100) -> Dict[str, Any]:
        """Dry-run simulation to preview exactly what would be cleaned before executing."""
        if not self.is_authenticated():
            return {"authenticated": False, "matchedCount": 0, "sample": []}

        search_res = self.search_messages(query=query, max_results=max_scan)
        messages = search_res.get("messages", [])
        total_size = sum(m.get("sizeEstimate", 0) for m in messages)

        return {
            "authenticated": True,
            "query": query,
            "matchedCount": search_res.get("resultSizeEstimate", len(messages)),
            "sampleCount": len(messages),
            "estimatedSizeBytes": total_size,
            "estimatedSizeFormatted": self._format_size(total_size),
            "sample": messages[:10],
        }

    def _format_size(self, size_bytes: int) -> str:
        """Formats byte size into KB, MB, or GB."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    # Gmail's batchModify / batchDelete accept at most 1000 message IDs per call.
    GMAIL_BATCH_LIMIT = 1000

    def batch_trash_messages(self, message_ids: List[str]) -> Dict[str, Any]:
        """Safely moves a list of message IDs to the Gmail Trash (recoverable for 30 days).

        Uses a single chunked ``batchModify`` that adds the TRASH label and strips
        INBOX/UNREAD. This is the recoverable-trash equivalent of ``messages.trash``
        but done in one API call per 1000 messages — far faster than per-message
        calls, and thread-safe (the googleapiclient service object is NOT safe to
        share across threads, which the previous ThreadPool version did).
        """
        if not self.is_authenticated():
            return {"authenticated": False, "success": False, "error": "Not authenticated"}

        if not message_ids:
            return {"success": True, "count": 0}

        success_count = 0
        errors: List[Dict[str, str]] = []
        for i in range(0, len(message_ids), self.GMAIL_BATCH_LIMIT):
            chunk = message_ids[i : i + self.GMAIL_BATCH_LIMIT]
            try:
                self.service.users().messages().batchModify(
                    userId="me",
                    body={
                        "ids": chunk,
                        "addLabelIds": ["TRASH"],
                        "removeLabelIds": ["INBOX", "UNREAD"],
                    },
                ).execute()
                success_count += len(chunk)
            except Exception as e:
                errors.append({"chunkStart": str(i), "error": str(e)})

        return {
            "success": len(errors) == 0,
            "count": success_count,
            "errors": errors,
        }

    def batch_untrash_messages(self, message_ids: List[str]) -> Dict[str, Any]:
        """Restores messages from Trash back to Inbox."""
        if not self.is_authenticated():
            return {"authenticated": False, "success": False}

        success_count = 0
        for mid in message_ids:
            try:
                self.service.users().messages().untrash(userId="me", id=mid).execute()
                success_count += 1
            except Exception:
                continue

        return {"success": True, "count": success_count}

    def batch_delete_messages(self, message_ids: List[str]) -> Dict[str, Any]:
        """Permanently deletes messages (irreversible). Chunked to Gmail's 1000-ID limit."""
        if not self.is_authenticated():
            return {"authenticated": False, "success": False}

        if not message_ids:
            return {"success": True, "count": 0}

        deleted = 0
        errors: List[Dict[str, str]] = []
        for i in range(0, len(message_ids), self.GMAIL_BATCH_LIMIT):
            chunk = message_ids[i : i + self.GMAIL_BATCH_LIMIT]
            try:
                self.service.users().messages().batchDelete(
                    userId="me", body={"ids": chunk}
                ).execute()
                deleted += len(chunk)
            except Exception as e:
                errors.append({"chunkStart": str(i), "error": str(e)})

        return {"success": len(errors) == 0, "count": deleted, "errors": errors}

    def batch_modify_labels(
        self,
        message_ids: List[str],
        add_labels: Optional[List[str]] = None,
        remove_labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Adds or removes labels (e.g., mark as read by removing 'UNREAD', archive by removing 'INBOX')."""
        if not self.is_authenticated():
            return {"authenticated": False, "success": False}

        if not message_ids:
            return {"success": True, "count": 0}

        modified = 0
        errors: List[Dict[str, str]] = []
        for i in range(0, len(message_ids), self.GMAIL_BATCH_LIMIT):
            chunk = message_ids[i : i + self.GMAIL_BATCH_LIMIT]
            try:
                self.service.users().messages().batchModify(
                    userId="me",
                    body={
                        "ids": chunk,
                        "addLabelIds": add_labels or [],
                        "removeLabelIds": remove_labels or [],
                    },
                ).execute()
                modified += len(chunk)
            except Exception as e:
                errors.append({"chunkStart": str(i), "error": str(e)})

        return {"success": len(errors) == 0, "count": modified, "errors": errors}

    def clean_by_preset(self, preset_name: str, max_items: int = 100) -> Dict[str, Any]:
        """Executes a 1-click clean for a given preset category."""
        preset_queries = {
            "promotions": "category:promotions",
            "social": "category:social",
            "updates": "category:updates",
            "spam": "is:spam",
            "older_than_6m": "older_than:6m (category:promotions OR category:social OR category:updates)",
            "older_than_1y": "older_than:1y (category:promotions OR category:social)",
            "large_files": "has:attachment larger:10M",
        }

        query = preset_queries.get(preset_name)
        if not query:
            return {"success": False, "error": f"Unknown preset: {preset_name}"}

        search_res = self.search_messages(query=query, max_results=max_items)
        messages = search_res.get("messages", [])
        if not messages:
            return {"success": True, "count": 0, "message": "No matching emails found to clean."}

        ids_to_trash = [m["id"] for m in messages]
        result = self.batch_trash_messages(ids_to_trash)
        result["preset"] = preset_name
        result["query"] = query
        return result


# Global singleton engine
engine = GmailEngine()
