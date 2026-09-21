"""Shared in-memory database setup for the unit and GUI test suites."""

from __future__ import annotations

from streaks.models import MODELS, db


def bind_memory_db() -> None:
    """Bind `streaks.models.db` to a fresh, empty in-memory SQLite database."""
    if not db.is_closed():
        db.close()
    db.init(":memory:", pragmas={"foreign_keys": 1})
    db.connect()
    db.create_tables(MODELS)
