"""One editable goal row inside the new/edit streak dialog (design-spec §6).

No engine/database logic lives here: the row just holds a name entry and a remove button; the
owning dialog (``streak_dialog.py``) decides what removing/renaming/adding means.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GObject, Gtk


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/goal_edit_row.ui")
class StreaksGoalEditRow(Gtk.ListBoxRow):
    """One goal being named/edited: a drag handle, a name entry, and a remove button."""

    __gtype_name__ = "StreaksGoalEditRow"

    handle = Gtk.Template.Child()
    entry = Gtk.Template.Child()
    remove_button = Gtk.Template.Child()

    goal_id = GObject.Property(type=int, default=0)

    def __init__(self, **kwargs):
        """Initialize the row."""
        super().__init__(**kwargs)
