"""One editable goal row inside the new/edit streak dialog (design-spec §6).

No engine/database logic lives here: the row just holds a name entry and a remove button, and
reports drag/keyboard reorder requests via signals; the owning dialog (``streak_dialog.py``)
decides what removing/renaming/adding/reordering means (it owns the row order, since that's what
gets saved as goal position).
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gio, GObject, Gtk


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/goal_edit_row.ui")
class StreaksGoalEditRow(Gtk.ListBoxRow):
    """One goal being named/edited: a drag handle, a name entry, and a remove button.

    Emits ``move-requested`` (direction: ``-1`` up / ``+1`` down) when its keyboard fallback
    actions (``row.move-up``/``row.move-down``, bound to Alt+Up/Alt+Down while the entry is
    focused — design-spec §6/Phase 8 deliverable 1) fire. Drag-and-drop reordering is wired by the
    owning dialog directly onto ``handle``/the goals list, since that needs a single
    ``Gtk.DropTarget`` shared by every row rather than one per row.
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
        # On the entry (not the row): that's what actually holds focus while editing a goal's
        # name, which is what "when a goal entry is focused" (design-spec/Phase 8 deliverable 1)
        # means.
        self.entry.add_controller(shortcuts)
