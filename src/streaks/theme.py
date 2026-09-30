"""Colour scheme support. The dark scheme uses an amber accent.

* The chart palettes. The engine describes chart cells with scheme-agnostic tokens
  (``engine.CHART_*``); ``resolve()`` turns a token into the hex for the current scheme.
* The stored streak colours. Streaks are saved with their light-scheme hex (``models.COLOURS``);
  ``colour_class()`` names the CSS class that paints that colour in either scheme (the
  ``streak-*`` rules and their ``prefers-color-scheme: dark`` overrides in ``data/style.css``).
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from streaks.engine import (
    CHART_FULL,
    CHART_HIGH,
    CHART_HOLLOW,
    CHART_LOW,
    CHART_MID,
    CHART_MISSED,
    CHART_UNCONFIRMED_BORDER,
    CHART_UPCOMING,
    CHART_ZERO,
)
from streaks.models import COLOURS

# The empty state's single "hint" cell: light reuses the low chart step.
CHART_EMPTY_HINT = "chart-empty-hint"

LIGHT_PALETTE: dict[str, str] = {
    CHART_ZERO: "#e9e9e7",
    CHART_LOW: "#cfe2f8",
    CHART_MID: "#92bdf0",
    CHART_HIGH: "#4b8fdb",
    CHART_FULL: "#1a68c7",
    CHART_HOLLOW: "#ffffff",
    CHART_UNCONFIRMED_BORDER: "#a9c9ef",
    CHART_MISSED: "#f3c0c4",
    CHART_UPCOMING: "#f4f4f2",
    CHART_EMPTY_HINT: "#cfe2f8",
}

DARK_PALETTE: dict[str, str] = {
    CHART_ZERO: "#2c2c30",
    CHART_LOW: "#4a3a22",
    CHART_MID: "#8a5f22",
    CHART_HIGH: "#c9822c",
    CHART_FULL: "#ffa348",
    CHART_HOLLOW: "rgba(0, 0, 0, 0)",
    CHART_UNCONFIRMED_BORDER: "#6b5230",
    CHART_MISSED: "#8e4a50",
    CHART_UPCOMING: "#232326",
    CHART_EMPTY_HINT: "#7a4d18",
}

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
    palette = DARK_PALETTE if is_dark() else LIGHT_PALETTE
    return palette.get(token, token)


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
    """Run ``callback`` whenever the scheme flips while ``widget`` is realized.

    The handler is connected on realize and dropped on unrealize, so a discarded widget never
    keeps itself alive through the ``Adw.StyleManager`` singleton.
    """
    manager = Adw.StyleManager.get_default()
    handler_ids: list[int] = []

    def on_realize(_widget: Gtk.Widget) -> None:
        handler_ids.append(manager.connect("notify::dark", lambda *_args: callback()))

    def on_unrealize(_widget: Gtk.Widget) -> None:
        for handler_id in handler_ids:
            manager.disconnect(handler_id)
        handler_ids.clear()

    widget.connect("realize", on_realize)
    widget.connect("unrealize", on_unrealize)
