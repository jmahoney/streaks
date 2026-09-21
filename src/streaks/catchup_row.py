"""One unconfirmed day inside the catch-up dialog (design-spec §5).

The row reports its own raw toggle state (kept/missed/unanswered, and which goals are ticked)
via ``current_answer()`` and ``answer-changed``. The owning ``StreaksCatchupDialog`` feeds this
through ``engine.catch_up_preview`` and pushes the resulting strings back onto the row with
``set_state_text()``/``set_warning()``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GObject, Gtk

from streaks import words
from streaks.engine import Answer, GoalData


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/catchup_row.ui")
class StreaksCatchupRow(Gtk.ListBoxRow):
    """One unconfirmed day: a date, a Kept/Missed toggle pair, and (when Missed) a goal list."""

    __gtype_name__ = "StreaksCatchupRow"

    __gsignals__ = {
        "answer-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    date_label = Gtk.Template.Child()
    state_label = Gtk.Template.Child()
    kept_button = Gtk.Template.Child()
    missed_button = Gtk.Template.Child()
    goals_revealer = Gtk.Template.Child()
    goals_list = Gtk.Template.Child()
    warning_label = Gtk.Template.Child()

    def __init__(self, **kwargs):
        """Initialize the row. Call ``configure()`` before it renders anything useful."""
        super().__init__(**kwargs)
        self.day: date | None = None
        self._goal_checks: list[tuple[int, Gtk.CheckButton]] = []
        self._configuring = False

        self.kept_button.connect("toggled", self._on_kept_toggled)
        self.missed_button.connect("toggled", self._on_missed_toggled)

    # -- configuration -------------------------------------------------------------

    def configure(self, day: date, goals: Sequence[GoalData]) -> None:
        """Populate the row for ``day``, with one ticked checkbox per active goal."""
        self.day = day
        self.date_label.set_label(words.fmt_weekday_day(day))

        self.goals_list.remove_all()
        self._goal_checks.clear()
        for goal in goals:
            check = Gtk.CheckButton(label=goal.name, active=True)
            check.connect("toggled", self._on_goal_toggled)
            self.goals_list.append(check)
            self._goal_checks.append((goal.id, check))

        self._update_visual()

    # -- reading state ---------------------------------------------------------------

    def current_answer(self) -> tuple[Answer, tuple[int, ...]] | None:
        """This row's answer as ``(status, missed_goal_ids)``, or ``None`` if unanswered."""
        if self.kept_button.get_active():
            return (Answer.KEPT, ())
        if self.missed_button.get_active():
            missed_ids = tuple(gid for gid, check in self._goal_checks if not check.get_active())
            return (Answer.MISSED, missed_ids)
        return None

    # -- writing back the computed preview ---------------------------------------------

    def set_state_text(self, text: str) -> None:
        """Set the caption under the date, as computed by ``engine.catch_up_preview``."""
        self.state_label.set_label(text)

    def set_warning(self, text: str | None) -> None:
        """Show ``text`` under the goal list, or hide the warning entirely if ``None``."""
        self.warning_label.set_visible(text is not None)
        self.warning_label.set_label(text or "")

    # -- interactions ---------------------------------------------------------------

    def _on_kept_toggled(self, button: Gtk.ToggleButton) -> None:
        if self._configuring:
            return
        self._configuring = True
        if button.get_active():
            self.missed_button.set_active(False)
        self._configuring = False
        self._update_visual()
        self.emit("answer-changed")

    def _on_missed_toggled(self, button: Gtk.ToggleButton) -> None:
        if self._configuring:
            return
        self._configuring = True
        if button.get_active():
            self.kept_button.set_active(False)
        self._configuring = False
        self._update_visual()
        self.emit("answer-changed")

    def _on_goal_toggled(self, _check: Gtk.CheckButton) -> None:
        if self._configuring:
            return
        self.emit("answer-changed")

    def _update_visual(self) -> None:
        is_missed = self.missed_button.get_active()
        is_kept = self.kept_button.get_active()

        if is_missed:
            self.add_css_class("missed")
        else:
            self.remove_css_class("missed")

        if is_kept:
            self.kept_button.add_css_class("suggested-action")
        else:
            self.kept_button.remove_css_class("suggested-action")

        if is_missed:
            self.missed_button.add_css_class("destructive-action")
        else:
            self.missed_button.remove_css_class("destructive-action")

        self.goals_revealer.set_reveal_child(is_missed)
        if not is_missed:
            self.warning_label.set_visible(False)
