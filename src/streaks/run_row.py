"""One earlier-run row in the streak history's "Earlier runs" card."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GObject, Gtk

from streaks.engine import EarlierRun
from streaks.widgets.grid_widgets import StripWidget  # noqa: F401  registers $StripWidget


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/run_row.ui")
class StreaksRunRow(Gtk.ListBoxRow):
    """One finished run: its title, date range/length, and a compact strip of its days."""

    __gtype_name__ = "StreaksRunRow"

    title_label = Gtk.Template.Child()
    meta_label = Gtk.Template.Child()
    strip = Gtk.Template.Child()

    run_index = GObject.Property(type=int, default=0)

    def configure(self, run: EarlierRun) -> None:
        """Populate the row from one ``engine.History.earlier_runs`` entry."""
        self.run_index = run.index
        self.title_label.set_label(run.title)
        self.meta_label.set_label(run.meta)
        self.strip.set_cells(run.strip)
