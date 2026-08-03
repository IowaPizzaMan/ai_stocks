"""POST /logs/frontend and the global unhandled-exception handler.
Spec: specs/SPEC.md 'Exception Handling & Logging'."""
from fastapi.testclient import TestClient

import deps
import main
import routers.logs as logs_router


class RecordingLogger:
    def __init__(self):
        self.calls = []

    def error(self, msg, *args):
        self.calls.append(msg % args if args else msg)

    def exception(self, msg, *args):
        self.calls.append(msg % args if args else msg)


def test_post_logs_frontend_records_and_returns_ok(monkeypatch):
    recorder = RecordingLogger()
    monkeypatch.setattr(logs_router, "logger", recorder)
    monkeypatch.setattr(main, "ensure_indexes", lambda db: None)
    monkeypatch.setattr(main, "get_db", lambda: None)

    with TestClient(main.app) as client:
        resp = client.post(
            "/logs/frontend",
            json={
                "message": "boom",
                "stack": "at x()",
                "component": "ErrorBoundary",
                "url": "http://localhost/feed",
                "timestamp": "2026-08-02T00:00:00Z",
            },
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "logged"}
    assert any("boom" in call for call in recorder.calls)


def test_post_logs_frontend_requires_message(monkeypatch):
    monkeypatch.setattr(main, "ensure_indexes", lambda db: None)
    monkeypatch.setattr(main, "get_db", lambda: None)

    with TestClient(main.app) as client:
        resp = client.post("/logs/frontend", json={})

    assert resp.status_code == 422


def test_unhandled_exception_is_logged_and_returns_generic_500(monkeypatch):
    recorder = RecordingLogger()
    monkeypatch.setattr(main, "logger", recorder)
    monkeypatch.setattr(main, "ensure_indexes", lambda db: None)
    monkeypatch.setattr(main, "get_db", lambda: None)

    def raise_error():
        raise RuntimeError("kaboom")

    main.app.dependency_overrides[deps.db_dependency] = raise_error
    try:
        with TestClient(main.app, raise_server_exceptions=False) as client:
            resp = client.get("/watchlist")
    finally:
        main.app.dependency_overrides.clear()

    assert resp.status_code == 500
    assert resp.json() == {"detail": "internal server error"}
    assert recorder.calls
