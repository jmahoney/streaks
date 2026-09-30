"""Tests for the custom cell-grid drawing widgets."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402
from render import pixel_at, render_widget, texture_pixels  # noqa: E402

from streaks.engine import Cell  # noqa: E402
from streaks.widgets.grid_widgets import EmptyGridWidget, HeatmapWidget, StripWidget  # noqa: E402


def _realize(app, widget, width, height):
    """Put `widget` in a realized, mapped, correctly-sized window and pump the loop."""
    window = Gtk.Window(application=app)
    window.set_child(widget)
    window.set_default_size(width, height)
    window.present()
    return window


def _natural_size(widget):
    width = widget.measure(Gtk.Orientation.HORIZONTAL, -1)[0]
    height = widget.measure(Gtk.Orientation.VERTICAL, -1)[0]
    return width, height


def test_empty_grid_natural_size(app, process_events):
    widget = EmptyGridWidget()
    window = _realize(app, widget, 200, 200)
    process_events()

    width, height = _natural_size(widget)
    assert width == 7 * 14 + 6 * 5
    assert height == 4 * 14 + 3 * 5

    window.destroy()


def test_heatmap_natural_width(app, process_events):
    widget = HeatmapWidget()
    widget.set_cells([Cell("#e9e9e7", None, "") for _ in range(7 * 30)])
    window = _realize(app, widget, 600, 200)
    process_events()

    width, _height = _natural_size(widget)
    assert width == 30 * 13 + 29 * 4

    window.destroy()


def test_cell_at_maps_point_to_index(app, process_events):
    widget = HeatmapWidget()
    widget.set_cells([Cell("#e9e9e7", None, f"cell {i}") for i in range(7 * 3)])
    window = _realize(app, widget, 200, 200)
    process_events()

    # Column-major layout: index = column * rows + row.
    assert widget.cell_at(2, 2) == 0  # column 0, row 0
    assert widget.cell_at(2, 13 + 4 + 2) == 1  # column 0, row 1
    assert widget.cell_at(13 + 4 + 2, 2) == 7  # column 1, row 0
    assert widget.cell_at(13, 13) is None  # inside the gap between cells

    window.destroy()


def test_tooltip_text_for_cell(app, process_events):
    widget = HeatmapWidget()
    cells = [Cell("#e9e9e7", None, f"cell {i}") for i in range(7 * 2)]
    widget.set_cells(cells)
    window = _realize(app, widget, 200, 200)
    process_events()

    index = widget.cell_at(2, 2)
    assert index is not None
    assert cells[index].tooltip == "cell 0"

    window.destroy()


def test_strip_widget_size(app, process_events):
    widget = StripWidget(cell_width=8, cell_height=22, gap=3, radius=2)
    widget.set_cells([Cell("#1a68c7", None, "") for _ in range(24)])
    window = _realize(app, widget, 400, 100)
    process_events()

    width, height = _natural_size(widget)
    assert width == 24 * 8 + 23 * 3
    assert height == 22

    window.destroy()


def test_cell_renders_with_fill_colour(app, process_events):
    widget = EmptyGridWidget()
    cells = [Cell("#e9e9e7", None, "") for _ in range(27)]
    cells.append(Cell("#cfe2f8", None, ""))
    widget.set_cells(cells)

    width, height = _natural_size(widget)
    window = _realize(app, widget, width, height)
    process_events()

    texture = render_widget(widget, width, height)
    pixels, stride, _w, _h = texture_pixels(texture)

    # Centre of cell 0 (top-left, 14x14 starting at the origin).
    r, g, b = pixel_at(pixels, stride, 7, 7)
    assert abs(r - 0xE9) <= 2
    assert abs(g - 0xE9) <= 2
    assert abs(b - 0xE7) <= 2

    window.destroy()
