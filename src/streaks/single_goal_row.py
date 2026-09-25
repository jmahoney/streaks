"""The Today view's single-goal check-in row (design-spec §3 "Single-goal card")."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GObject, Gtk

from streaks import theme
from streaks.engine import Card


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/single_goal_row.ui")
class StreaksSingleGoalRow(Gtk.ListBoxRow):
    """A single-goal streak's whole check-in row: colour dot, name, subtitle and a checkbox.

    ``configure()`` places already-computed strings from an ``engine.Card`` whose ``single`` flag
    is set. The row emits ``toggle-requested`` when its checkbox changes, whether from a direct
    click or the owning card flipping it in response to row activation; the card decides what a
    toggle means, writing a ``GoalCheck``.
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
        self._configuring = False
        self.check.connect("toggled", self._on_check_toggled)

    def _on_check_toggled(self, _check: Gtk.CheckButton) -> None:
        if self._configuring:
            return
        self.emit("toggle-requested")

    def configure(self, card: Card) -> None:
        """Populate the row from a single-goal ``engine.Card``."""
        goal = card.goals[0]

        self._configuring = True
        self.goal_id = goal.goal_id
        self.check.set_active(goal.done_at is not None)
        self._configuring = False

        for css_class in theme.colour_classes():
            self.dot.remove_css_class(css_class)
        self.dot.add_css_class(theme.colour_class(card.colour))
        self.name_label.set_label(card.name)
        self.subtitle_label.set_label(card.meta)

        if goal.done_at is not None:
            self.name_label.add_css_class("strike")
            self.name_label.add_css_class("dim-label")
        else:
            self.name_label.remove_css_class("strike")
            self.name_label.remove_css_class("dim-label")
