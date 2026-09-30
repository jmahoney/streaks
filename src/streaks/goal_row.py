"""One goal row inside a check-in card."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GObject, Gtk

from streaks import words
from streaks.engine import CardGoal


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/goal_row.ui")
class StreaksGoalRow(Gtk.ListBoxRow):
    """A single check-in goal: a checkbox, its name, and a trailing time/countdown caption.

    The row emits ``toggle-requested`` when its checkbox changes, whether from a direct click or
    the owning card flipping it in response to row activation.
    """

    __gtype_name__ = "StreaksGoalRow"

    __gsignals__ = {
        "toggle-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    check = Gtk.Template.Child()
    name_label = Gtk.Template.Child()
    time_label = Gtk.Template.Child()

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

    def configure(self, goal: CardGoal) -> None:
        """Populate the row from an ``engine.CardGoal``."""
        self._configuring = True
        self.goal_id = goal.goal_id
        self.name_label.set_label(goal.name)
        done = goal.done_at is not None
        self.check.set_active(done)
        self._configuring = False

        if done:
            self.name_label.add_css_class("strike")
            self.name_label.add_css_class("dim-label")
            self.time_label.set_label(words.time_hm(goal.done_at))
            self.time_label.set_visible(True)
        else:
            self.name_label.remove_css_class("strike")
            self.name_label.remove_css_class("dim-label")
            if goal.trailing:
                self.time_label.set_label(goal.trailing)
                self.time_label.set_visible(True)
            else:
                self.time_label.set_label("")
                self.time_label.set_visible(False)
