from fastapi.testclient import TestClient

import main


def test_health(monkeypatch):
    # Skip Mongo index bootstrap — no DB needed for a smoke test
    monkeypatch.setattr(main, "ensure_indexes", lambda db: None)
    monkeypatch.setattr(main, "get_db", lambda: None)
    with TestClient(main.app) as client:
        assert client.get("/health").json() == {"status": "ok"}
