"""``AppState``: the single owner of the database connection and the in-memory snapshot of it.

Views never talk to ``models``/``engine`` directly for anything but read-only formatting —
they read ``AppState.streaks``/``AppState.today()`` and subscribe to ``changed`` to know when to
rebuild themselves. Every write helper this class grows in later phases (create/check-in/answer/
end/delete/reorder) is expected to call ``reload()`` when it's done, which is what fires
``changed``.
"""

from __future__ import annotations

from datetime import date

import gi

gi.require_version("GObject", "2.0")

from gi.repository import GObject

from streaks import clock, models
from streaks.engine import StreakData
from streaks.settings import AppSettings


class AppState(GObject.Object):
    """Owns the database, the app's settings, and the last-loaded streak snapshot."""

    __gsignals__ = {
        "changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, settings: AppSettings | None = None):
        """Initialize state, opening the production database unless one is already bound."""
        super().__init__()
        self.settings = settings or AppSettings()
        if models.db.database is None:
            models.init_db()
        self.streaks: list[StreakData] = []
        self.reload()

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
        self.streaks = models.load_all(self.today())
        self.emit("changed")
        return self.streaks

    def set_selection(self, streak_id: int) -> None:
        """Record the sidebar selection (0 = Today), persisting it to GSettings."""
        self.selection = streak_id
