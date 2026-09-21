"""Preferences dialog (design-spec §7): check-in, run and data settings.

Every row binds straight to a ``Gio.Settings`` key via ``settings.bind()``; "Delete all data"
writes through ``models.delete_all()``. ``AppState`` picks up every GSettings change itself (see
``AppState._on_settings_changed``) and re-notifies its own subscribers.
"""

from __future__ import annotations

import gettext
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gio", "2.0")

from gi.repository import Adw, Gio, GLib, Gtk

from streaks import export, models
from streaks.state import AppState
from streaks.widgets import confirm_dialog

_ = gettext.gettext
ngettext = gettext.ngettext


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/preferences_dialog.ui")
class StreaksPreferencesDialog(Adw.PreferencesDialog):
    """The Preferences dialog (design-spec §7)."""

    __gtype_name__ = "StreaksPreferencesDialog"

    reminders_row = Gtk.Template.Child()
    day_start_row = Gtk.Template.Child()
    day_start_label = Gtk.Template.Child()
    day_start_popover = Gtk.Template.Child()
    day_start_hour_spin = Gtk.Template.Child()
    day_start_minute_spin = Gtk.Template.Child()
    backfill_row = Gtk.Template.Child()
    backfill_label = Gtk.Template.Child()
    count_through_row = Gtk.Template.Child()
    show_ended_row = Gtk.Template.Child()
    export_row = Gtk.Template.Child()
    delete_row = Gtk.Template.Child()

    def __init__(self, state: AppState, **kwargs):
        """Initialize the dialog, binding every row straight to ``state.settings``."""
        super().__init__(**kwargs)
        self.state = state
        self._gio = state.settings.gio
        self.delete_all_dialog: Adw.AlertDialog | None = None

        self.day_start_popover.set_parent(self.day_start_row)

        flags = Gio.SettingsBindFlags.DEFAULT
        self._gio.bind("reminders", self.reminders_row, "active", flags)
        self._gio.bind("backfill-days", self.backfill_row, "value", flags)
        self._gio.bind("count-through-unconfirmed", self.count_through_row, "active", flags)
        self._gio.bind("show-ended", self.show_ended_row, "active", flags)

        self.backfill_row.connect("notify::value", self._on_backfill_changed)
        self._update_backfill_label()

        self._load_day_start()
        self.day_start_row.connect("activated", self._on_day_start_activated)
        self.day_start_hour_spin.connect("value-changed", self._on_day_start_spin_changed)
        self.day_start_minute_spin.connect("value-changed", self._on_day_start_spin_changed)

        self.export_row.connect("activated", self._on_export_activated)
        self.delete_row.connect("activated", self._on_delete_activated)

    # -- backfill window --------------------------------------------------------------

    def _on_backfill_changed(self, *_args) -> None:
        self._update_backfill_label()

    def _update_backfill_label(self) -> None:
        n = int(self.backfill_row.get_value())
        self.backfill_label.set_label(ngettext("%d day", "%d days", n) % n)

    # -- day start ----------------------------------------------------------------------

    def _load_day_start(self) -> None:
        minutes = self._gio.get_int("day-start-minutes")
        self.day_start_hour_spin.set_value(minutes // 60)
        self.day_start_minute_spin.set_value(minutes % 60)
        self._update_day_start_label(minutes)

    def _update_day_start_label(self, minutes: int) -> None:
        self.day_start_label.set_label(f"{minutes // 60:02d}:{minutes % 60:02d}")

    def _on_day_start_activated(self, *_args) -> None:
        self.day_start_popover.popup()

    def _on_day_start_spin_changed(self, *_args) -> None:
        minutes = int(self.day_start_hour_spin.get_value()) * 60 + int(
            self.day_start_minute_spin.get_value()
        )
        self._gio.set_int("day-start-minutes", minutes)
        self._update_day_start_label(minutes)

    # -- export -------------------------------------------------------------------------

    def _on_export_activated(self, *_args) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_initial_name(f"streaks-export-{self.state.today().isoformat()}.json")
        dialog.save(self.get_root(), None, self._on_export_dialog_done)

    def _on_export_dialog_done(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            file = dialog.save_finish(result)
        except GLib.Error:
            return
        if file is None:
            return
        self._export_to(Path(file.get_path()))

    def _export_to(self, path: Path) -> None:
        """Write the whole database to ``path`` as JSON. Split out so tests can call it directly
        without going through the async ``Gtk.FileDialog``."""
        export.dump_json(str(path))

    # -- delete all data ------------------------------------------------------------------

    def _on_delete_activated(self, *_args) -> None:
        self.delete_all_dialog = confirm_dialog(
            self,
            heading=_("Delete all data?"),
            body=_(
                "Every streak, goal and check-in on this machine will be removed. "
                "This cannot be undone."
            ),
            confirm_id="delete",
            confirm_label=_("Delete"),
            destructive=True,
            on_confirm=self._on_delete_response,
        )

    def _on_delete_response(self, _dialog: Adw.AlertDialog, response: str) -> None:
        if response != "delete":
            return
        models.delete_all()
        self.state.reload()
