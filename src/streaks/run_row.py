"""One earlier-run row in the streak history's "Earlier runs" card (design-spec §4)."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GObject, Gtk

from streaks.engine import Cell
from streaks.widgets.grid_widgets import StripWidget


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/run_row.ui")
class StreaksRunRow(Gtk.ListBoxRow):
    """One finished run: its title, date range/length, and a compact strip of its days.

    ``configure()`` places an already-computed entry of ``engine.History.earlier_runs``.
    Activating the row is the owning view's job to interpret, switching the chart to show
    this run.
    """

    __gtype_name__ = "StreaksRunRow"

    title_label = Gtk.Template.Child()
    meta_label = Gtk.Template.Child()
    strip_slot = Gtk.Template.Child()

    run_index = GObject.Property(type=int, default=0)

    def __init__(self, **kwargs):
        """Initialize the row and its 7×18 (gap 2) day strip (design-spec §4)."""
        super().__init__(**kwargs)
        self.strip = StripWidget(cell_width=7, cell_height=18, gap=2)
        self.strip_slot.append(self.strip)

    def configure(self, title: str, meta: str, cells: list[Cell], run_index: int) -> None:
        """Populate the row from one ``engine.History.earlier_runs`` tuple."""
        self.run_index = run_index
        self.title_label.set_label(title)
        self.meta_label.set_label(meta)
        self.strip.set_cells(cells)
