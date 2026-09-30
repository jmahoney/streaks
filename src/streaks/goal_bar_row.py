"""One goal row in the streak history's "Per goal, all time" card."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib, Gtk

from streaks.engine import GoalBar

_LOW_CLASS = "low"


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/goal_bar_row.ui")
class StreaksGoalBarRow(Gtk.ListBoxRow):
    """One goal's all-time completion ratio: a name, a progress bar, and a ratio caption."""

    __gtype_name__ = "StreaksGoalBarRow"

    name_label = Gtk.Template.Child()
    bar = Gtk.Template.Child()
    ratio_label = Gtk.Template.Child()

    def configure(self, bar: GoalBar) -> None:
        """Populate the row from one ``engine.History.goal_bars`` entry."""
        self.name_label.set_label(bar.name)
        self.bar.set_fraction(bar.ratio)
        self.ratio_label.set_markup(f"<b>{GLib.markup_escape_text(bar.ratio_text)}</b>")
        if bar.low:
            self.bar.add_css_class(_LOW_CLASS)
        else:
            self.bar.remove_css_class(_LOW_CLASS)
