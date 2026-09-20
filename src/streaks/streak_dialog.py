"""New/Edit streak dialog (design-spec §6), also used for editing (Phase 5's `win.edit-streak`).

No engine logic lives here beyond the handful of writes a streak editor has to make
(``models.create_streak``/``models.update_streak``) — everything else is plain widget wiring.
Call ``set_state()`` before presenting so ``Save`` has an ``AppState`` to write through and
reload.
"""

from __future__ import annotations

import gettext
from datetime import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GObject, Gtk

from streaks import theme
from streaks.engine import PeriodKind, StreakData
from streaks.goal_edit_row import StreaksGoalEditRow  # noqa: F401  registers $StreaksGoalEditRow
from streaks.models import COLOURS, Streak, create_streak, update_streak
from streaks.state import AppState

_ = gettext.gettext

_STANDARD_WEEKDAYS = 0b0011111  # Mon-Fri


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/streak_dialog.ui")
class StreaksStreakDialog(Adw.Dialog):
    """The New/Edit streak dialog. Build it with ``for_new()``/``for_edit()``, not ``__init__``."""

    __gtype_name__ = "StreaksStreakDialog"

    cancel_button = Gtk.Template.Child()
    save_button = Gtk.Template.Child()
    name_row = Gtk.Template.Child()
    colour_row = Gtk.Template.Child()
    swatch_0 = Gtk.Template.Child()
    swatch_1 = Gtk.Template.Child()
    swatch_2 = Gtk.Template.Child()
    swatch_3 = Gtk.Template.Child()
    swatch_4 = Gtk.Template.Child()
    period_group = Gtk.Template.Child()
    period_toggle = Gtk.Template.Child()
    weekday_box = Gtk.Template.Child()
    weekday_0 = Gtk.Template.Child()
    weekday_1 = Gtk.Template.Child()
    weekday_2 = Gtk.Template.Child()
    weekday_3 = Gtk.Template.Child()
    weekday_4 = Gtk.Template.Child()
    weekday_5 = Gtk.Template.Child()
    weekday_6 = Gtk.Template.Child()
    times_row = Gtk.Template.Child()
    reminder_row = Gtk.Template.Child()
    reminder_label = Gtk.Template.Child()
    reminder_popover = Gtk.Template.Child()
    reminder_switch = Gtk.Template.Child()
    hour_spin = Gtk.Template.Child()
    minute_spin = Gtk.Template.Child()
    skip_row = Gtk.Template.Child()
    goals_group = Gtk.Template.Child()
    goals_list = Gtk.Template.Child()
    add_goal_row = Gtk.Template.Child()

    def __init__(self, **kwargs):
        """Initialize the dialog in its "new streak" default state.

        Use ``for_new()``/``for_edit()`` rather than calling this directly.
        """
        super().__init__(**kwargs)
        self.state: AppState | None = None
        self._editing_id: int | None = None
        self._goal_rows: list[StreaksGoalEditRow] = []

        self._swatches = (
            self.swatch_0,
            self.swatch_1,
            self.swatch_2,
            self.swatch_3,
            self.swatch_4,
        )
        self._weekday_buttons = (
            self.weekday_0,
            self.weekday_1,
            self.weekday_2,
            self.weekday_3,
            self.weekday_4,
            self.weekday_5,
            self.weekday_6,
        )

        for colour, swatch in zip(COLOURS, self._swatches, strict=True):
            swatch.add_css_class(theme.colour_class(colour))

        for i, button in enumerate(self._weekday_buttons):
            button.set_active(i < 5)  # Mon-Fri default, kept across period-kind switches.

        self.reminder_popover.set_parent(self.reminder_row)

        # Goal drag-reorder (design-spec §6/Phase 8 deliverable 1): one `Gtk.DropTarget` on the
        # whole list (rather than one per row) is enough, since dropping anywhere in the list
        # only ever needs to know which row is being dragged and which row it landed on.
        self._drop_target = Gtk.DropTarget.new(GObject.TYPE_PYOBJECT, Gdk.DragAction.MOVE)
        self._drop_target.connect("drop", self._on_goal_row_dropped)
        self.goals_list.add_controller(self._drop_target)

        self.name_row.connect("notify::text", self._on_field_changed)
        self.period_toggle.connect("notify::active-name", self._on_period_changed)
        self.reminder_row.connect("activated", self._on_reminder_activated)
        self.reminder_switch.connect("notify::active", self._update_reminder_label)
        self.hour_spin.connect("value-changed", self._update_reminder_label)
        self.minute_spin.connect("value-changed", self._update_reminder_label)
        self.cancel_button.connect("clicked", self._on_cancel_clicked)
        self.save_button.connect("clicked", self._on_save_clicked)
        self.add_goal_row.connect("activated", self._on_add_goal_activated)

        self.period_toggle.set_active_name("daily")
        self._update_period_visibility("daily")
        self._update_reminder_label()
        self._add_goal_row_widget()

    # -- construction -------------------------------------------------------------

    @classmethod
    def for_new(cls) -> StreaksStreakDialog:
        """Build a dialog for creating a new streak."""
        dialog = cls()
        dialog.set_title(_("New Streak"))
        dialog.save_button.set_label(_("Create"))
        return dialog

    @classmethod
    def for_edit(cls, streak_data: StreakData) -> StreaksStreakDialog:
        """Build a dialog pre-filled to edit an existing streak."""
        dialog = cls()
        dialog._editing_id = streak_data.id
        dialog.set_title(_("Edit Streak"))
        dialog.save_button.set_label(_("Save"))
        dialog._load_from(streak_data)
        return dialog

    def set_state(self, state: AppState) -> None:
        """Bind the dialog to ``state``, needed before ``Save`` can write anything."""
        self.state = state

    def _load_from(self, streak_data: StreakData) -> None:
        self.name_row.set_text(streak_data.name)
        colour_index = list(COLOURS).index(streak_data.colour)
        self._swatches[colour_index].set_active(True)

        period_name = str(streak_data.period_kind)
        self.period_toggle.set_active_name(period_name)
        self._update_period_visibility(period_name)

        for i, button in enumerate(self._weekday_buttons):
            button.set_active(bool(streak_data.weekdays_mask & (1 << i)))

        self.times_row.set_value(streak_data.times_per_week)
        self.skip_row.set_active(streak_data.allow_skip)

        if streak_data.reminder_time is not None:
            self.reminder_switch.set_active(True)
            self.hour_spin.set_value(streak_data.reminder_time.hour)
            self.minute_spin.set_value(streak_data.reminder_time.minute)
        else:
            self.reminder_switch.set_active(False)
        self._update_reminder_label()

        for row in list(self._goal_rows):
            self.goals_list.remove(row)
        self._goal_rows.clear()

        active_goals = sorted(
            (g for g in streak_data.goals if g.removed_on is None), key=lambda g: g.position
        )
        for goal in active_goals:
            self._add_goal_row_widget(text=goal.name, goal_id=goal.id)

    # -- period ---------------------------------------------------------------------

    def _on_period_changed(self, *_args) -> None:
        self._update_period_visibility(self.period_toggle.get_active_name())

    def _update_period_visibility(self, period_name: str | None) -> None:
        is_weekdays = period_name == "weekdays"
        self.weekday_box.set_sensitive(is_weekdays)
        self.times_row.set_visible(period_name == "n_per_week")

    def _selected_period_kind(self) -> PeriodKind:
        return PeriodKind(self.period_toggle.get_active_name())

    def _weekday_mask(self) -> int:
        mask = 0
        for i, button in enumerate(self._weekday_buttons):
            if button.get_active():
                mask |= 1 << i
        return mask

    def _selected_colour(self) -> str:
        for colour, swatch in zip(COLOURS, self._swatches, strict=True):
            if swatch.get_active():
                return colour
        return COLOURS[0]

    # -- reminder ---------------------------------------------------------------------

    def _on_reminder_activated(self, *_args) -> None:
        self.reminder_popover.popup()

    def _update_reminder_label(self, *_args) -> None:
        on = self.reminder_switch.get_active()
        self.hour_spin.set_sensitive(on)
        self.minute_spin.set_sensitive(on)
        if on:
            hour = int(self.hour_spin.get_value())
            minute = int(self.minute_spin.get_value())
            self.reminder_label.set_label(f"{hour:02d}:{minute:02d} ›")
        else:
            self.reminder_label.set_label(_("Off ›"))

    def _selected_reminder_time(self) -> time | None:
        if not self.reminder_switch.get_active():
            return None
        return time(int(self.hour_spin.get_value()), int(self.minute_spin.get_value()))

    # -- goals ---------------------------------------------------------------------

    def _add_goal_row_widget(self, text: str = "", goal_id: int = 0) -> StreaksGoalEditRow:
        row = StreaksGoalEditRow()
        row.goal_id = goal_id
        row.entry.set_text(text)
        row.entry.connect("changed", self._on_field_changed)
        row.entry.connect("activate", self._on_goal_entry_activate, row)
        row.remove_button.connect("clicked", self._on_remove_goal_clicked, row)
        row.connect("move-requested", self._on_goal_row_move_requested)
        self._setup_goal_drag_source(row)
        self._goal_rows.append(row)
        self.goals_list.insert(row, len(self._goal_rows) - 1)
        self._update_goals()
        return row

    # -- goal reordering (drag-and-drop + keyboard fallback) -----------------------------

    def _setup_goal_drag_source(self, row: StreaksGoalEditRow) -> None:
        drag_source = Gtk.DragSource()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        drag_source.connect("prepare", self._on_goal_drag_prepare, row)
        row.handle.add_controller(drag_source)

    def _on_goal_drag_prepare(
        self, _source: Gtk.DragSource, _x: float, _y: float, row: StreaksGoalEditRow
    ) -> Gdk.ContentProvider:
        value = GObject.Value()
        value.init(GObject.TYPE_PYOBJECT)
        value.set_boxed(row)
        return Gdk.ContentProvider.new_for_value(value)

    def _on_goal_row_dropped(
        self, _target: Gtk.DropTarget, source_row: StreaksGoalEditRow, _x: float, y: float
    ) -> bool:
        target_row = self.goals_list.get_row_at_y(int(y))
        if target_row is None or target_row is self.add_goal_row:
            target_index = len(self._goal_rows) - 1
        elif target_row not in self._goal_rows:
            return False
        else:
            target_index = self._goal_rows.index(target_row)
        return self._reorder_goal_row(source_row, target_index)

    def _on_goal_row_move_requested(self, row: StreaksGoalEditRow, direction: int) -> None:
        if row not in self._goal_rows:
            return
        target_index = self._goal_rows.index(row) + direction
        if self._reorder_goal_row(row, target_index):
            row.entry.grab_focus()

    def _reorder_goal_row(self, source_row: StreaksGoalEditRow, target_index: int) -> bool:
        """Move ``source_row`` to ``target_index`` in both the model list and ``goals_list``.

        This is the single place goal order actually changes — both the real drag-and-drop
        ``drop`` handler and the keyboard fallback (``row.move-up``/``row.move-down``) funnel
        through it, and tests call it directly with a row and an index rather than driving actual
        GTK drag/keyboard input. Returns ``False`` (no-op) if ``source_row`` isn't one of this
        dialog's goal rows or ``target_index`` is already where it is/out of range.
        """
        if source_row not in self._goal_rows:
            return False
        target_index = max(0, min(target_index, len(self._goal_rows) - 1))
        current_index = self._goal_rows.index(source_row)
        if current_index == target_index:
            return False
        self._goal_rows.pop(current_index)
        self._goal_rows.insert(target_index, source_row)
        self.goals_list.remove(source_row)
        self.goals_list.insert(source_row, target_index)
        self._update_save_sensitive()
        return True

    def _on_add_goal_activated(self, *_args) -> None:
        row = self._add_goal_row_widget()
        row.entry.grab_focus()

    def _on_goal_entry_activate(self, _entry: Gtk.Entry, row: StreaksGoalEditRow) -> None:
        if row is self._goal_rows[-1]:
            new_row = self._add_goal_row_widget()
            new_row.entry.grab_focus()

    def _on_remove_goal_clicked(self, _button: Gtk.Button, row: StreaksGoalEditRow) -> None:
        if len(self._goal_rows) <= 1:
            return
        self._goal_rows.remove(row)
        self.goals_list.remove(row)
        self._update_goals()

    def _update_goals(self) -> None:
        only_one = len(self._goal_rows) == 1
        for row in self._goal_rows:
            row.remove_button.set_visible(not only_one)
        self.goals_group.set_title(_("Goals — %(n)d") % {"n": len(self._goal_rows)})
        self._update_save_sensitive()

    def _goal_entries(self) -> list[tuple[int, str]]:
        return [(row.goal_id, row.entry.get_text()) for row in self._goal_rows]

    # -- save/cancel ---------------------------------------------------------------------

    def _on_field_changed(self, *_args) -> None:
        self._update_save_sensitive()

    def _update_save_sensitive(self) -> None:
        name_ok = bool(self.name_row.get_text().strip())
        goal_ok = any(text.strip() for _gid, text in self._goal_entries())
        self.save_button.set_sensitive(name_ok and goal_ok)

    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        self.close()

    def _on_save_clicked(self, _button: Gtk.Button) -> None:
        if self.state is None:
            return

        name = self.name_row.get_text()
        colour = self._selected_colour()
        period_kind = self._selected_period_kind()
        weekdays_mask = self._weekday_mask()
        times_per_week = int(self.times_row.get_value())
        reminder_time = self._selected_reminder_time()
        allow_skip = self.skip_row.get_active()
        today = self.state.today()

        if self._editing_id is None:
            goal_names = [text for _gid, text in self._goal_entries()]
            streak = create_streak(
                name,
                colour,
                period_kind,
                goal_names,
                weekdays_mask=weekdays_mask,
                times_per_week=times_per_week,
                reminder_time=reminder_time,
                allow_skip=allow_skip,
                created_on=today,
            )
        else:
            streak = Streak.get_by_id(self._editing_id)
            goals = [(gid or None, text) for gid, text in self._goal_entries()]
            streak = update_streak(
                streak,
                name=name,
                colour=colour,
                period_kind=period_kind,
                weekdays_mask=weekdays_mask,
                times_per_week=times_per_week,
                reminder_time=reminder_time,
                allow_skip=allow_skip,
                goals=goals,
                today=today,
            )

        self.state.set_selection(streak.id)
        self.state.reload()
        self.close()
