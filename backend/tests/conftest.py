"""Shared pytest fixtures.

Each test gets a fresh in-memory SQLite database and a TestClient that uses it.
"""

import os
import tempfile
from collections.abc import Iterator

# Force test settings BEFORE importing the app.
_test_dir = tempfile.mkdtemp(prefix="karkov-test-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_test_dir}/test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-at-least-32-chars-long!!")
os.environ.setdefault("UPLOADS_DIR", f"{_test_dir}/uploads")
os.environ.setdefault("ADMIN_EMAIL", "admin@karkov.example.com")
os.environ.setdefault("ADMIN_PASSWORD", "admin-test-password")
# Coalesce-then-flush window: zero in tests so existing per-action assertions
# still see chat messages immediately. Tests that exercise coalescing override
# the setting explicitly and call `flush_*` to control timing.
os.environ.setdefault("NOTIFICATION_DEBOUNCE_SECONDS", "0")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import Base, get_db  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def settings():
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def db_engine(tmp_path):
    url = f"sqlite:///{tmp_path}/test.db"
    eng = create_engine(url, future=True, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(db_engine) -> Iterator:
    SessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_engine) -> Iterator[TestClient]:
    SessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)

    def _override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db

    # Run lifespan-equivalent seeding against the test engine.
    from app.seeds import seed_initial_data  # noqa: WPS433

    # Patch the SessionLocal used by seed_initial_data temporarily.
    import app.seeds as seeds_mod  # noqa: WPS433
    import app.core.db as db_mod  # noqa: WPS433
    import app.api.v1.chat as chat_mod  # noqa: WPS433

    original_sessionlocal = None
    if hasattr(seeds_mod, "SessionLocal"):
        original_sessionlocal = seeds_mod.SessionLocal
        seeds_mod.SessionLocal = SessionLocal  # type: ignore[assignment]
    original_db_sessionlocal = db_mod.SessionLocal
    db_mod.SessionLocal = SessionLocal  # type: ignore[assignment]
    original_chat_sessionlocal = chat_mod.SessionLocal
    chat_mod.SessionLocal = SessionLocal  # type: ignore[assignment]
    try:
        seed_initial_data()
        with TestClient(app) as c:
            yield c
    finally:
        if original_sessionlocal is not None:
            seeds_mod.SessionLocal = original_sessionlocal  # type: ignore[assignment]
        db_mod.SessionLocal = original_db_sessionlocal  # type: ignore[assignment]
        chat_mod.SessionLocal = original_chat_sessionlocal  # type: ignore[assignment]
        app.dependency_overrides.clear()
