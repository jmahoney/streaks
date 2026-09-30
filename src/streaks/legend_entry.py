"""One swatch/caption pair in the streak history chart's legend."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

from streaks.engine import Cell, LegendEntry
from streaks.widgets.grid_widgets import StripWidget  # noqa: F401  registers $StripWidget


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/legend_entry.ui")
class StreaksLegendEntry(Gtk.Box):
    """One legend entry: a one-cell colour swatch and a caption label."""

    __gtype_name__ = "StreaksLegendEntry"

    swatch = Gtk.Template.Child()
    caption_label = Gtk.Template.Child()

    def configure(self, entry: LegendEntry) -> None:
        """Populate the entry from one ``engine.History.legend`` entry."""
        self.swatch.set_cells([Cell(entry.fill, entry.border, "")])
        self.caption_label.set_label(entry.label)
