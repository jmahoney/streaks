"""Catch-up dialog (design-spec §5): answer every unconfirmed day for one streak at once.

No engine logic lives here beyond the writes ``Save`` has to make (``models.answer_day``) —
every string, colour and sensitivity rule comes straight from ``engine.catch_up``/
``engine.catch_up_preview``. Build it with ``StreaksCatchupDialog(state, streak_id)`` and
``present(window)`` it, same as ``StreaksStreakDialog``.
"""

from __future__ import annotations

import gettext
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

_ = gettext.gettext

# Design-spec §5: the result strip is 9×20 (gap 3), unlike the banner's default 8×22 strip.
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
    days_list = Gtk.Template.Child()
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
        for day, _label in cu.days:
            row = StreaksCatchupRow()
            row.configure(day, active_goals)
            row.connect("answer-changed", self._on_row_changed)
            self.days_list.append(row)
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
            row.set_warning(preview.row_warning.get(row.day))

        self.result_strip.set_cells(preview.strip)
        self.result_label.set_label(preview.summary)

        any_answered = bool(answers)
        missed_rows_ok = all(
            bool(missed_ids) for status, missed_ids in answers.values() if status == Answer.MISSED
        )
        self.save_button.set_sensitive(any_answered and missed_rows_ok)

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
