"""Widget walkers shared by the GUI test suite and `screens.py`."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gi.repository import Gtk

    from streaks.window import StreaksWindow


def sidebar_rows(window: StreaksWindow) -> list:
    """`window`'s sidebar rows, in display order, skipping the section-header labels
    `Gtk.ListBox` interleaves as row siblings (see `Gtk.ListBoxRow.set_header`)."""
    from streaks.sidebar_row import StreaksSidebarRow

    rows = []
    child = window.sidebar_list.get_first_child()
    while child is not None:
        if isinstance(child, StreaksSidebarRow):
            rows.append(child)
        child = child.get_next_sibling()
    return rows


def listbox_rows(listbox: Gtk.ListBox) -> list:
    """Every row in `listbox`, in order."""
    rows = []
    row = listbox.get_row_at_index(0)
    while row is not None:
        rows.append(row)
        row = row.get_next_sibling()
    return rows


def box_children(box: Gtk.Widget) -> list:
    """Every direct child widget of `box`, in order."""
    children = []
    child = box.get_first_child()
    while child is not None:
        children.append(child)
        child = child.get_next_sibling()
    return children


def select_streak(window: StreaksWindow, name: str):
    """Select and return the sidebar row named `name`."""
    for row in sidebar_rows(window):
        if row.name_label.get_label() == name:
            window.sidebar_list.select_row(row)
            return row
    raise AssertionError(f"no sidebar row named {name!r}")
