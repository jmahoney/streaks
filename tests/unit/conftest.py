"""Fixtures shared by the unit test suite: an isolated in-memory database per test.

Per ``CLAUDE.md``, tests never touch the user's live/production database — each test gets a
fresh ``:memory:`` SQLite database bound to the Peewee models.
"""

from __future__ import annotations

from datetime import date

import pytest

from streaks.engine import Settings
from streaks.models import MODELS, db


@pytest.fixture(autouse=True)
def in_memory_db():
    """Swap the production database for an isolated, in-memory database for the test's duration."""
    db.init(":memory:", pragmas={"foreign_keys": 1})
    db.connect()
    db.create_tables(MODELS)
    yield db
    db.drop_tables(MODELS)
    db.close()
    db.init(None)


@pytest.fixture
def today() -> date:
    """The fixture's pinned "today", matching ``STREAKS_FAKE_TODAY`` and the design fixture."""
    return date(2026, 9, 13)


@pytest.fixture
def settings():
    """Default engine settings."""
    return Settings()


@pytest.fixture
def seeded(today):
    """Seed the design fixture (see ``tests/fixtures/seed.py``) into the in-memory database."""
    from fixtures.seed import seed

    return seed(today)
