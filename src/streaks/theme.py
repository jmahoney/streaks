"""Colour scheme and accent support.

* The chart palette. The engine describes chart cells with scheme-agnostic tokens
  (``engine.CHART_*``); ``resolve()`` turns a token into the hex for the current scheme, with
  the ramp mixed from the system accent colour (``chart_palette()``).
* The stored streak colours. Streaks are saved with their light-scheme hex (``models.COLOURS``);
  ``colour_class()`` names the CSS class that paints that colour in either scheme (the
  ``streak-*`` rules and their ``prefers-color-scheme: dark`` overrides in ``data/style.css``).
"""

from __future__ import annotations

import functools
from collections.abc import Callable

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gtk

from streaks.engine import (
    CHART_FULL,
    CHART_HIGH,
    CHART_HOLLOW,
    CHART_LOW,
    CHART_MID,
    CHART_MISSED,
    CHART_MISSED_BORDER,
    CHART_UNCONFIRMED_BORDER,
    CHART_UPCOMING,
    CHART_ZERO,
)
from streaks.models import COLOURS

# The empty state's single "hint" cell: a step of the accent ramp.
CHART_EMPTY_HINT = "chart-empty-hint"

_LIGHT_BASE = (0xFF, 0xFF, 0xFF)
_DARK_BASE = (0x2C, 0x2C, 0x30)

# Ramp weights of the accent mixed over the scheme's base.
_RAMP: dict[str, float] = {CHART_LOW: 0.25, CHART_MID: 0.5, CHART_HIGH: 0.75, CHART_FULL: 1.0}


def _mix(accent: tuple[int, int, int], base: tuple[int, int, int], weight: float) -> str:
    """Plain per-channel sRGB mix of ``accent`` over ``base``, as lowercase ``#rrggbb``."""
    r, g, b = (int(a * weight + c * (1 - weight) + 0.5) for a, c in zip(accent, base, strict=True))
    return f"#{r:02x}{g:02x}{b:02x}"


@functools.lru_cache(maxsize=32)
def _palette_for(accent_hex: str, dark: bool) -> dict[str, str]:
    accent = (int(accent_hex[1:3], 16), int(accent_hex[3:5], 16), int(accent_hex[5:7], 16))
    base = _DARK_BASE if dark else _LIGHT_BASE
    palette = {token: _mix(accent, base, weight) for token, weight in _RAMP.items()}
    zero = "#2c2c30" if dark else "#e9e9e7"
    palette.update(
        {
            CHART_ZERO: zero,
            CHART_HOLLOW: "rgba(0, 0, 0, 0)" if dark else "#ffffff",
            CHART_UNCONFIRMED_BORDER: _mix(accent, base, 0.45 if dark else 0.4),
            # A miss is a neutral cell with a red border, so it stays distinct from the
            # accent ramp whatever hue the accent is.
            CHART_MISSED: zero,
            CHART_MISSED_BORDER: "#ff938a" if dark else "#c01c28",
            CHART_UPCOMING: "#232326" if dark else "#f4f4f2",
            CHART_EMPTY_HINT: _mix(accent, base, 0.5 if dark else 0.25),
        }
    )
    return palette


def _cached_palette(accent: Gdk.RGBA, dark: bool) -> dict[str, str]:
    """The shared cached palette for ``accent``; callers must not mutate it."""
    accent_hex = "#{:02x}{:02x}{:02x}".format(
        *(int(channel * 255 + 0.5) for channel in (accent.red, accent.green, accent.blue))
    )
    return _palette_for(accent_hex, dark)


def chart_palette(accent: Gdk.RGBA, dark: bool) -> dict[str, str]:
    """Token -> colour for every chart token, with the ramp derived from ``accent``."""
    return dict(_cached_palette(accent, dark))


def accent_rgba() -> Gdk.RGBA:
    """The system accent colour libadwaita is currently following."""
    return Adw.StyleManager.get_default().get_accent_color_rgba()


# Stored (light) streak colour -> CSS class carrying both schemes' hues, in ``COLOURS`` order.
_COLOUR_CLASSES: dict[str, str] = dict(
    zip(
        COLOURS,
        ("streak-blue", "streak-green", "streak-yellow", "streak-red", "streak-purple"),
        strict=True,
    )
)


def is_dark() -> bool:
    """Whether libadwaita is currently rendering the dark scheme."""
    return Adw.StyleManager.get_default().get_dark()


def resolve(token: str) -> str:
    """Hex (or CSS colour name) for a chart token in the current scheme.

    Anything that is not a known token is returned untouched, so plain hex still works.
    """
    return _cached_palette(accent_rgba(), is_dark()).get(token, token)


def colour_class(colour: str) -> str:
    """CSS class for a stored streak colour (see ``models.COLOURS``)."""
    return _COLOUR_CLASSES[colour]


def colour_classes() -> tuple[str, ...]:
    return tuple(_COLOUR_CLASSES.values())


def set_colour_class(widget: Gtk.Widget, colour: str | None, *other_classes: str) -> None:
    """Paint ``widget`` with the CSS class for ``colour``, clearing every streak colour class
    (and every class in ``other_classes``, for a caller with its own non-streak dot classes)
    first. ``colour=None`` clears without adding one."""
    for old in (*colour_classes(), *other_classes):
        widget.remove_css_class(old)
    if colour is not None:
        widget.add_css_class(colour_class(colour))


def watch(widget: Gtk.Widget, callback: Callable[[], None]) -> None:
    """Run ``callback`` whenever the scheme or accent colour changes while ``widget`` is realized.

    The handler is connected on realize and dropped on unrealize, so a discarded widget never
    keeps itself alive through the ``Adw.StyleManager`` singleton.
    """
    manager = Adw.StyleManager.get_default()
    handler_ids: list[int] = []

    def on_realize(_widget: Gtk.Widget) -> None:
        for signal in ("notify::dark", "notify::accent-color-rgba"):
            handler_ids.append(manager.connect(signal, lambda *_args: callback()))

    def on_unrealize(_widget: Gtk.Widget) -> None:
        for handler_id in handler_ids:
            manager.disconnect(handler_id)
        handler_ids.clear()

    widget.connect("realize", on_realize)
    widget.connect("unrealize", on_unrealize)
