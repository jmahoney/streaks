"""Tests for the New/Edit streak dialog (design-spec §6)."""

from datetime import date, time

from helpers import listbox_rows

from streaks import engine
from streaks.models import Goal, Streak, load_streak_data
from streaks.streak_dialog import StreaksStreakDialog


def _goal_rows(dialog):
    """`dialog`'s goal rows, excluding the trailing add-goal row."""
    return [row for row in listbox_rows(dialog.goals_list) if row is not dialog.add_goal_row]


def _new_dialog(state, window):
    dialog = StreaksStreakDialog.for_new()
    dialog.set_state(state)
    dialog.present(window)
    return dialog


def test_for_new_defaults(fresh_state, fresh_window, process_events):
    window = fresh_window

    dialog = _new_dialog(fresh_state, window)
    process_events()

    assert dialog.get_title() == "New Streak"
    assert dialog.save_button.get_label() == "Create"
    assert not dialog.save_button.get_sensitive()
    assert dialog.period_toggle.get_active_name() == "daily"
    assert not dialog.weekday_box.get_sensitive()
    assert not dialog.times_row.get_visible()
    assert dialog.reminder_label.get_label() == "Off ›"

    rows = _goal_rows(dialog)
    assert len(rows) == 1
    assert not rows[0].remove_button.get_visible()
    assert dialog.goals_group.get_title() == "Goals — 1"


def test_save_sensitivity_tracks_name_and_goal(fresh_state, fresh_window, process_events):
    window = fresh_window

    dialog = _new_dialog(fresh_state, window)
    process_events()

    dialog.name_row.set_text("75 Hard")
    process_events()
    assert not dialog.save_button.get_sensitive()

    row = _goal_rows(dialog)[0]
    row.entry.set_text("Take a photo")
    process_events()
    assert dialog.save_button.get_sensitive()

    row.entry.set_text("   ")
    process_events()
    assert not dialog.save_button.get_sensitive()


def test_period_switching(fresh_state, fresh_window, process_events):
    window = fresh_window

    dialog = _new_dialog(fresh_state, window)
    process_events()

    dialog.period_toggle.set_active_name("weekdays")
    process_events()
    assert dialog.weekday_box.get_sensitive()
    assert [b.get_active() for b in dialog._weekday_buttons] == [
        True,
        True,
        True,
        True,
        True,
        False,
        False,
    ]
    assert not dialog.times_row.get_visible()

    dialog.period_toggle.set_active_name("n_per_week")
    process_events()
    assert not dialog.weekday_box.get_sensitive()
    assert dialog.times_row.get_visible()

    dialog.period_toggle.set_active_name("monthly")
    process_events()
    assert not dialog.weekday_box.get_sensitive()
    assert not dialog.times_row.get_visible()


def test_add_and_remove_goal_rows(fresh_state, fresh_window, process_events):
    window = fresh_window

    dialog = _new_dialog(fresh_state, window)
    process_events()

    dialog.add_goal_row.emit("activated")
    process_events()
    rows = _goal_rows(dialog)
    assert len(rows) == 2
    assert dialog.goals_group.get_title() == "Goals — 2"
    assert all(r.remove_button.get_visible() for r in rows)

    rows[1].remove_button.emit("clicked")
    process_events()
    rows = _goal_rows(dialog)
    assert len(rows) == 1
    assert dialog.goals_group.get_title() == "Goals — 1"
    assert not rows[0].remove_button.get_visible()


def test_reminder_popover_sets_label(fresh_state, fresh_window, process_events):
    window = fresh_window

    dialog = _new_dialog(fresh_state, window)
    process_events()

    dialog.reminder_row.emit("activated")
    process_events()

    dialog.reminder_switch.set_active(True)
    dialog.hour_spin.set_value(20)
    dialog.minute_spin.set_value(0)
    process_events()

    assert dialog.reminder_label.get_label() == "20:00 ›"


def test_save_new_streak(fresh_state, fresh_window, process_events):
    window = fresh_window

    dialog = _new_dialog(fresh_state, window)
    process_events()

    dialog.name_row.set_text("75 Hard")
    dialog.swatch_4.set_active(True)
    dialog.period_toggle.set_active_name("weekdays")
    process_events()
    for i, active in enumerate([True, False, True, False, True, False, False]):
        dialog._weekday_buttons[i].set_active(active)
    dialog.skip_row.set_active(True)
    dialog.reminder_switch.set_active(True)
    dialog.hour_spin.set_value(20)
    dialog.minute_spin.set_value(0)

    rows = _goal_rows(dialog)
    rows[0].entry.set_text("A")
    dialog.add_goal_row.emit("activated")
    process_events()
    rows = _goal_rows(dialog)
    rows[1].entry.set_text("B")
    process_events()

    assert dialog.save_button.get_sensitive()
    dialog.save_button.emit("clicked")
    process_events()

    streak = Streak.get(Streak.name == "75 Hard")
    assert streak.colour == "#9141ac"
    assert streak.weekdays_mask == 0b0010101
    assert streak.reminder_time == time(20, 0)
    assert streak.allow_skip

    goals = list(Goal.select().where(Goal.streak == streak).order_by(Goal.position))
    assert [g.name for g in goals] == ["A", "B"]
    assert [g.position for g in goals] == [0, 1]

    assert fresh_state.selection == streak.id

    selected_row = window.sidebar_list.get_selected_row()
    assert selected_row is not None
    assert selected_row.streak_id == streak.id
    assert selected_row.name_label.get_label() == "75 Hard"


def test_for_edit_prefill_and_reconcile_goals(seeded_state, seeded_window, process_events):
    window = seeded_window

    streak_data = next(s for s in seeded_state.streaks if s.name == "75 Hard")
    dialog = StreaksStreakDialog.for_edit(streak_data)
    dialog.set_state(seeded_state)
    dialog.present(window)
    process_events()

    assert dialog.get_title() == "Edit Streak"
    assert dialog.save_button.get_label() == "Save"
    assert dialog.name_row.get_text() == "75 Hard"
    assert dialog.swatch_0.get_active()
    assert dialog.period_toggle.get_active_name() == "daily"
    assert dialog.reminder_label.get_label() == "Off ›"

    rows = _goal_rows(dialog)
    assert [r.entry.get_text() for r in rows] == [
        "Progress photo",
        "45 min outdoors",
        "45 min second workout",
        "Read 10 pages",
        "Stick to the diet",
    ]

    goal_2_id = rows[1].goal_id
    goal_4_id = rows[3].goal_id
    rows[1].entry.set_text("45 min outdoors (renamed)")
    rows[3].remove_button.emit("clicked")
    process_events()

    dialog.add_goal_row.emit("activated")
    process_events()
    rows = _goal_rows(dialog)
    rows[-1].entry.set_text("New goal")
    process_events()

    dialog.save_button.emit("clicked")
    process_events()

    goal_2 = Goal.get_by_id(goal_2_id)
    assert goal_2.name == "45 min outdoors (renamed)"

    goal_4 = Goal.get_by_id(goal_4_id)
    assert goal_4.removed_on == date(2026, 9, 13)

    new_goal = Goal.get(Goal.name == "New goal")
    assert new_goal.position == 4

    streak = Streak.get(Streak.name == "75 Hard")
    updated_data = load_streak_data(streak)
    hist_runs = engine.runs(updated_data, date(2026, 9, 13), seeded_state.settings.to_engine())
    assert len(hist_runs) == 3
    assert hist_runs[-1].length == 51


def test_reorder_goal_row_via_drop_handler(fresh_state, fresh_window, process_events):
    """Dropping a goal row reorders the list. Drives ``_reorder_goal_row`` directly with
    (row, index), the same entry point the drop handler uses."""
    window = fresh_window

    dialog = _new_dialog(fresh_state, window)
    process_events()

    for _text in ("B", "C"):
        dialog.add_goal_row.emit("activated")
        process_events()
    rows = _goal_rows(dialog)
    for row, text in zip(rows, ("A", "B", "C"), strict=True):
        row.entry.set_text(text)
    process_events()

    # Move the first row ("A") to the end.
    moved = dialog._reorder_goal_row(rows[0], 2)
    process_events()
    assert moved is True
    assert [r.entry.get_text() for r in _goal_rows(dialog)] == ["B", "C", "A"]

    # A no-op move returns False and leaves the order unchanged.
    assert dialog._reorder_goal_row(rows[0], 2) is False
    assert [r.entry.get_text() for r in _goal_rows(dialog)] == ["B", "C", "A"]

    # Out-of-range indices clamp to the last position.
    moved = dialog._reorder_goal_row(rows[1], 99)  # rows[1] == "B", currently first
    process_events()
    assert moved is True
    assert [r.entry.get_text() for r in _goal_rows(dialog)] == ["C", "A", "B"]


def test_reorder_goal_row_keyboard_fallback(fresh_state, fresh_window, process_events):
    """The ``row.move-up``/``row.move-down`` actions (bound to Alt+Up/Alt+Down while a goal
    entry is focused) reorder rows the same way dragging does."""
    window = fresh_window

    dialog = _new_dialog(fresh_state, window)
    process_events()

    dialog.add_goal_row.emit("activated")
    process_events()
    rows = _goal_rows(dialog)
    for row, text in zip(rows, ("A", "B"), strict=True):
        row.entry.set_text(text)
    process_events()

    rows[1].activate_action("row.move-up")
    process_events()
    assert [r.entry.get_text() for r in _goal_rows(dialog)] == ["B", "A"]

    rows[1].activate_action("row.move-down")
    process_events()
    assert [r.entry.get_text() for r in _goal_rows(dialog)] == ["A", "B"]

    # A no-op move returns False and leaves the order unchanged.
    rows[0].activate_action("row.move-up")
    process_events()
    assert [r.entry.get_text() for r in _goal_rows(dialog)] == ["A", "B"]


def test_reorder_goal_row_persists_positions_on_save(fresh_state, fresh_window, process_events):
    """Reordering before Save persists the new order as goal positions."""
    window = fresh_window

    dialog = _new_dialog(fresh_state, window)
    process_events()

    dialog.name_row.set_text("Order test")
    dialog.add_goal_row.emit("activated")
    process_events()
    rows = _goal_rows(dialog)
    for row, text in zip(rows, ("First", "Second"), strict=True):
        row.entry.set_text(text)
    process_events()

    dialog._reorder_goal_row(rows[0], 1)
    process_events()

    dialog.save_button.emit("clicked")
    process_events()

    streak = Streak.get(Streak.name == "Order test")
    goals = list(Goal.select().where(Goal.streak == streak).order_by(Goal.position))
    assert [g.name for g in goals] == ["Second", "First"]
    assert [g.position for g in goals] == [0, 1]


def test_cancel_writes_nothing(fresh_state, fresh_window, process_events):
    window = fresh_window

    dialog = _new_dialog(fresh_state, window)
    process_events()

    dialog.name_row.set_text("Should not save")
    _goal_rows(dialog)[0].entry.set_text("Goal")
    process_events()

    dialog.cancel_button.emit("clicked")
    process_events()

    assert Streak.select().count() == 0
