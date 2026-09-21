"""GResource and CSS loading, kept separate from any template class so it can run first."""

import gettext
import os

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, Gio, Gtk

_loaded = False


def load_resources() -> None:
    """Register the gresource bundle and application CSS (idempotent)."""
    global _loaded
    if _loaded:
        return
    resource_path = os.environ.get(
        "STREAKS_GRESOURCE",
        os.path.join(os.path.dirname(__file__), "streaks.gresource"),
    )

    if not os.path.exists(resource_path):
        raise RuntimeError(f"gresource not found at {resource_path} — run: meson compile -C _build")

    resource = Gio.Resource.load(resource_path)
    resource._register()

    css_provider = Gtk.CssProvider()
    css_provider.load_from_resource("/com/cheerschopper/Streaks/style.css")
    display = Gdk.Display.get_default()
    Gtk.StyleContext.add_provider_for_display(
        display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    # Install _() into builtins so modules work without the launcher's gettext setup.
    gettext.install("streaks")

    _loaded = True
