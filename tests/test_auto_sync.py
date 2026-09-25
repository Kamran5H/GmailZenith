import pytest

import auto_sync


def test_migrates_v1_config():
    v1 = {
        "enabled": True, "interval_minutes": 30,
        "purge_promotions": True, "purge_social": False, "purge_spam": True,
        "custom_rules": [{"name": "Quora", "query": "quora in:inbox", "enabled": True}],
    }
    cfg = auto_sync.validate_config(v1)
    names = {r["name"]: r for r in cfg["rules"]}
    assert cfg["interval_minutes"] == 30
    assert names["Social in inbox"]["enabled"] is False
    assert names["Quora"]["query"] == "quora in:inbox"
    assert all(r["action"] == "trash" for r in cfg["rules"])


@pytest.mark.parametrize("bad", [
    {"interval_minutes": 1, "rules": []},
    {"max_per_rule": 0, "rules": []},
    {"rules": [{"name": "x", "query": ""}]},
    {"rules": [{"name": "x", "query": "a", "action": "delete"}]},
])
def test_rejects_bad_config(bad):
    with pytest.raises(ValueError):
        auto_sync.validate_config(bad)


def test_run_rules_records_history(tmp_path, monkeypatch):
    monkeypatch.setattr(auto_sync, "HISTORY_PATH", tmp_path / "log.json")

    class Eng:
        def apply_action_to_query(self, query, action, limit):
            if "boom" in query:
                raise RuntimeError("quota")
            return {"count": 3}

        def get_inbox_stats(self):
            return {"counts": {"inbox": 42}}

    cfg = auto_sync.validate_config({"rules": [
        {"name": "ok", "query": "a"}, {"name": "bad", "query": "boom"}, {"name": "off", "query": "b", "enabled": False},
    ]})
    entry = auto_sync.run_rules(Eng(), cfg)
    assert entry["totalCleaned"] == 3
    assert entry["details"] == {"ok": 3}
    assert entry["errors"] == {"bad": "quota"}
    assert entry["inboxMessagesRemaining"] == 42
    assert auto_sync.load_history()[-1]["totalCleaned"] == 3
    assert auto_sync.status()["running"] is False
