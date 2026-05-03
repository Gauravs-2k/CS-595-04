"""Shared test fixtures."""

import os
import sqlite3
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import JSON, String, create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config import get_settings
from db.database import Base, get_db
from main import app

# Register UUID adapter for SQLite
sqlite3.register_adapter(uuid.UUID, lambda u: str(u))
sqlite3.register_converter("UUID", lambda b: uuid.UUID(b.decode()))


@pytest.fixture(autouse=True)
def force_mock_mode():
    """Force Abstractive Health mock mode for all tests."""
    os.environ["OPENROUTER_API_KEY"] = ""
    os.environ["OPENAI_API_KEY"] = ""
    get_settings.cache_clear()
    with patch("services.abstractive._use_mock", return_value=True):
        yield
    get_settings.cache_clear()


@pytest.fixture()
def test_db():
    """Create an in-memory SQLite database for testing.

    Maps PostgreSQL-specific types (JSONB, UUID) to SQLite-compatible types.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    from sqlalchemy.dialects.postgresql import JSONB, UUID

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
            elif isinstance(col.type, UUID):
                col.type = String(36)

    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
