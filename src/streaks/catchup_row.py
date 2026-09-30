"""One unconfirmed day inside the catch-up dialog.

The row is its own card: a date, a status caption, and one tick box per active goal. The user
ticks the goals they completed; the row derives its own answer from those ticks (all ticked is
kept, some ticked is partial/missed, none ticked is either unconfirmed or explicitly missed via
the header's "Mark missed"/"Undo" link). It reports that raw state via ``current_answer()`` and
``answer-changed``.
"""

from __future__ import annotations

import gettext
from collections.abc import Sequence
from datetime import date

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GObject, Gtk

from streaks import words
from streaks.catchup_goal_row import (
    StreaksCatchupGoalRow,  # noqa: F401  registers $StreaksCatchupGoalRow
)
from streaks.engine import Answer, GoalData

_ = gettext.gettext


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/catchup_row.ui")
class StreaksCatchupRow(Gtk.Box):
    """One unconfirmed day: a date, a status caption, a "Mark missed"/"Undo" link, and a tick
    box per active goal."""

    __gtype_name__ = "StreaksCatchupRow"

    __gsignals__ = {
        "answer-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    header = Gtk.Template.Child()
    date_label = Gtk.Template.Child()
    state_label = Gtk.Template.Child()
    action_button = Gtk.Template.Child()
    goals_list = Gtk.Template.Child()

    def __init__(self, **kwargs):
        """Initialize the row. Call ``configure()`` before it renders anything useful."""
        super().__init__(**kwargs)
        self.day: date | None = None
        self._goal_checks: list[tuple[int, StreaksCatchupGoalRow]] = []
        self._marked_missed = False

        self.action_button.connect("clicked", self._on_action_clicked)

    # -- configuration -------------------------------------------------------------

    def configure(self, day: date, goals: Sequence[GoalData]) -> None:
        """Populate the row for ``day``, with one unticked checkbox per active goal."""
        self.day = day
        self._marked_missed = False
        self.date_label.set_label(words.fmt_weekday_day(day))

        self.goals_list.remove_all()
        self._goal_checks.clear()
        for goal in goals:
            row = StreaksCatchupGoalRow()
            row.goal_id = goal.id
            row.check.set_label(goal.name)
            row.check.set_active(False)
            row.check.connect("toggled", self._on_goal_toggled)
            self.goals_list.append(row)
            self._goal_checks.append((goal.id, row))

        self._update_visual()

    # -- reading state ---------------------------------------------------------------

    def current_answer(self) -> tuple[Answer, tuple[int, ...]] | None:
        """This row's answer as ``(status, missed_goal_ids)``, derived from its ticks, or
        ``None`` if unconfirmed."""
        total = len(self._goal_checks)
        ticked = [gid for gid, row in self._goal_checks if row.check.get_active()]
        if total and len(ticked) == total:
            return (Answer.KEPT, ())
        if not ticked:
            return (Answer.MISSED, ()) if self._marked_missed else None
        missed_ids = tuple(gid for gid, row in self._goal_checks if not row.check.get_active())
        return (Answer.MISSED, missed_ids)

    # -- writing back the computed preview ---------------------------------------------

    def set_state_text(self, text: str) -> None:
        """Set the caption under the date, as computed by ``engine.catch_up_preview``."""
        self.state_label.set_label(text)

    # -- interactions ---------------------------------------------------------------

    def _on_goal_toggled(self, _check: Gtk.CheckButton) -> None:
        # Ticking (or unticking) any goal clears an explicit "Mark missed".
        self._marked_missed = False
        self._update_visual()
        self.emit("answer-changed")

    def _on_action_clicked(self, _button: Gtk.Button) -> None:
        self._marked_missed = not self._marked_missed
        self._update_visual()
        self.emit("answer-changed")

    def _update_visual(self) -> None:
        answer = self.current_answer()
        is_partial = answer is not None and answer[0] == Answer.MISSED and bool(answer[1])
        is_missed_or_partial = answer is not None and answer[0] == Answer.MISSED

        if is_missed_or_partial:
            self.add_css_class("missed")
        else:
            self.remove_css_class("missed")

        for _gid, row in self._goal_checks:
            ticked = row.check.get_active()
            if ticked:
                row.add_css_class("ticked")
            else:
                row.remove_css_class("ticked")
            if is_partial and not ticked:
                row.add_css_class("missed")
            else:
                row.remove_css_class("missed")

        if self._marked_missed:
            self.action_button.set_label(_("Undo"))
            self.action_button.set_visible(True)
        elif answer is None:
            self.action_button.set_label(_("Mark missed"))
            self.action_button.set_visible(True)
        else:
            self.action_button.set_visible(False)
