"""A single streak's check-in card in the Today view."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GObject, Gtk

from streaks import theme
from streaks.engine import Card
from streaks.goal_row import StreaksGoalRow  # noqa: F401  registers $StreaksGoalRow
from streaks.single_goal_row import (
    StreaksSingleGoalRow,  # noqa: F401  registers $StreaksSingleGoalRow
)


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/checkin_card.ui")
class StreaksCheckinCard(Gtk.Box):
    """One streak's check-in card: header, goal rows, and an optional progress footer. A
    single-goal streak instead renders as one row (``single_list``), with no header or footer.

    Emits ``goal-toggled`` (goal id) and ``mark-missed`` (streak id).
    """

    __gtype_name__ = "StreaksCheckinCard"

    __gsignals__ = {
        "goal-toggled": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "mark-missed": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    multi_box = Gtk.Template.Child()
    dot = Gtk.Template.Child()
    name_label = Gtk.Template.Child()
    meta_label = Gtk.Template.Child()
    goals_list = Gtk.Template.Child()
    body_label = Gtk.Template.Child()
    footer = Gtk.Template.Child()
    progress = Gtk.Template.Child()
    progress_label = Gtk.Template.Child()
    missed_button = Gtk.Template.Child()
    single_list = Gtk.Template.Child()

    streak_id = GObject.Property(type=int, default=0)

    def __init__(self, **kwargs):
        """Initialize the card."""
        super().__init__(**kwargs)
        self.goals_list.connect("row-activated", self._on_row_activated)
        self.single_list.connect("row-activated", self._on_row_activated)
        self.missed_button.connect("clicked", self._on_missed_clicked)

    def _on_row_activated(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        row.check.set_active(not row.check.get_active())

    def _on_missed_clicked(self, _button: Gtk.Button) -> None:
        self.emit("mark-missed", self.streak_id)

    def _on_goal_toggle_requested(self, row: StreaksGoalRow | StreaksSingleGoalRow) -> None:
        self.emit("goal-toggled", row.goal_id)

    def configure(self, card: Card) -> None:
        """Populate the card from an ``engine.Card``."""
        self.streak_id = card.streak_id
        self.multi_box.set_visible(not card.single)
        self.single_list.set_visible(card.single)

        # The (possibly hidden) multi-layout header still carries the card's name/colour, since
        # callers identify a card by its `name_label` regardless of layout.
        theme.set_colour_class(self.dot, card.colour)
        self.name_label.set_label(card.name)
        self.meta_label.set_label(card.meta)

        if card.single:
            self.single_list.remove_all()
            row = StreaksSingleGoalRow()
            row.configure(card)
            row.connect("toggle-requested", self._on_goal_toggle_requested)
            self.single_list.append(row)
            return

        self.goals_list.remove_all()
        for goal in card.goals:
            row = StreaksGoalRow()
            row.configure(goal)
            row.connect("toggle-requested", self._on_goal_toggle_requested)
            self.goals_list.append(row)

        is_not_due = card.kind == "not_due"
        self.body_label.set_visible(is_not_due)
        if is_not_due:
            self.body_label.set_label(card.body or "")

        self.footer.set_visible(card.show_footer)
        if card.show_footer:
            self.progress.set_fraction(card.progress or 0.0)
            self.progress_label.set_label(card.progress_text or "")
