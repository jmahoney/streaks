"""Fixtures shared by the unit test suite: an isolated in-memory database per test.

Tests never touch the user's live/production database (see ``docs/HACKING.md``) — each test gets
a fresh ``:memory:`` SQLite database bound to the Peewee models.
"""

from __future__ import annotations

from datetime import date

import pytest

from fixtures.db import bind_memory_db
from fixtures.seed import FIXTURE_TODAY
from streaks.engine import Settings
from streaks.models import MODELS, db


@pytest.fixture(autouse=True)
def in_memory_db():
    """Swap the production database for an isolated, in-memory database for the test's duration."""
    bind_memory_db()
    yield db
    db.drop_tables(MODELS)
    db.close()
    db.init(None)


@pytest.fixture
def today() -> date:
    """The fixture's pinned "today", matching ``STREAKS_FAKE_TODAY`` and the design fixture."""
    return FIXTURE_TODAY


@pytest.fixture
def settings():
    """Default engine settings."""
    return Settings()


@pytest.fixture
def seeded(today):
    """Seed the design fixture (see ``tests/fixtures/seed.py``) into the in-memory database."""
    from fixtures.seed import seed

    return seed(today)
