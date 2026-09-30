"""One stat tile in the streak history view."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

from streaks.engine import Tile

_ACCENT_CLASS = "stat-accent"


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/stat_tile.ui")
class StreaksStatTile(Gtk.Box):
    """A single stat tile: a big number and a caption underneath."""

    __gtype_name__ = "StreaksStatTile"

    value_label = Gtk.Template.Child()
    caption_label = Gtk.Template.Child()

    def configure(self, tile: Tile) -> None:
        """Populate the tile from one ``engine.History.tiles`` entry."""
        self.value_label.set_label(tile.value)
        self.caption_label.set_label(tile.caption)
        self.value_label.remove_css_class(_ACCENT_CLASS)
        if tile.style == "accent":
            self.value_label.add_css_class(_ACCENT_CLASS)
