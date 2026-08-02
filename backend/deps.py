"""FastAPI dependencies. Tests override db_dependency with mongomock."""
from db import get_db


def db_dependency():
    return get_db()
