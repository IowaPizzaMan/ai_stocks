import mongomock
import pytest
from fastapi.testclient import TestClient

import deps
import main


@pytest.fixture
def db():
    return mongomock.MongoClient()["stockai_test"]


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(main, "ensure_indexes", lambda d: None)
    monkeypatch.setattr(main, "get_db", lambda: db)
    main.app.dependency_overrides[deps.db_dependency] = lambda: db
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()
