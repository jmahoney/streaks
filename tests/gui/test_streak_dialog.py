"""Tests for the New/Edit streak dialog (design-spec §6)."""

from datetime import time

from helpers import listbox_rows

from streaks.engine import Settings, evaluate
from streaks.models import Goal, GoalCheck, Streak, load_streak_data
from streaks.streak_dialog import StreaksStreakDialog

_EDIT_GOALS_DESCRIPTION = (
    "New goals apply from the current period. Earlier periods keep their recorded shade."
)


def _goal_rows(dialog):
    """`dialog`'s goal rows, excluding the trailing add-goal row."""
    return [row for row in listbox_rows(dialog.goals_list) if row is not dialog.add_goal_row]


def _new_dialog(state, window):
    dialog = StreaksStreakDialog.for_new()
    dialog.set_state(state)
    dialog.present(window)
    return dialog


def _edit_dialog(state, window, name):
    streak_data = next(s for s in state.streaks if s.name == name)
    dialog = StreaksStreakDialog.for_edit(streak_data)
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

    assert dialog.name_row.get_title() == "Name"
    assert not dialog.goals_group.get_visible()
    assert dialog.more_goals_button.get_visible()
    assert dialog.more_goals_hint.get_visible()
    assert not dialog.delete_group.get_visible()


def test_single_save_creates_one_goal_named_after_streak(fresh_state, fresh_window, process_events):
    window = fresh_window

    dialog = _new_dialog(fresh_state, window)
    process_events()

    dialog.name_row.set_text("Floss")
    process_events()
    assert dialog.save_button.get_sensitive()

    dialog.save_button.emit("clicked")
    process_events()

    streak = Streak.get(Streak.name == "Floss")
    goals = list(Goal.select().where(Goal.streak == streak))
    assert [g.name for g in goals] == ["Floss"]
    assert fresh_state.selection == streak.id


def test_whitespace_name_keeps_save_insensitive(fresh_state, fresh_window, process_events):
    window = fresh_window

    dialog = _new_dialog(fresh_state, window)
    process_events()

    dialog.name_row.set_text("   ")
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


def test_expand_moves_name_into_goal_1(fresh_state, fresh_window, process_events):
    window = fresh_window

    dialog = _new_dialog(fresh_state, window)
    process_events()

    dialog.name_row.set_text("Floss")
    process_events()
    dialog.more_goals_button.emit("clicked")
    process_events()

    rows = _goal_rows(dialog)
    assert [r.entry.get_text() for r in rows] == ["Floss", ""]
    assert rows[1].entry.get_placeholder_text() == "Goal 2"
    assert dialog.name_row.get_text() == ""
    assert dialog.name_row.get_title() == "Streak name"
    assert not dialog.more_goals_button.get_visible()
    assert dialog.goals_group.get_description() == "“Floss” moved from the name field to goal 1."


def test_expand_with_empty_name(fresh_state, fresh_window, process_events):
    window = fresh_window

    dialog = _new_dialog(fresh_state, window)
    process_events()

    dialog.more_goals_button.emit("clicked")
    process_events()

    rows = _goal_rows(dialog)
    assert [r.entry.get_text() for r in rows] == ["", ""]
    assert dialog.goals_group.get_description() == ""


def test_multi_save_needs_name_and_two_goals(fresh_state, fresh_window, process_events):
    window = fresh_window

    dialog = _new_dialog(fresh_state, window)
    process_events()

    dialog.more_goals_button.emit("clicked")
    process_events()
    rows = _goal_rows(dialog)

    dialog.name_row.set_text("75 Hard")
    rows[0].entry.set_text("Take a photo")
    process_events()
    assert not dialog.save_button.get_sensitive()

    dialog.name_row.set_text("")
    rows[1].entry.set_text("Read pages")
    process_events()
    assert not dialog.save_button.get_sensitive()

    dialog.name_row.set_text("75 Hard")
    process_events()
    assert dialog.save_button.get_sensitive()

    dialog.save_button.emit("clicked")
    process_events()

    streak = Streak.get(Streak.name == "75 Hard")
    goals = list(Goal.select().where(Goal.streak == streak).order_by(Goal.position))
    assert [g.name for g in goals] == ["Take a photo", "Read pages"]


def test_collapse_on_remove(fresh_state, fresh_window, process_events):
    window = fresh_window

    dialog = _new_dialog(fresh_state, window)
    process_events()

    dialog.name_row.set_text("Floss")
    dialog.more_goals_button.emit("clicked")
    process_events()
    rows = _goal_rows(dialog)
    rows[1].entry.set_text("Floss goal 2")
    dialog.name_row.set_text("Ignored streak name")
    process_events()

    rows[1].remove_button.emit("clicked")
    process_events()

    assert not dialog._multi
    assert dialog.name_row.get_text() == "Floss"
    assert dialog.name_row.get_title() == "Name"
    assert not dialog.goals_group.get_visible()

    # Removing goal 1 instead leaves goal 2's text in name_row.
    dialog.more_goals_button.emit("clicked")
    process_events()
    rows = _goal_rows(dialog)
    rows[1].entry.set_text("Goal two text")
    process_events()

    rows[0].remove_button.emit("clicked")
    process_events()

    assert not dialog._multi
    assert dialog.name_row.get_text() == "Goal two text"


def test_collapse_then_expand_round_trips(fresh_state, fresh_window, process_events):
    window = fresh_window

    dialog = _new_dialog(fresh_state, window)
    process_events()

    dialog.name_row.set_text("Floss")
    dialog.more_goals_button.emit("clicked")
    process_events()
    rows = _goal_rows(dialog)
    rows[1].entry.set_text("Floss goal 2")
    process_events()

    rows[1].remove_button.emit("clicked")
    process_events()
    assert not dialog._multi

    dialog.more_goals_button.emit("clicked")
    process_events()
    rows = _goal_rows(dialog)
    assert len(rows) == 2
    assert [r.entry.get_text() for r in rows] == ["Floss", ""]


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

    dialog._expand_to_multi()
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


def test_edit_single_prefill(seeded_state, seeded_window, process_events):
    window = seeded_window

    dialog = _edit_dialog(seeded_state, window, "Clip fingernails")
    process_events()

    assert dialog.get_title() == "Edit Streak"
    assert dialog.save_button.get_label() == "Save"
    assert not dialog._multi
    assert dialog.name_row.get_text() == "Clip fingernails"
    assert dialog.name_row.get_title() == "Name"
    assert dialog.period_toggle.get_active_name() == "monthly"
    assert dialog.swatch_2.get_active()
    assert dialog.delete_group.get_visible()
    assert not dialog.more_goals_hint.get_visible()


def test_edit_single_to_multi_keeps_goal_id(seeded_state, seeded_window, process_events):
    window = seeded_window

    streak_data = next(s for s in seeded_state.streaks if s.name == "Clip fingernails")
    original_goal_id = next(g.id for g in streak_data.goals if g.removed_on is None)
    today = seeded_state.today()
    results_before = {
        (pr.period.start.year, pr.period.start.month): pr
        for pr in evaluate(streak_data, today, Settings())
    }

    dialog = StreaksStreakDialog.for_edit(streak_data)
    dialog.set_state(seeded_state)
    dialog.present(window)
    process_events()

    dialog.more_goals_button.emit("clicked")
    process_events()

    assert dialog.goals_group.get_description() == _EDIT_GOALS_DESCRIPTION

    rows = _goal_rows(dialog)
    assert rows[0].goal_id == original_goal_id
    rows[1].entry.set_text("Haircut")
    dialog.name_row.set_text("Grooming")
    process_events()

    dialog.save_button.emit("clicked")
    process_events()

    original_goal = Goal.get_by_id(original_goal_id)
    assert original_goal.name == "Clip fingernails"
    assert original_goal.removed_on is None
    assert GoalCheck.select().where(GoalCheck.goal == original_goal).count() == 3

    new_goal = Goal.get(Goal.name == "Haircut")
    assert new_goal.streak_id == original_goal.streak_id

    streak = Streak.get_by_id(original_goal.streak_id)
    assert streak.name == "Grooming"

    # Adding "Haircut" grows the goal count from September on but must not retroactively
    # change June-August, which were already recorded against the one goal.
    results_after = {
        (pr.period.start.year, pr.period.start.month): pr
        for pr in evaluate(load_streak_data(streak), today, Settings())
    }
    for month in (6, 7, 8):
        assert results_after[(2026, month)] == results_before[(2026, month)]


def test_edit_collapse_keeps_surviving_goal(seeded_state, seeded_window, process_events):
    window = seeded_window

    streak_data = next(s for s in seeded_state.streaks if s.name == "Gym, three times a week")
    session_goal_id = next(g.id for g in streak_data.goals if g.name == "45 min session")
    weights_goal_id = next(g.id for g in streak_data.goals if g.name == "Log the weights")

    dialog = StreaksStreakDialog.for_edit(streak_data)
    dialog.set_state(seeded_state)
    dialog.present(window)
    process_events()

    rows = _goal_rows(dialog)
    weights_row = next(r for r in rows if r.entry.get_text() == "Log the weights")
    weights_row.remove_button.emit("clicked")
    process_events()

    assert not dialog._multi
    assert dialog.name_row.get_text() == "45 min session"

    dialog.save_button.emit("clicked")
    process_events()

    streak = Streak.get_by_id(streak_data.id)
    assert streak.name == "45 min session"
    assert Goal.get_by_id(session_goal_id).removed_on is None
    assert Goal.get_by_id(weights_goal_id).removed_on == seeded_state.today()


def test_edit_multi_prefill(seeded_state, seeded_window, process_events):
    window = seeded_window

    dialog = _edit_dialog(seeded_state, window, "75 Hard")
    process_events()

    assert dialog._multi
    assert dialog.name_row.get_title() == "Streak name"
    rows = _goal_rows(dialog)
    assert len(rows) == 5
    assert dialog.goals_group.get_description() == _EDIT_GOALS_DESCRIPTION


def test_delete_row_opens_confirmation(seeded_state, seeded_window, process_events):
    window = seeded_window

    dialog = _edit_dialog(seeded_state, window, "Clip fingernails")
    process_events()

    dialog.delete_row.emit("activated")
    process_events()

    assert window.delete_streak_dialog is not None


def test_reorder_goal_row_via_drop_handler(fresh_state, fresh_window, process_events):
    """Dropping a goal row reorders the list. Drives ``_reorder_goal_row`` directly with
    (row, index), the same entry point the drop handler uses."""
    window = fresh_window

    dialog = _new_dialog(fresh_state, window)
    process_events()
    dialog._expand_to_multi()
    process_events()

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
    dialog._expand_to_multi()
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
    dialog._expand_to_multi()
    process_events()

    dialog.name_row.set_text("Order test")
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
    process_events()

    dialog.cancel_button.emit("clicked")
    process_events()

    assert Streak.select().count() == 0
