"""New/Edit streak dialog. Opened by `win.new-streak` and `win.edit-streak`.

Writes go through ``models.create_streak``/``models.update_streak``; everything else is plain
widget wiring. Call ``set_state()`` before presenting so ``Save`` has an ``AppState`` to write
through and reload.
"""

from __future__ import annotations

import gettext
from datetime import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GLib, GObject, Gtk

from streaks import theme, words
from streaks.engine import PeriodKind, StreakData, current_goals
from streaks.goal_edit_row import StreaksGoalEditRow  # noqa: F401  registers $StreaksGoalEditRow
from streaks.models import COLOURS, Streak, create_streak, update_streak
from streaks.state import AppState
from streaks.time_popover import StreaksTimePopover  # noqa: F401  registers $StreaksTimePopover

_ = gettext.gettext


def _edit_goals_description() -> str:
    """The Goals group description once a streak has more than one goal: new goals count from
    the current period on, so a period already recorded keeps that shade."""
    return _("New goals apply from the current period. Earlier periods keep their recorded shade.")


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/streak_dialog.ui")
class StreaksStreakDialog(Adw.Dialog):
    """The New/Edit streak dialog. ``for_new()``/``for_edit()`` are the constructors; both
    start in single mode, switching to multi only for a streak that already has more than one
    goal."""

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
    skip_row = Gtk.Template.Child()
    name_group = Gtk.Template.Child()
    more_goals_button = Gtk.Template.Child()
    more_goals_hint = Gtk.Template.Child()
    goals_group = Gtk.Template.Child()
    goals_list = Gtk.Template.Child()
    add_goal_row = Gtk.Template.Child()
    delete_group = Gtk.Template.Child()
    delete_row = Gtk.Template.Child()

    def __init__(self, **kwargs):
        """Initialize the dialog in its "new streak" default state (single mode, no goal rows).

        Wires the widget signal handlers; ``for_edit()`` overwrites this state via
        ``_load_from()``.
        """
        super().__init__(**kwargs)
        self.state: AppState | None = None
        self._editing_id: int | None = None
        self._goal_rows: list[StreaksGoalEditRow] = []
        self._multi = False
        # A single-goal streak's one goal, tracked outside the (hidden) goal rows so its id
        # survives a round trip through multi mode. 0 means "a new goal", same as a fresh row.
        self._single_goal_id = 0

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

        # One drop target on the list is enough: a drop only needs the dragged row and the row
        # under the pointer.
        self._drop_target = Gtk.DropTarget.new(GObject.TYPE_PYOBJECT, Gdk.DragAction.MOVE)
        self._drop_target.connect("drop", self._on_goal_row_dropped)
        self.goals_list.add_controller(self._drop_target)

        self.name_row.connect("notify::text", self._on_field_changed)
        self.period_toggle.connect("notify::active-name", self._on_period_changed)
        self.reminder_row.connect("activated", self._on_reminder_activated)
        self.reminder_popover.connect("changed", self._update_reminder_label)
        self.cancel_button.connect("clicked", self._on_cancel_clicked)
        self.save_button.connect("clicked", self._on_save_clicked)
        self.add_goal_row.connect("activated", self._on_add_goal_activated)
        self.more_goals_button.connect("clicked", self._on_more_goals_clicked)
        self.delete_row.connect("activated", self._on_delete_row_activated)

        self.period_toggle.set_active_name("daily")
        self._update_period_visibility("daily")
        self._update_reminder_label()
        self._set_multi(False)

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
            self.reminder_popover.active = True
            self.reminder_popover.minutes = (
                streak_data.reminder_time.hour * 60 + streak_data.reminder_time.minute
            )
        else:
            self.reminder_popover.active = False
        self._update_reminder_label()

        self._clear_goal_rows()

        active_goals = current_goals(streak_data)
        if len(active_goals) == 1:
            self._single_goal_id = active_goals[0].id
            self._set_multi(False)
        else:
            for goal in active_goals:
                self._add_goal_row_widget(text=goal.name, goal_id=goal.id)
            self.goals_group.set_description(_edit_goals_description())
            self._set_multi(True)

        self.delete_group.set_visible(True)

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
        reminder = self._selected_reminder_time()
        if reminder is None:
            self.reminder_label.set_label(_("Off ›"))
        else:
            self.reminder_label.set_label(f"{words.fmt_hm(reminder.hour, reminder.minute)} ›")

    def _selected_reminder_time(self) -> time | None:
        if not self.reminder_popover.active:
            return None
        minutes = self.reminder_popover.minutes
        return time(minutes // 60, minutes % 60)

    # -- single/multi mode ---------------------------------------------------------------------

    def _set_multi(self, multi: bool) -> None:
        self._multi = multi
        self.name_row.set_title(_("Streak name") if multi else _("Name"))
        self.more_goals_button.set_visible(not multi)
        self.goals_group.set_visible(multi)
        # The hint applies to new streaks; editing an existing one may already have expanded it
        # to multi goals in an earlier save.
        self.more_goals_hint.set_visible(self._editing_id is None)
        self._update_save_sensitive()

    def _clear_goal_rows(self) -> None:
        """Remove every goal row widget and forget it, ready to rebuild the list from scratch."""
        for row in list(self._goal_rows):
            self.goals_list.remove(row)
        self._goal_rows.clear()

    def _on_more_goals_clicked(self, _button: Gtk.Button) -> None:
        self._expand_to_multi()

    def _expand_to_multi(self) -> None:
        text = self.name_row.get_text().strip()
        self._clear_goal_rows()

        # Editing keeps the single goal's id so its history survives; a new streak's goal 1 is a
        # new goal, same as goal 2.
        self._add_goal_row_widget(text=text, goal_id=self._single_goal_id)
        self._add_goal_row_widget()
        self.name_row.set_text("")

        if self._editing_id is not None:
            description = _edit_goals_description()
        elif text:
            description = _("“%(text)s” moved from the name field to goal 1.") % {"text": text}
        else:
            description = ""
        self.goals_group.set_description(description)

        self._set_multi(True)
        self.name_row.grab_focus()

    def _collapse_to_single(self, row: StreaksGoalEditRow) -> None:
        text = row.entry.get_text()
        self._single_goal_id = row.goal_id
        self._clear_goal_rows()
        self.name_row.set_text(text)
        self._set_multi(False)

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
        through it. Returns ``False`` (no-op) if ``source_row`` isn't one of this dialog's goal
        rows or ``target_index`` is already where it is/out of range.
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
        self._update_goals()
        return True

    def _on_add_goal_activated(self, *_args) -> None:
        row = self._add_goal_row_widget()
        row.entry.grab_focus()

    def _on_goal_entry_activate(self, _entry: Gtk.Entry, row: StreaksGoalEditRow) -> None:
        if row is self._goal_rows[-1]:
            new_row = self._add_goal_row_widget()
            new_row.entry.grab_focus()

    def _on_remove_goal_clicked(self, _button: Gtk.Button, row: StreaksGoalEditRow) -> None:
        # Two goals is the multi-mode floor: removing one collapses back to single mode instead
        # of leaving a lone goal row around.
        if len(self._goal_rows) == 2:
            other = next(r for r in self._goal_rows if r is not row)
            self._collapse_to_single(other)
            return
        self._goal_rows.remove(row)
        self.goals_list.remove(row)
        self._update_goals()

    def _update_goals(self) -> None:
        for i, row in enumerate(self._goal_rows):
            row.remove_button.set_visible(True)
            row.entry.set_placeholder_text(_("Goal %(n)d") % {"n": i + 1})
        self._update_save_sensitive()

    def _goal_entries(self) -> list[tuple[int, str]]:
        return [(row.goal_id, row.entry.get_text()) for row in self._goal_rows]

    # -- save/cancel ---------------------------------------------------------------------

    def _on_field_changed(self, *_args) -> None:
        self._update_save_sensitive()

    def _update_save_sensitive(self) -> None:
        name_ok = bool(self.name_row.get_text().strip())
        if self._multi:
            goal_count = sum(1 for _gid, text in self._goal_entries() if text.strip())
            self.save_button.set_sensitive(name_ok and goal_count >= 2)
        else:
            self.save_button.set_sensitive(name_ok)

    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        self.close()

    def _on_delete_row_activated(self, *_args) -> None:
        self.activate_action("win.delete-streak", GLib.Variant.new_int32(self._editing_id))
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
            goal_names = [text for _gid, text in self._goal_entries()] if self._multi else [name]
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
            goals = (
                [(gid or None, text) for gid, text in self._goal_entries()]
                if self._multi
                else [(self._single_goal_id or None, name)]
            )
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

        self.state.selection = streak.id
        self.state.reload()
        self.close()
