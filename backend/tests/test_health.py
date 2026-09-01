from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["advisory_only"] is True


def test_health_reports_dataset_configured_flag():
    r = client.get("/api/health")
    body = r.json()
    assert "dataset_configured" in body
    assert "dataset_dir" in body
    assert isinstance(body["dataset_configured"], bool)


def test_root_and_shortcut_health():
    r = client.get("/")
    assert r.status_code == 200
    r2 = client.get("/api/health")
    assert r2.status_code == 200
