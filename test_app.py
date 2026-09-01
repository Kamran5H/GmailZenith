"""
Smoke test for Gmail Zenith Pro backend
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "backend"))

from backend.app import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    print("Health check passed:", data)

def test_auth_status():
    res = client.get("/api/auth/status")
    assert res.status_code == 200
    data = res.json()
    assert "authenticated" in data
    assert "hasCredentials" in data
    print("Auth status passed:", data)

def test_frontend_index():
    res = client.get("/")
    assert res.status_code == 200
    assert "Gmail" in res.text
    print("Frontend index check passed (Length:", len(res.text), ")")

if __name__ == "__main__":
    test_health()
    test_auth_status()
    test_frontend_index()
    print("\nALL SMOKE TESTS PASSED SUCCESSFULLY! [OK]")
