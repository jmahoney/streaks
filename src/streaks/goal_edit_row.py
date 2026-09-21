"""One editable goal row inside the new/edit streak dialog (design-spec §6).

The row holds a name entry and a remove button, and reports drag/keyboard reorder requests via
signals. The owning dialog (``streak_dialog.py``) decides what removing/renaming/adding/
reordering means; it owns the row order, since that's what gets saved as goal position.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gio, GObject, Gtk


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/goal_edit_row.ui")
class StreaksGoalEditRow(Gtk.ListBoxRow):
    """One goal being named/edited: a drag handle, a name entry, and a remove button.

    Emits ``move-requested`` (-1 up / +1 down) from the Alt+Up/Alt+Down shortcuts on the entry.
    Drag-and-drop is wired by the owning dialog, which holds the one `Gtk.DropTarget` for the
    whole list.
    """

    __gtype_name__ = "StreaksGoalEditRow"

    __gsignals__ = {
        "move-requested": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    handle = Gtk.Template.Child()
    entry = Gtk.Template.Child()
    remove_button = Gtk.Template.Child()

    goal_id = GObject.Property(type=int, default=0)

    def __init__(self, **kwargs):
        """Initialize the row, including its keyboard-reorder fallback actions."""
        super().__init__(**kwargs)
        self._install_move_actions()

    def _install_move_actions(self) -> None:
        move_up = Gio.SimpleAction.new("move-up", None)
        move_up.connect("activate", lambda *_a: self.emit("move-requested", -1))
        move_down = Gio.SimpleAction.new("move-down", None)
        move_down.connect("activate", lambda *_a: self.emit("move-requested", 1))
        group = Gio.SimpleActionGroup()
        group.add_action(move_up)
        group.add_action(move_down)
        self.insert_action_group("row", group)

        shortcuts = Gtk.ShortcutController()
        shortcuts.set_scope(Gtk.ShortcutScope.LOCAL)
        shortcuts.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("<Alt>Up"), Gtk.NamedAction.new("row.move-up")
            )
        )
        shortcuts.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("<Alt>Down"), Gtk.NamedAction.new("row.move-down")
            )
        )
        # The entry holds focus while a goal is being edited, so the shortcuts live there.
        self.entry.add_controller(shortcuts)
