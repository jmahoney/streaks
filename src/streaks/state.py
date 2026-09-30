"""``AppState`` owns the database connection, the app's ``AppSettings``, and ``streaks`` — the
last snapshot loaded from the database. ``reload()`` reloads the snapshot and emits ``changed``;
a settings change emits ``changed`` without a reload, since only derived values change.
"""

from __future__ import annotations

from datetime import date

import gi

gi.require_version("GObject", "2.0")

from gi.repository import GObject

from streaks import clock, models
from streaks.engine import StreakData
from streaks.settings import AppSettings

# Keys whose change re-derives views. sidebar-selection and window-* are written by the views
# themselves.
_ENGINE_SETTINGS_KEYS = frozenset(
    {"day-start-minutes", "backfill-days", "count-through-unconfirmed", "show-ended", "reminders"}
)


class AppState(GObject.Object):
    """Owns the database, the app's settings, and the last-loaded streak snapshot."""

    __gsignals__ = {
        "changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, settings: AppSettings | None = None):
        """Initialize state, opening the production database unless one is already bound."""
        super().__init__()
        self.settings = settings or AppSettings()
        self._settings_changed_id = self.settings.connect("changed", self._on_settings_changed)
        if models.db.database is None:
            models.init_db()
        self.streaks: list[StreakData] = []
        self.reload()

    def close(self) -> None:
        """Disconnect from settings.

        GSettings broadcasts to every connected listener for the life of the process, so an
        ``AppState`` that is no longer owned must unhook itself. ``StreaksWindow`` calls this on
        ``destroy``.
        """
        if self._settings_changed_id is not None:
            self.settings.disconnect(self._settings_changed_id)
            self._settings_changed_id = None

    @property
    def selection(self) -> int:
        """The current sidebar selection (0 = Today), read live from GSettings."""
        return self.settings.sidebar_selection

    @selection.setter
    def selection(self, streak_id: int) -> None:
        self.settings.sidebar_selection = streak_id

    def today(self) -> date:
        """Today's check-in day, honouring the configured day-start and the test clock."""
        return clock.today(self.settings.to_engine().day_start_minutes)

    def reload(self) -> list[StreakData]:
        """Reload every streak from the database and notify subscribers."""
        self.streaks = models.load_all()
        self.emit("changed")
        return self.streaks

    def _on_settings_changed(self, _settings: AppSettings, key: str) -> None:
        if key in _ENGINE_SETTINGS_KEYS:
            self.notify_changed()

    def notify_changed(self) -> None:
        """Re-derive views without reloading.

        Settings only change derived values (run counts, which section a streak sits in), never
        the loaded rows. Data writes call ``reload()`` instead.
        """
        self.emit("changed")
