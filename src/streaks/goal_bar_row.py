"""One goal row in the streak history's "Per goal, this month" card (design-spec §4)."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib, Gtk

_LOW_CLASS = "low"


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/goal_bar_row.ui")
class StreaksGoalBarRow(Gtk.ListBoxRow):
    """One goal's this-month completion ratio: a name, a progress bar, and a ratio caption.

    ``configure()`` places an already-computed entry of ``engine.History.goal_bars``.
    """

    __gtype_name__ = "StreaksGoalBarRow"

    name_label = Gtk.Template.Child()
    bar = Gtk.Template.Child()
    ratio_label = Gtk.Template.Child()

    def configure(self, name: str, ratio: float, ratio_text: str, low: bool) -> None:
        """Populate the row from one ``engine.History.goal_bars`` tuple."""
        self.name_label.set_label(name)
        self.bar.set_fraction(ratio)
        self.ratio_label.set_markup(f"<b>{GLib.markup_escape_text(ratio_text)}</b>")
        if low:
            self.bar.add_css_class(_LOW_CLASS)
        else:
            self.bar.remove_css_class(_LOW_CLASS)
