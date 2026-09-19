"""``AppSettings``: a thin GObject wrapper over the app's GSettings schema.

Keeps ``Gio.Settings`` details out of the views. Exposes the subset of keys the engine cares
about as an ``engine.Settings`` dataclass (``to_engine()``), plus a ``changed`` signal so widgets
can react to any GSettings key changing without each holding its own ``Gio.Settings`` handle.
"""

from __future__ import annotations

import gi

gi.require_version("Gio", "2.0")
gi.require_version("Gtk", "4.0")

from gi.repository import Gio, GObject, Gtk

from streaks import engine

APPLICATION_ID = "com.cheerschopper.Streaks"


class AppSettings(GObject.Object):
    """Wraps ``Gio.Settings("com.cheerschopper.Streaks")``."""

    __gsignals__ = {
        "changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self):
        """Initialize the settings wrapper and start relaying GSettings changes."""
        super().__init__()
        self._gio = Gio.Settings.new(APPLICATION_ID)
        self._gio.connect("changed", self._on_gio_changed)

    def _on_gio_changed(self, _gio_settings: Gio.Settings, key: str) -> None:
        self.emit("changed", key)

    def to_engine(self) -> engine.Settings:
        """The subset of settings the pure engine needs, as an ``engine.Settings``."""
        return engine.Settings(
            day_start_minutes=self._gio.get_int("day-start-minutes"),
            backfill_days=self._gio.get_int("backfill-days"),
            count_through_unconfirmed=self._gio.get_boolean("count-through-unconfirmed"),
            show_ended=self._gio.get_boolean("show-ended"),
        )

    @property
    def show_ended(self) -> bool:
        return self._gio.get_boolean("show-ended")

    @show_ended.setter
    def show_ended(self, value: bool) -> None:
        self._gio.set_boolean("show-ended", value)

    @property
    def sidebar_selection(self) -> int:
        """The last-selected streak id, or 0 for Today."""
        return self._gio.get_int("sidebar-selection")

    @sidebar_selection.setter
    def sidebar_selection(self, streak_id: int) -> None:
        self._gio.set_int("sidebar-selection", streak_id)

    def bind_window_state(self, window: Gtk.Window) -> None:
        """Bind window geometry to GSettings so it's restored across launches."""
        flags = Gio.SettingsBindFlags.DEFAULT
        self._gio.bind("window-width", window, "default-width", flags)
        self._gio.bind("window-height", window, "default-height", flags)
        self._gio.bind("window-maximized", window, "maximized", flags)
