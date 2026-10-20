"""Colour scheme support: palettes, streak colour classes, live switching."""

from __future__ import annotations

import time

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402
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
    engine.CHART_MISSED_BORDER,
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


def rgba(value: str) -> Gdk.RGBA:
    colour = Gdk.RGBA()
    assert colour.parse(value), value
    return colour


BLUE = rgba("#3584e4")
RED = rgba("#e62d42")


@pytest.mark.parametrize("dark", [False, True])
def test_palette_covers_every_token_with_parseable_colours(dark):
    palette = theme.chart_palette(BLUE, dark)
    assert set(palette) == set(ALL_TOKENS)
    for value in palette.values():
        assert Gdk.RGBA().parse(value), value


def test_light_ramp_from_default_blue():
    p = theme.chart_palette(BLUE, dark=False)
    ramp = (engine.CHART_LOW, engine.CHART_MID, engine.CHART_HIGH, engine.CHART_FULL)
    assert [p[t] for t in ramp] == ["#cde0f8", "#9ac2f2", "#68a3eb", "#3584e4"]
    assert p[engine.CHART_UNCONFIRMED_BORDER] == "#aecef4"
    assert p[theme.CHART_EMPTY_HINT] == "#cde0f8"


def test_dark_ramp_from_default_blue():
    p = theme.chart_palette(BLUE, dark=True)
    ramp = (engine.CHART_LOW, engine.CHART_MID, engine.CHART_HIGH, engine.CHART_FULL)
    assert [p[t] for t in ramp] == ["#2e425d", "#31588a", "#336eb7", "#3584e4"]
    assert p[engine.CHART_UNCONFIRMED_BORDER] == "#305481"
    assert p[theme.CHART_EMPTY_HINT] == "#31588a"
    assert rgba(p[engine.CHART_HOLLOW]).alpha == 0


@pytest.mark.parametrize("dark", [False, True])
def test_red_accent_keeps_missed_distinct(dark):
    p = theme.chart_palette(RED, dark)
    assert p[engine.CHART_MISSED] == p[engine.CHART_ZERO]  # neutral fill
    assert p[engine.CHART_MISSED_BORDER] == ("#ff938a" if dark else "#c01c28")
    assert p[engine.CHART_MISSED] not in {p[engine.CHART_LOW], p[engine.CHART_MID]}


def test_resolve_follows_the_scheme_and_accent(app, light_again):
    set_colour_scheme(dark=False)
    assert not theme.is_dark()
    assert theme.resolve(engine.CHART_FULL) == "#3584e4"  # test env accent is default blue
    assert theme.resolve("#123456") == "#123456"  # plain hex passes straight through

    set_colour_scheme(dark=True)
    assert theme.is_dark()
    assert theme.resolve(engine.CHART_LOW) == "#2e425d"


def test_stubbed_test_accent_is_default_blue(app):
    assert theme.accent_rgba().to_string() == "rgb(53,132,228)"


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
    widget.set_cells([Cell(engine.CHART_LOW, None, "") for _ in range(24)])
    width = widget.measure(Gtk.Orientation.HORIZONTAL, -1)[0]
    height = widget.measure(Gtk.Orientation.VERTICAL, -1)[0]

    window = Gtk.Window(application=app)
    window.set_child(widget)
    window.set_default_size(width, height)
    window.present()
    process_events()

    pixels, stride, _w, _h = texture_pixels(render_widget(widget, width, height))
    assert _hex(*pixel_at(pixels, stride, 4, 11)) == "#cde0f8"

    set_colour_scheme(dark=True)
    process_events()
    pixels, stride, _w, _h = texture_pixels(render_widget(widget, width, height))
    assert _hex(*pixel_at(pixels, stride, 4, 11)) == "#2e425d"

    window.destroy()


def test_grid_repaints_when_the_accent_changes(app, process_events, light_again, mocker):
    """A realized grid re-resolves its tokens on notify::accent-color-rgba."""
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
    assert _hex(*pixel_at(pixels, stride, 4, 11)) == "#3584e4"

    mocker.patch.object(theme, "accent_rgba", return_value=RED)
    Adw.StyleManager.get_default().notify("accent-color-rgba")
    for _ in range(5):  # let the frame clock rebuild the widget's invalidated render node
        time.sleep(0.05)
        process_events()
    pixels, stride, _w, _h = texture_pixels(render_widget(widget, width, height))
    assert _hex(*pixel_at(pixels, stride, 4, 11)) == "#e62d42"

    window.destroy()
