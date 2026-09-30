"""Catch-up dialog: tick completed goals for every unconfirmed day at once.

Each unconfirmed day is its own card; the user ticks the goals they completed and the day's
answer follows from those ticks (see ``StreaksCatchupRow``). ``Save`` writes through
``models.answer_day``.
"""

from __future__ import annotations

from datetime import date

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from streaks import engine
from streaks.catchup_row import StreaksCatchupRow  # noqa: F401  registers $StreaksCatchupRow
from streaks.engine import Answer
from streaks.models import Streak, answer_day, db
from streaks.state import AppState
from streaks.widgets.grid_widgets import StripWidget  # noqa: F401  registers $StripWidget

# The result strip is 9×20 with a 3px gap.
_RESULT_CELL_WIDTH = 9
_RESULT_CELL_HEIGHT = 20
_RESULT_GAP = 3


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/catchup_dialog.ui")
class StreaksCatchupDialog(Adw.Dialog):
    """Answer every unconfirmed day of one streak's current run, then save them all at once."""

    __gtype_name__ = "StreaksCatchupDialog"

    cancel_button = Gtk.Template.Child()
    save_button = Gtk.Template.Child()
    dialog_title = Gtk.Template.Child()
    intro_label = Gtk.Template.Child()
    days_box = Gtk.Template.Child()
    result_title = Gtk.Template.Child()
    result_strip = Gtk.Template.Child()
    result_label = Gtk.Template.Child()

    def __init__(self, state: AppState, streak_id: int, **kwargs):
        """Initialize the dialog for ``streak_id``, building one row per unconfirmed day."""
        super().__init__(**kwargs)
        self.state = state
        self.streak_id = streak_id
        self._streak = next(s for s in state.streaks if s.id == streak_id)
        self._rows: list[StreaksCatchupRow] = []
        self._answers: dict[date, tuple[Answer, tuple[int, ...]]] = {}

        self.result_strip.cell_width = _RESULT_CELL_WIDTH
        self.result_strip.cell_height = _RESULT_CELL_HEIGHT
        self.result_strip.gap = _RESULT_GAP

        self.cancel_button.connect("clicked", self._on_cancel_clicked)
        self.save_button.connect("clicked", self._on_save_clicked)

        self._build_rows()
        self._recompute()

    # -- construction -------------------------------------------------------------

    def _build_rows(self) -> None:
        today = self.state.today()
        settings = self.state.settings.to_engine()
        cu = engine.catch_up(self._streak, today, settings)
        self.dialog_title.set_subtitle(cu.subtitle)

        active_goals = sorted(
            (g for g in self._streak.goals if g.removed_on is None), key=lambda g: g.position
        )
        for cu_day in cu.days:
            row = StreaksCatchupRow()
            row.configure(cu_day.day, active_goals)
            row.connect("answer-changed", self._on_row_changed)
            self.days_box.append(row)
            self._rows.append(row)

    # -- recomputation ---------------------------------------------------------------

    def _on_row_changed(self, _row: StreaksCatchupRow) -> None:
        self._recompute()

    def _recompute(self) -> None:
        today = self.state.today()
        settings = self.state.settings.to_engine()

        answers: dict[date, tuple[Answer, tuple[int, ...]]] = {}
        for row in self._rows:
            answer = row.current_answer()
            if answer is not None and row.day is not None:
                answers[row.day] = answer
        self._answers = answers

        preview = engine.catch_up_preview(self._streak, today, settings, answers)
        for row in self._rows:
            row.set_state_text(preview.row_state.get(row.day, ""))

        self.result_strip.set_cells(preview.strip)
        self.result_label.set_label(preview.summary)
        if preview.ends_run:
            self.result_label.remove_css_class("dim-label")
            self.result_label.add_css_class("error")
        else:
            self.result_label.remove_css_class("error")
            self.result_label.add_css_class("dim-label")

        self.save_button.set_sensitive(bool(answers))

    # -- save/cancel ---------------------------------------------------------------

    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        self.close()

    def _on_save_clicked(self, _button: Gtk.Button) -> None:
        streak = Streak.get_by_id(self.streak_id)
        with db.atomic():
            for day, (status, missed_ids) in self._answers.items():
                answer_day(streak, day, status, list(missed_ids))
        self.state.reload()
        self.close()
