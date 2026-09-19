"""Main application module."""

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, Gtk

from streaks.resources import load_resources  # noqa: F401  (re-exported for callers)


class StreaksApplication(Adw.Application):
    """Main application class."""

    def __init__(self, **kwargs):
        """Initialize the application."""
        kwargs.setdefault("application_id", "com.cheerschopper.Streaks")
        kwargs.setdefault("flags", Gio.ApplicationFlags.DEFAULT_FLAGS)
        super().__init__(**kwargs)
        self.resource_base_path = "/com/cheerschopper/Streaks"
        self.window = None

        # Create actions
        action = Gio.SimpleAction.new("quit", None)
        action.connect("activate", lambda *_: self.quit())
        self.add_action(action)
        self.set_accels_for_action("app.quit", ["<Ctrl>q"])

        action = Gio.SimpleAction.new("about", None)
        action.connect("activate", self._on_about)
        self.add_action(action)

        # Present-but-no-op for now; a later phase wires up the preferences dialog.
        action = Gio.SimpleAction.new("preferences", None)
        action.connect("activate", self._on_preferences)
        self.add_action(action)
        self.set_accels_for_action("app.preferences", ["<Ctrl>comma"])

    def do_activate(self):
        """Activate the application."""
        if not self.window:
            from streaks.window import StreaksWindow

            self.window = StreaksWindow(application=self)
        self.window.present()

    def _on_preferences(self, *args):
        """Show the preferences dialog (not yet implemented)."""

    def _on_about(self, *args):
        """Show the about dialog."""
        about = Adw.AboutDialog(
            application_name="Streaks",
            version=getattr(self, "_version", "0.1.0"),
            developer_name="Cheers Chopper",
            license_type=Gtk.License.GPL_3_0,
        )
        about.present(self.window)


def main(version):
    """Entry point for the application."""
    load_resources()
    app = StreaksApplication()
    app._version = version
    return app.run(sys.argv)
