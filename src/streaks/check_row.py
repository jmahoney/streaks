"""Toggle guard and "done" styling shared by the check-in goal rows.

Free functions rather than a base class: a Blueprint template's parent type must be the class's
direct GTK parent.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk


def setup(row: Gtk.ListBoxRow) -> None:
    """Wire `row.check`'s toggles to `row`'s own `toggle-requested`, guarded by a
    `row._configuring` flag `configure()` sets around its own `check.set_active()` call."""
    row._configuring = False
    row.check.connect("toggled", lambda _check: _on_check_toggled(row))


def _on_check_toggled(row: Gtk.ListBoxRow) -> None:
    if row._configuring:
        return
    row.emit("toggle-requested")


def set_done_look(label: Gtk.Label, done: bool) -> None:
    """Add/remove the "completed" look (strikethrough, dimmed) on `label`."""
    if done:
        label.add_css_class("strike")
        label.add_css_class("dim-label")
    else:
        label.remove_css_class("strike")
        label.remove_css_class("dim-label")
