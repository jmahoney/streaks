"""Custom cell-grid drawing widgets shared by the heatmap, strip and empty-state grid.

All three share one drawing routine: a plain ``Gtk.Widget`` that lays a flat
list of ``engine.Cell`` values on a fixed grid and paints each cell as a rounded rectangle, with
an optional 1px border and a per-cell tooltip. The caller supplies colours and tooltip text as
plain strings via ``set_cells()``; colour tokens (``engine.CHART_*``) are resolved for the
current light/dark scheme by ``streaks.theme``.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gsk", "4.0")

from gi.repository import Gdk, GObject, Graphene, Gsk, Gtk

from streaks import theme
from streaks.engine import Cell


class _CellGridWidget(Gtk.Widget):
    """Base class: paints ``self._cells`` on a fixed-size grid of rounded rectangles.

    Subclasses implement ``_rows_columns()`` to say how big the grid is (fixed, or derived from
    the number of cells) and set ``_major`` to say how a flat cell index maps to a (row, column)
    position: ``"row"`` (index = row * columns + col, left-to-right then top-to-bottom) or
    ``"column"`` (index = col * rows + row, top-to-bottom then left-to-right — used by the
    heatmap, whose cells arrive one week/column at a time).
    """

    _major = "row"

    cell_width = GObject.Property(type=int, default=0)
    cell_height = GObject.Property(type=int, default=0)
    gap = GObject.Property(type=int, default=0)
    radius = GObject.Property(type=int, default=0)

    def __init__(self, cell_width: int, cell_height: int, gap: int, radius: int, **kwargs):
        super().__init__(**kwargs)
        self.cell_width = cell_width
        self.cell_height = cell_height
        self.gap = gap
        self.radius = radius
        self._cells: list[Cell] = []
        self.set_has_tooltip(True)
        theme.watch(self, self.queue_draw)
        for prop in ("cell-width", "cell-height", "gap"):
            self.connect(f"notify::{prop}", lambda *_args: self.queue_resize())
        self.connect("notify::radius", lambda *_args: self.queue_draw())

    @property
    def cells(self) -> list[Cell]:
        """Copy of the cells currently drawn."""
        return list(self._cells)

    def _rows_columns(self) -> tuple[int, int]:
        raise NotImplementedError

    def set_cells(self, cells: list[Cell]) -> None:
        """Replace the cells being drawn and request a re-layout/redraw."""
        self._cells = list(cells)
        self.queue_resize()

    def _index_to_row_col(self, index: int) -> tuple[int, int]:
        rows, columns = self._rows_columns()
        if self._major == "column":
            col, row = divmod(index, rows)
        else:
            row, col = divmod(index, columns)
        return row, col

    def cell_at(self, x: float, y: float) -> int | None:
        """The index of the cell under point ``(x, y)``, or ``None`` (gap or out of bounds)."""
        rows, columns = self._rows_columns()
        step_x = self.cell_width + self.gap
        step_y = self.cell_height + self.gap
        if step_x <= 0 or step_y <= 0 or rows <= 0 or columns <= 0:
            return None
        col = int(x // step_x)
        row = int(y // step_y)
        if col < 0 or row < 0 or col >= columns or row >= rows:
            return None
        cell_x = col * step_x
        cell_y = row * step_y
        if x >= cell_x + self.cell_width or y >= cell_y + self.cell_height:
            return None  # inside the gap between cells
        index = col * rows + row if self._major == "column" else row * columns + col
        if index >= len(self._cells):
            return None
        return index

    def do_measure(self, orientation, _for_size):
        rows, columns = self._rows_columns()
        width = columns * self.cell_width + max(0, columns - 1) * self.gap
        height = rows * self.cell_height + max(0, rows - 1) * self.gap
        size = width if orientation == Gtk.Orientation.HORIZONTAL else height
        return size, size, -1, -1

    def do_snapshot(self, snapshot: Gtk.Snapshot) -> None:
        for index, cell in enumerate(self._cells):
            row, col = self._index_to_row_col(index)
            x = col * (self.cell_width + self.gap)
            y = row * (self.cell_height + self.gap)

            bounds = Graphene.Rect()
            bounds.init(x, y, self.cell_width, self.cell_height)
            rrect = Gsk.RoundedRect()
            rrect.init_from_rect(bounds, self.radius)

            snapshot.push_rounded_clip(rrect)
            colour = Gdk.RGBA()
            colour.parse(theme.resolve(cell.fill))
            snapshot.append_color(colour, bounds)
            snapshot.pop()

            if cell.border:
                border_colour = Gdk.RGBA()
                border_colour.parse(theme.resolve(cell.border))
                widths = [1.0, 1.0, 1.0, 1.0]
                colours = [border_colour, border_colour, border_colour, border_colour]
                snapshot.append_border(rrect, widths, colours)

    def do_query_tooltip(self, x, y, _keyboard_mode, tooltip: Gtk.Tooltip) -> bool:
        index = self.cell_at(x, y)
        if index is None:
            return False
        tooltip.set_text(self._cells[index].tooltip)
        return True


class HeatmapWidget(_CellGridWidget):
    """7 rows × N columns (column-major weeks), cell 13, gap 4, radius 3."""

    __gtype_name__ = "HeatmapWidget"
    _major = "column"

    def __init__(self, **kwargs):
        super().__init__(cell_width=13, cell_height=13, gap=4, radius=3, **kwargs)
        self.columns = 0

    def set_cells(self, cells: list[Cell]) -> None:
        self.columns = len(cells) // 7 if cells else 0
        super().set_cells(cells)

    def _rows_columns(self) -> tuple[int, int]:
        return 7, self.columns


class StripWidget(_CellGridWidget):
    """1 row, configurable cell size/gap, radius 2 by default."""

    __gtype_name__ = "StripWidget"
    _major = "row"

    def __init__(
        self,
        cell_width: int = 8,
        cell_height: int = 22,
        gap: int = 3,
        radius: int = 2,
        **kwargs,
    ):
        super().__init__(
            cell_width=cell_width, cell_height=cell_height, gap=gap, radius=radius, **kwargs
        )

    def _rows_columns(self) -> tuple[int, int]:
        return 1, len(self._cells)


class EmptyGridWidget(_CellGridWidget):
    """Fixed 7 columns × 4 rows grid, cell 14, gap 5, radius 4."""

    __gtype_name__ = "EmptyGridWidget"
    _major = "row"

    def __init__(self, **kwargs):
        super().__init__(cell_width=14, cell_height=14, gap=5, radius=4, **kwargs)

    def _rows_columns(self) -> tuple[int, int]:
        return 4, 7
