"""One goal's tick box inside a catch-up dialog day card."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GObject, Gtk


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/catchup_goal_row.ui")
class StreaksCatchupGoalRow(Gtk.ListBoxRow):
    """A single catch-up goal row: a checkbox carrying the goal's name and id."""

    __gtype_name__ = "StreaksCatchupGoalRow"

    check = Gtk.Template.Child()

    goal_id = GObject.Property(type=int, default=0)
