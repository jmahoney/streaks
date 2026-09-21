"""GUI test configuration.

Test isolation: the suite runs with `GSETTINGS_BACKEND=memory`, which holds every key's value
for the life of the whole test process. Window geometry and the sidebar selection written by one
test are therefore visible to the next test too, unless something resets them: the
`fresh_state`/`seeded_state` fixtures reset the keys that matter before each test runs, and any
test that maps a real window destroys it afterwards, or builds its own window and dialog,
keeping a window's negotiated geometry out of the tests that follow.
"""

import os

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

import pytest
from gi.repository import Gio
from render import configure_for_rendering, make_test_application
from render import process_events as _process_events

from fixtures.db import bind_memory_db
from fixtures.seed import FIXTURE_TODAY, seed
from streaks.resources import load_resources

# Templates validate their resource path at class-definition time, so the bundle must be
# registered before any test module imports a view class.
load_resources()

from streaks.window import StreaksWindow  # noqa: E402

# Keys `seeded_state`/`fresh_state` reset before each test; see the module docstring.
_RESET_KEYS = (
    "sidebar-selection",
    "show-ended",
    "day-start-minutes",
    "backfill-days",
    "count-through-unconfirmed",
    "window-width",
    "window-height",
    "window-maximized",
)


def _fresh_app_settings():
    from streaks.settings import APPLICATION_ID, AppSettings

    gio_settings = Gio.Settings.new(APPLICATION_ID)
    for key in _RESET_KEYS:
        gio_settings.reset(key)
    return AppSettings()


@pytest.fixture
def fresh_state():
    """An `AppState` bound to a fresh, empty in-memory database (no streaks)."""
    from streaks.state import AppState

    os.environ["STREAKS_FAKE_TODAY"] = FIXTURE_TODAY.isoformat()
    bind_memory_db()
    yield AppState(settings=_fresh_app_settings())


@pytest.fixture
def seeded_state():
    """An `AppState` bound to an in-memory database seeded with the design fixture."""
    from streaks.state import AppState

    os.environ["STREAKS_FAKE_TODAY"] = FIXTURE_TODAY.isoformat()
    bind_memory_db()
    seed(FIXTURE_TODAY)
    yield AppState(settings=_fresh_app_settings())


@pytest.fixture
def process_events():
    """Fixture for event processing."""
    return _process_events


@pytest.fixture(scope="session")
def app():
    """Create and register the test application."""
    configure_for_rendering()
    return make_test_application()


@pytest.fixture
def seeded_window(app, seeded_state):
    """A `StreaksWindow` presented for `seeded_state`, destroyed after the test."""
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    _process_events()
    yield window
    window.destroy()
    _process_events()


@pytest.fixture
def fresh_window(app, fresh_state):
    """A `StreaksWindow` presented for `fresh_state`, destroyed after the test."""
    window = StreaksWindow(application=app, state=fresh_state)
    window.present()
    _process_events()
    yield window
    window.destroy()
    _process_events()
