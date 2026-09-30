"""The Today view's single-goal check-in row."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GObject, Gtk

from streaks import check_row, theme
from streaks.engine import Card


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/single_goal_row.ui")
class StreaksSingleGoalRow(Gtk.ListBoxRow):
    """A single-goal streak's whole check-in row: colour dot, name, subtitle and a checkbox.

    The row emits ``toggle-requested`` when its checkbox changes, whether from a direct click or
    the owning card flipping it in response to row activation.
    """

    __gtype_name__ = "StreaksSingleGoalRow"

    __gsignals__ = {
        "toggle-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    check = Gtk.Template.Child()
    name_label = Gtk.Template.Child()
    subtitle_label = Gtk.Template.Child()
    dot = Gtk.Template.Child()

    goal_id = GObject.Property(type=int, default=0)

    def __init__(self, **kwargs):
        """Initialize the row."""
        super().__init__(**kwargs)
        check_row.setup(self)

    def configure(self, card: Card) -> None:
        """Populate the row from a single-goal ``engine.Card``."""
        goal = card.goals[0]

        self._configuring = True
        self.goal_id = goal.goal_id
        self.check.set_active(goal.done_at is not None)
        self._configuring = False

        theme.set_colour_class(self.dot, card.colour)
        self.name_label.set_label(card.name)
        self.subtitle_label.set_label(card.meta)
        check_row.set_done_look(self.name_label, goal.done_at is not None)
