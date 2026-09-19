"""GUI test configuration."""

import sys
from datetime import date
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

import pytest
from gi.repository import Gio, GLib
from render import configure_for_rendering

from streaks.resources import load_resources

# Templates validate their resource path at class-definition time, so the bundle must be
# registered before any test module imports a view class.
load_resources()

_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

# The fixture's pinned "today" (matches `STREAKS_FAKE_TODAY` and `tests/fixtures/seed.py`).
SEEDED_TODAY = date(2026, 9, 13)

# GSettings keys `seeded_state`/`fresh_state` reset before each test, since the `memory` backend
# keeps its values for the whole test process rather than per-test.
_RESET_KEYS = (
    "sidebar-selection",
    "show-ended",
    "day-start-minutes",
    "backfill-days",
    "count-through-unconfirmed",
)


def _fresh_app_settings():
    from streaks.settings import APPLICATION_ID, AppSettings

    gio_settings = Gio.Settings.new(APPLICATION_ID)
    for key in _RESET_KEYS:
        gio_settings.reset(key)
    return AppSettings()


def _bind_memory_db() -> None:
    from streaks.models import MODELS, db

    if not db.is_closed():
        db.close()
    db.init(":memory:", pragmas={"foreign_keys": 1})
    db.connect()
    db.create_tables(MODELS)


@pytest.fixture
def fresh_state():
    """An `AppState` bound to a fresh, empty in-memory database (no streaks)."""
    import os

    from streaks.state import AppState

    os.environ["STREAKS_FAKE_TODAY"] = SEEDED_TODAY.isoformat()
    _bind_memory_db()
    yield AppState(settings=_fresh_app_settings())


@pytest.fixture
def seeded_state():
    """An `AppState` bound to an in-memory database seeded with the design fixture."""
    import os

    from fixtures.seed import seed
    from streaks.state import AppState

    os.environ["STREAKS_FAKE_TODAY"] = SEEDED_TODAY.isoformat()
    _bind_memory_db()
    seed(SEEDED_TODAY)
    yield AppState(settings=_fresh_app_settings())


def _process_events():
    """Iterate GLib main context while pending."""
    context = GLib.MainContext.default()
    while context.pending():
        context.iteration(False)


@pytest.fixture
def process_events():
    """Fixture for event processing."""
    return _process_events


@pytest.fixture(scope="session")
def app():
    """Create and register the test application."""
    from streaks.main import StreaksApplication

    configure_for_rendering()

    # Create and register the app
    # NON_UNIQUE: never attach to (or block on) a real running Streaks instance on the bus.
    app = StreaksApplication(flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.register()

    return app
