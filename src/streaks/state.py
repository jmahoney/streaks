"""``AppState`` owns the database connection, the app's ``AppSettings``, and ``streaks`` — the
last snapshot loaded from the database. Views read ``streaks``/``today()`` and subscribe to
``changed`` to know when to rebuild. Whoever writes to the database (views call ``models.*``
directly) calls ``reload()`` afterwards, which reloads the snapshot and emits ``changed``.
Settings changes emit ``changed`` without a reload, since only derived values change.
"""

from __future__ import annotations

from datetime import date

import gi

gi.require_version("GObject", "2.0")

from gi.repository import GObject

from streaks import clock, models
from streaks.engine import StreakData
from streaks.settings import AppSettings

# GSettings keys that feed the pure-engine calculations (`AppSettings.to_engine()`/
# `show_ended`) — the only keys whose change should trigger a re-derive-and-notify. Excludes
# `sidebar-selection` and `window-*`: those are *written* by the very act of rebuilding the
# sidebar/resizing the window, so forwarding them here would close a feedback loop (rebuild
# writes the selection -> "changed" -> notify -> rebuild -> writes the selection -> ...).
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
        """Disconnect from ``self.settings``'s ``changed`` signal.

        GSettings (including the ``memory`` backend the test suite uses) broadcasts every write
        to *every* still-connected listener for the whole process — not just the one that made
        the write — so an ``AppState`` that never disconnects stays on that broadcast list, doing
        real work (re-deriving views) on every future settings change for the rest of the
        process, even once whatever owned it is otherwise done with it. Whoever owns an
        ``AppState``'s lifetime calls this once they're done with it (``StreaksWindow`` does so
        on its own ``destroy``).
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

    def set_selection(self, streak_id: int) -> None:
        """Record the sidebar selection (0 = Today), persisting it to GSettings."""
        self.selection = streak_id

    def _on_settings_changed(self, _settings: AppSettings, key: str) -> None:
        if key in _ENGINE_SETTINGS_KEYS:
            self.notify_changed()

    def notify_changed(self) -> None:
        """Tell subscribers to re-derive their views, without touching the database.

        Called whenever a GSettings key changes: day-start, backfill window, show-ended and
        count-through-unconfirmed all feed into *derived* values (sidebar counts, run state,
        which section a streak sits in) that every subscriber already recomputes fresh from
        ``self.streaks`` and ``self.settings.to_engine()`` each time it handles ``changed`` — the
        already-loaded streak data itself is untouched by a settings change, so there is nothing
        to re-query. Deliberately not ``reload()``: this fires on every GSettings write, and a
        real per-write database round trip piles up across a long-running app (or a test run
        that constructs many ``AppState``s, each still listening on the same GSettings backend).
        An actual data write (create/edit/delete a streak, answer a day, "Delete all data") calls
        ``reload()`` directly instead, since there ``self.streaks`` itself is stale.
        """
        self.emit("changed")
