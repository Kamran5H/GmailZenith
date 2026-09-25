import pytest

import gmail_engine as ge
from gmail_engine import (
    classify_github, format_size, parse_from, parse_unsubscribe, protect_query, wants_spam_trash,
)


def test_parse_from():
    assert parse_from('"Jane Doe" <Jane@Example.com>') == ("Jane Doe", "jane@example.com")
    assert parse_from("<noreply@x.io>") == ("noreply@x.io", "noreply@x.io")
    assert parse_from("plain@x.io") == ("plain@x.io", "plain@x.io")
    assert parse_from("") == ("Unknown", "")


def test_parse_unsubscribe_prefers_https_and_detects_one_click():
    info = parse_unsubscribe("<mailto:u@list.com?subject=unsub>, <https://list.com/u/123>",
                             "List-Unsubscribe=One-Click")
    assert info == {"url": "https://list.com/u/123", "mailto": "mailto:u@list.com?subject=unsub", "oneClick": True}
    # One-click requires both an https link and the RFC 8058 header.
    assert parse_unsubscribe("<mailto:u@list.com>", "List-Unsubscribe=One-Click")["oneClick"] is False
    assert parse_unsubscribe("<https://a.b/u>", "")["oneClick"] is False
    assert parse_unsubscribe("", "") == {"url": None, "mailto": None, "oneClick": False}


def test_protect_query_and_spam_detection():
    assert protect_query("a OR b") == "(a OR b) -is:starred"
    with pytest.raises(ValueError):
        protect_query("   ")
    assert wants_spam_trash("in:spam older_than:1d")
    assert not wants_spam_trash("category:promotions")


@pytest.mark.parametrize("subject,reason,category,url", [
    ("Re: [octo/app] Fix login (PR #42)", "comment", "pull_requests", "https://github.com/octo/app/pull/42"),
    ("[octo/app] Crash on start (Issue #7)", "", "issues", "https://github.com/octo/app/issues/7"),
    ("[octo/app] Run failed: CI - main (abc123)", "ci_activity", "ci_cd", "https://github.com/octo/app/actions"),
    ("[octo/app] Release v1.2.0 - Spring", "", "releases", "https://github.com/octo/app/releases"),
    ("[octo/app] Dependabot alert: lodash", "security_alert", "security", "https://github.com/octo/app/security"),
    ("[octo/app] Weekly project update", "", "general", "https://github.com/octo/app"),
    # "pr" inside words like "april"/"project" must not be treated as a pull request.
    ("[octo/app] April project planning", "", "general", "https://github.com/octo/app"),
])
def test_classify_github(subject, reason, category, url):
    meta = classify_github(subject, reason)
    assert meta["category"] == category
    assert meta["url"] == url
    assert meta["repo"] == "octo/app"


def test_format_size():
    assert format_size(0) == "0 B"
    assert format_size(2048) == "2.0 KB"
    assert format_size(5 * 1024 * 1024) == "5.0 MB"


class FakeEngine(ge.GmailEngine):
    """GmailEngine with the network replaced by an in-memory mailbox."""

    def __init__(self, mailbox):
        self.mailbox = mailbox  # id -> set(labels)
        self.modified = []

    def _require_auth(self):
        pass

    def list_ids(self, query, cap=ge.DEFAULT_ACTION_CAP):
        # Every message matches the base query; only the scope the engine appends filters.
        scope = query.rsplit(")", 1)[-1]

        def match(labels):
            if "is:unread" in scope and "UNREAD" not in labels:
                return False
            if "in:inbox" in scope and "INBOX" not in labels:
                return False
            if "in:spam" in scope and "SPAM" not in labels:
                return False
            return True
        ids = [i for i, labels in self.mailbox.items() if match(labels)]
        return ids[:cap], len(ids) > cap

    def _fetch_metadata(self, ids, headers=(), fmt="metadata"):
        return [{"id": i, "labelIds": sorted(self.mailbox[i])} for i in ids if i in self.mailbox]

    def _modify(self, ids, action):
        spec = ge.ACTIONS[action]
        for i in ids:
            self.mailbox[i] = (self.mailbox[i] | set(spec["add"])) - set(spec["remove"])
        self.modified.append((action, list(ids)))
        return len(ids)


def snapshot(mb):
    return {k: set(v) for k, v in mb.items()}


def test_trash_by_query_then_undo_restores_exact_labels():
    mailbox = {
        "a": {"INBOX", "UNREAD", "CATEGORY_PROMOTIONS"},
        "b": {"CATEGORY_PROMOTIONS"},            # archived: must NOT come back to the inbox
        "c": {"SPAM"},
    }
    before = snapshot(mailbox)
    eng = FakeEngine(mailbox)
    res = eng.apply_action_to_query("in:spam OR category:promotions", "trash")
    assert res["count"] == 3
    assert all("TRASH" in labels for labels in mailbox.values())
    eng.run_ops(res["undo"])
    assert mailbox == before


def test_archive_and_read_only_touch_affected_messages():
    mailbox = {"a": {"INBOX", "UNREAD"}, "b": {"INBOX"}, "c": set()}
    eng = FakeEngine(mailbox)
    res = eng.apply_action(["a", "b", "c", "missing"], "read")
    assert res["count"] == 1 and res["undo"] == [{"action": "unread", "ids": ["a"]}]
    res = eng.apply_action(["a", "b", "c"], "archive")
    assert res["count"] == 2
    eng.run_ops(res["undo"])
    assert mailbox == {"a": {"INBOX"}, "b": {"INBOX"}, "c": set()}


def test_unknown_action_rejected():
    eng = FakeEngine({})
    with pytest.raises(ValueError):
        eng.apply_action(["x"], "delete")
    with pytest.raises(ValueError):
        eng.run_ops([{"action": "nuke", "ids": ["x"]}])
