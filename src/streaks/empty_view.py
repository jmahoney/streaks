"""The empty-state view shown when there are no streaks yet (design-spec §8)."""

from __future__ import annotations

import gettext

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from streaks.engine import CHART_LOW, CHART_ZERO, Cell
from streaks.widgets.grid_widgets import EmptyGridWidget  # noqa: F401  registers $EmptyGridWidget

_ = gettext.gettext

_GRID_ROWS = 4
_GRID_COLUMNS = 7


def _empty_grid_cells() -> list[Cell]:
    """The static decorative grid: every cell empty except the last (bottom-right)."""
    n = _GRID_ROWS * _GRID_COLUMNS
    cells = [Cell(CHART_ZERO, None, "") for _ in range(n - 1)]
    cells.append(Cell(CHART_LOW, None, ""))
    return cells


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/empty_view.ui")
class StreaksEmptyView(Adw.Bin):
    """The centred "no streaks yet" placeholder (design-spec §8)."""

    __gtype_name__ = "StreaksEmptyView"

    grid = Gtk.Template.Child()
    title_label = Gtk.Template.Child()
    body_label = Gtk.Template.Child()
    create_button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        """Initialize the view."""
        super().__init__(**kwargs)
        self.grid.set_cells(_empty_grid_cells())
