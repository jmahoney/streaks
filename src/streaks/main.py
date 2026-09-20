"""Main application module."""

import gettext
import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from streaks import models
from streaks.resources import load_resources  # noqa: F401  (re-exported for callers)

_ = gettext.gettext


class StreaksApplication(Adw.Application):
    """Main application class."""

    def __init__(self, **kwargs):
        """Initialize the application."""
        kwargs.setdefault("application_id", "com.cheerschopper.Streaks")
        kwargs.setdefault("flags", Gio.ApplicationFlags.DEFAULT_FLAGS)
        super().__init__(**kwargs)
        self.resource_base_path = "/com/cheerschopper/Streaks"
        self.window = None
        self._db_error_dialog: Adw.AlertDialog | None = None

        # Create actions
        action = Gio.SimpleAction.new("quit", None)
        action.connect("activate", lambda *_: self.quit())
        self.add_action(action)
        self.set_accels_for_action("app.quit", ["<Ctrl>q"])

        action = Gio.SimpleAction.new("about", None)
        action.connect("activate", self._on_about)
        self.add_action(action)

        action = Gio.SimpleAction.new("preferences", None)
        action.connect("activate", self._on_preferences)
        self.add_action(action)
        self.set_accels_for_action("app.preferences", ["<Ctrl>comma"])

        self.set_accels_for_action("win.new-streak", ["<Ctrl>n"])
        self.set_accels_for_action("win.toggle-search", ["<Ctrl>f"])
        self.set_accels_for_action("win.show-help-overlay", ["<Ctrl>question"])

    def do_activate(self):
        """Activate the application.

        Opens (creating if needed) the on-disk database before building the window, so a
        corrupt/unwritable database shows a message and quits cleanly instead of crashing with a
        traceback partway through building the UI (design-spec/Phase 8 deliverable 6).
        """
        if not self.window:
            if models.db.database is None:
                try:
                    models.init_db()
                except models.DatabaseInitError as exc:
                    self._show_database_error(exc)
                    return

            from streaks.window import StreaksWindow

            self.window = StreaksWindow(application=self)

            # `scripts/flatpak.sh test`'s headless "does the window actually open" check sets
            # this so the app can prove it and quit on its own, instead of the check having to
            # kill a window that would otherwise sit open until its `timeout` wrapper expires.
            if os.environ.get("STREAKS_QUIT_AFTER_STARTUP"):
                self.window.connect("map", lambda *_args: GLib.idle_add(self.quit))
        self.window.present()

    def _show_database_error(self, exc: models.DatabaseInitError) -> None:
        """Show ``exc``'s path/reason in an ``Adw.AlertDialog`` and quit once dismissed.

        There is no application window to parent this to (opening the database is what building
        one requires), and ``Adw.AlertDialog.present()`` accepts a ``None`` parent for exactly
        this case: it is shown as its own top-level.
        """
        dialog = Adw.AlertDialog(
            heading=_("Can't open the Streaks database"),
            body=_("%(path)s\n\n%(reason)s") % {"path": exc.path, "reason": exc.reason},
        )
        dialog.add_response("quit", _("Quit"))
        dialog.set_default_response("quit")
        dialog.set_close_response("quit")
        dialog.connect("response", lambda *_args: self.quit())
        self._db_error_dialog = dialog
        dialog.present(None)

    def _on_preferences(self, *args):
        """Present the Preferences dialog over the active window."""
        window = self.get_active_window() or self.window
        if window is None:
            return
        from streaks.preferences_dialog import StreaksPreferencesDialog

        dialog = StreaksPreferencesDialog(window.state)
        dialog.present(window)

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
