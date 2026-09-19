"""GUI test configuration."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

import pytest
from gi.repository import Adw, GLib, Gtk

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

    # Set up style manager for testing
    style_manager = Adw.StyleManager.get_default()
    style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)

    # Set up font for testing
    settings = Gtk.Settings.get_default()
    settings.set_property("gtk-font-name", "Cantarell 11")
    settings.set_property("gtk-enable-animations", False)

    # Create and register the app
    app = StreaksApplication()
    app.register()

    return app
