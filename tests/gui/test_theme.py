"""Colour scheme support: palettes, streak colour classes, live switching."""

from __future__ import annotations

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402
from render import pixel_at, render_widget, set_colour_scheme, texture_pixels  # noqa: E402

from streaks import engine, theme  # noqa: E402
from streaks.engine import Cell  # noqa: E402
from streaks.models import COLOURS  # noqa: E402
from streaks.widgets.grid_widgets import StripWidget  # noqa: E402

ALL_TOKENS = (
    engine.CHART_ZERO,
    engine.CHART_LOW,
    engine.CHART_MID,
    engine.CHART_HIGH,
    engine.CHART_FULL,
    engine.CHART_HOLLOW,
    engine.CHART_UNCONFIRMED_BORDER,
    engine.CHART_MISSED,
    engine.CHART_UPCOMING,
    theme.CHART_EMPTY_HINT,
)


@pytest.fixture
def light_again():
    """Whatever a test does to the scheme, hand the next test the light default back."""
    yield
    set_colour_scheme(dark=False)


def _hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


@pytest.mark.parametrize("palette", [theme.LIGHT_PALETTE, theme.DARK_PALETTE])
def test_palettes_cover_every_token_with_parseable_colours(palette):
    assert set(palette) == set(ALL_TOKENS)
    for value in palette.values():
        assert Gdk.RGBA().parse(value), value


def test_dark_scheme_hollow_cell_is_fully_transparent():
    """An unconfirmed (hollow) cell in the dark scheme paints no fill of its own — only its
    border shows, over whatever sits behind it."""
    hollow = Gdk.RGBA()
    hollow.parse(theme.DARK_PALETTE[engine.CHART_HOLLOW])
    assert hollow.alpha == 0


def test_resolve_follows_the_scheme(app, light_again):
    set_colour_scheme(dark=False)
    assert not theme.is_dark()
    assert theme.resolve(engine.CHART_FULL) == "#1a68c7"
    assert theme.resolve("#123456") == "#123456"  # plain hex passes straight through

    set_colour_scheme(dark=True)
    assert theme.is_dark()
    assert theme.resolve(engine.CHART_FULL) == "#ffa348"


def test_every_stored_colour_has_a_class():
    classes = [theme.colour_class(c) for c in COLOURS]
    assert classes == [
        "streak-blue",
        "streak-green",
        "streak-yellow",
        "streak-red",
        "streak-purple",
    ]
    assert theme.colour_classes() == tuple(classes)


def test_grid_repaints_when_the_scheme_flips(app, process_events, light_again):
    """A realized grid re-resolves its tokens on notify::dark without a new set_cells()."""
    widget = StripWidget()
    widget.set_cells([Cell(engine.CHART_FULL, None, "") for _ in range(24)])
    width = widget.measure(Gtk.Orientation.HORIZONTAL, -1)[0]
    height = widget.measure(Gtk.Orientation.VERTICAL, -1)[0]

    window = Gtk.Window(application=app)
    window.set_child(widget)
    window.set_default_size(width, height)
    window.present()
    process_events()

    pixels, stride, _w, _h = texture_pixels(render_widget(widget, width, height))
    assert _hex(*pixel_at(pixels, stride, 4, 11)) == "#1a68c7"

    set_colour_scheme(dark=True)
    process_events()
    pixels, stride, _w, _h = texture_pixels(render_widget(widget, width, height))
    assert _hex(*pixel_at(pixels, stride, 4, 11)) == "#ffa348"

    window.destroy()
