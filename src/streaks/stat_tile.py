"""One stat tile in the streak history view (design-spec §4)."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk

_ACCENT_CLASS = "stat-accent"
_DIM_CLASS = "dim-label"


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/stat_tile.ui")
class StreaksStatTile(Gtk.Box):
    """A single stat tile: a big number and a caption underneath.

    No engine logic lives here — ``configure()`` only places an already-computed
    ``(value, caption, style)`` triple, one entry of ``engine.History.tiles``.
    """

    __gtype_name__ = "StreaksStatTile"

    value_label = Gtk.Template.Child()
    caption_label = Gtk.Template.Child()

    def configure(self, value: str, caption: str, style: str) -> None:
        """Populate the tile from one ``engine.History.tiles`` entry."""
        self.value_label.set_label(value)
        self.caption_label.set_label(caption)
        self.value_label.remove_css_class(_ACCENT_CLASS)
        self.value_label.remove_css_class(_DIM_CLASS)
        if style == "accent":
            self.value_label.add_css_class(_ACCENT_CLASS)
        elif style == "dim":
            self.value_label.add_css_class(_DIM_CLASS)
