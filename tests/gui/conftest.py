"""GUI test configuration."""

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
