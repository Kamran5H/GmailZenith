import pytest
from fastapi.testclient import TestClient

import app as app_module
import auto_sync
from gmail_engine import NotAuthenticated

client = TestClient(app_module.app)


def test_health_and_index():
    assert client.get("/api/health").json()["status"] == "ok"
    res = client.get("/")
    assert res.status_code == 200 and "Gmail Zenith" in res.text
    assert client.get("/static/app.js").status_code == 200


def test_auth_status_reports_redirect_uri():
    data = client.get("/api/auth/status").json()
    assert data["redirectUri"] == "http://testserver/oauth2callback"
    assert {"authenticated", "hasCredentials", "clientType"} <= data.keys()


def test_unauthenticated_calls_return_401(monkeypatch):
    def boom(*a, **k):
        raise NotAuthenticated("Gmail is not connected.")
    monkeypatch.setattr(app_module.engine, "get_inbox_stats", boom)
    res = client.get("/api/stats/inbox")
    assert res.status_code == 401


def test_cross_origin_post_is_blocked():
    res = client.post("/api/auth/logout", headers={"Origin": "https://evil.example"})
    assert res.status_code == 403


def test_same_origin_action_passes(monkeypatch):
    calls = {}

    def fake(query, action, limit, protect_starred):
        calls.update(query=query, action=action, limit=limit, protect=protect_starred)
        return {"success": True, "count": 2, "undo": []}

    monkeypatch.setattr(app_module.engine, "apply_action_to_query", fake)
    res = client.post("/api/actions/query", json={"query": "category:social", "action": "archive"},
                      headers={"Origin": "http://testserver"})
    assert res.status_code == 200 and res.json()["count"] == 2
    assert calls == {"query": "category:social", "action": "archive", "limit": 5000, "protect": True}


def test_invalid_credentials_upload_rejected():
    res = client.post("/api/auth/upload-credentials",
                      files={"file": ("credentials.json", b'{"foo": 1}', "application/json")})
    assert res.status_code == 400
    assert "OAuth client" in res.json()["detail"]


def test_oauth_callback_escapes_error():
    res = client.get("/oauth2callback", params={"error": "<script>alert(1)</script>"})
    assert res.status_code == 400
    assert "<script>alert(1)</script>" not in res.text


def test_oauth_callback_rejects_unknown_state():
    res = client.get("/oauth2callback", params={"code": "abc", "state": "nope"})
    assert res.status_code == 400
    assert "expired" in res.text


def test_sync_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(auto_sync, "CONFIG_PATH", tmp_path / "cfg.json")
    cfg = client.get("/api/sync/config").json()
    assert cfg["rules"]
    cfg["interval_minutes"] = 30
    cfg["rules"] = [{"name": "News", "query": "from:news@x.com", "action": "archive", "enabled": True}]
    res = client.post("/api/sync/config", json=cfg)
    assert res.status_code == 200
    assert client.get("/api/sync/config").json()["rules"][0]["action"] == "archive"
    bad = client.post("/api/sync/config", json={"interval_minutes": 1, "rules": []})
    assert bad.status_code == 400


def test_presets_listed_without_counts():
    presets = client.get("/api/presets").json()["presets"]
    keys = {p["key"] for p in presets}
    assert {"promotions", "social", "spam", "large_files"} <= keys
