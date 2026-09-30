"""Tests for the catch-up dialog, against the seeded "75 Hard" streak.

The unconfirmed days are Wed 9 - Sat 12 September 2026; the fixture's fake "today" is Sunday 13
September 2026 (``tests/fixtures/seed.py::FIXTURE_TODAY``). Every string/number asserted here is
cross-checked against ``engine.catch_up``/``catch_up_preview``.
"""

import json
from datetime import date

from helpers import catchup_goal_rows, catchup_rows, sidebar_rows

from streaks import engine
from streaks.catchup_dialog import StreaksCatchupDialog
from streaks.engine import Answer
from streaks.models import DayAnswer, Goal, Streak

WED, THU, FRI, SAT = date(2026, 9, 9), date(2026, 9, 10), date(2026, 9, 11), date(2026, 9, 12)


def _hard_streak_data(state):
    return next(s for s in state.streaks if s.name == "75 Hard")


def _goal_ids(state):
    streak_data = _hard_streak_data(state)
    return [g.id for g in sorted(streak_data.goals, key=lambda g: g.position)]


def _open_dialog(state, window):
    streak_data = _hard_streak_data(state)
    dialog = StreaksCatchupDialog(state, streak_data.id)
    dialog.present(window)
    return dialog


def _row_by_day(dialog, day):
    return next(r for r in catchup_rows(dialog) if r.day == day)


def _tick(row, index, active):
    catchup_goal_rows(row)[index][1].check.set_active(active)


def _settings(state):
    return state.settings.to_engine()


def test_initial_state(seeded_state, seeded_window, process_events):
    window = seeded_window

    dialog = _open_dialog(seeded_state, window)
    process_events()

    assert dialog.dialog_title.get_subtitle() == "75 Hard · 4 days"
    assert dialog.intro_label.get_label() == (
        "Unticked goals on a day with any ticks are recorded as missed. Days with no ticks "
        "stay unconfirmed."
    )

    rows = catchup_rows(dialog)
    assert [r.day for r in rows] == [WED, THU, FRI, SAT]
    expected_dates = [
        "Wednesday 9 September",
        "Thursday 10 September",
        "Friday 11 September",
        "Saturday 12 September",
    ]
    for row, expected in zip(rows, expected_dates, strict=True):
        assert row.date_label.get_label() == expected
        assert row.state_label.get_label() == "Unconfirmed"
        goal_rows = catchup_goal_rows(row)
        assert len(goal_rows) == 5
        assert all(not goal_row.check.get_active() for _gid, goal_row in goal_rows)
        assert "missed" not in row.get_css_classes()
        assert row.action_button.get_visible()
        assert row.action_button.get_label() == "Mark missed"

    assert not dialog.save_button.get_sensitive()

    cells = dialog.result_strip.cells
    assert len(cells) == 24
    bordered = [i for i, c in enumerate(cells) if c.border is not None]
    assert len(bordered) == 4

    expected_preview = engine.catch_up_preview(
        _hard_streak_data(seeded_state), seeded_state.today(), _settings(seeded_state), {}
    )
    assert dialog.result_label.get_label() == expected_preview.summary
    assert dialog.result_label.get_label() == "Run 3 continues at 51 days. 4 days unconfirmed."
    assert "dim-label" in dialog.result_label.get_css_classes()
    assert "error" not in dialog.result_label.get_css_classes()


def test_ticking_all_goals_keeps_the_day(seeded_state, seeded_window, process_events):
    window = seeded_window

    dialog = _open_dialog(seeded_state, window)
    process_events()

    wed_row = _row_by_day(dialog, WED)
    for i in range(5):
        _tick(wed_row, i, True)
    process_events()

    assert wed_row.current_answer() == (Answer.KEPT, ())
    assert wed_row.state_label.get_label() == "All 5 kept"
    assert "missed" not in wed_row.get_css_classes()
    assert not wed_row.action_button.get_visible()
    assert dialog.save_button.get_sensitive()

    # Every goal row is ticked (dimmed), and none is flagged missed on a fully-kept day.
    for _gid, row in catchup_goal_rows(wed_row):
        assert "ticked" in row.get_css_classes()
        assert "missed" not in row.get_css_classes()

    expected_preview = engine.catch_up_preview(
        _hard_streak_data(seeded_state),
        seeded_state.today(),
        _settings(seeded_state),
        {WED: (Answer.KEPT, ())},
    )
    assert [(c.fill, c.border) for c in dialog.result_strip.cells] == [
        (c.fill, c.border) for c in expected_preview.strip
    ]
    # The strip ends at today; Wednesday is 5th-from-last. "Kept" renders it as a full day.
    assert dialog.result_strip.cells[-5].fill == engine.CHART_FULL
    assert dialog.result_strip.cells[-5].border is None


def test_ticking_some_goals_records_the_rest_missed(seeded_state, seeded_window, process_events):
    window = seeded_window

    dialog = _open_dialog(seeded_state, window)
    process_events()

    goal_ids = _goal_ids(seeded_state)
    goal2_id = goal_ids[2]
    goal = Goal.get_by_id(goal2_id)
    assert goal.name == "45 min second workout"

    fri_row = _row_by_day(dialog, FRI)
    for i in range(5):
        if i != 2:
            _tick(fri_row, i, True)
    process_events()

    assert fri_row.current_answer() == (Answer.MISSED, (goal2_id,))
    assert "missed" in fri_row.get_css_classes()
    assert fri_row.state_label.get_label() == "4 of 5 kept · 1 missed"
    assert not fri_row.action_button.get_visible()
    assert dialog.save_button.get_sensitive()

    # The unticked goal row is flagged missed (and dropped from ticked); the ticked ones are
    # flagged ticked (and not missed).
    for i, (gid, row) in enumerate(catchup_goal_rows(fri_row)):
        if i == 2:
            assert gid == goal2_id
            assert not row.check.get_active()
            assert "missed" in row.get_css_classes()
            assert "ticked" not in row.get_css_classes()
        else:
            assert row.check.get_active()
            assert "ticked" in row.get_css_classes()
            assert "missed" not in row.get_css_classes()


def test_goal_row_click_path_toggles_the_check_exactly_once(
    seeded_state, seeded_window, process_events
):
    """The checkbutton fills its (non-activatable) row, so a real click only has one path to
    toggle it: the checkbutton's own click/keyboard "activate" signal. `row.activate()` -- the
    other path a double-toggle bug would go through -- must be a no-op."""
    window = seeded_window

    dialog = _open_dialog(seeded_state, window)
    process_events()

    wed_row = _row_by_day(dialog, WED)
    _gid, row = catchup_goal_rows(wed_row)[0]
    check = row.check
    assert row.get_activatable() is False
    assert row.get_focusable() is False

    toggles = []
    check.connect("toggled", lambda c: toggles.append(c.get_active()))

    row.activate()
    process_events()
    assert not check.get_active()
    assert toggles == []

    check.emit("activate")
    process_events()
    assert check.get_active() is True
    assert toggles == [True]


def test_mark_missed_link_answers_missed_with_no_ticks(seeded_state, seeded_window, process_events):
    window = seeded_window

    dialog = _open_dialog(seeded_state, window)
    process_events()

    fri_row = _row_by_day(dialog, FRI)
    assert fri_row.action_button.get_label() == "Mark missed"
    fri_row.action_button.emit("clicked")
    process_events()

    assert fri_row.current_answer() == (Answer.MISSED, ())
    assert "missed" in fri_row.get_css_classes()
    assert fri_row.state_label.get_label() == "Missed"
    assert fri_row.action_button.get_label() == "Undo"
    assert fri_row.action_button.get_visible()
    assert dialog.save_button.get_sensitive()


def test_undo_reverts_marked_missed_to_unconfirmed(seeded_state, seeded_window, process_events):
    window = seeded_window

    dialog = _open_dialog(seeded_state, window)
    process_events()

    fri_row = _row_by_day(dialog, FRI)
    fri_row.action_button.emit("clicked")
    process_events()
    assert fri_row.current_answer() == (Answer.MISSED, ())

    fri_row.action_button.emit("clicked")
    process_events()

    assert fri_row.current_answer() is None
    assert fri_row.state_label.get_label() == "Unconfirmed"
    assert "missed" not in fri_row.get_css_classes()
    assert fri_row.action_button.get_label() == "Mark missed"
    assert not dialog.save_button.get_sensitive()


def test_ticking_a_goal_after_mark_missed_clears_the_mark(
    seeded_state, seeded_window, process_events
):
    window = seeded_window

    dialog = _open_dialog(seeded_state, window)
    process_events()

    fri_row = _row_by_day(dialog, FRI)
    fri_row.action_button.emit("clicked")
    process_events()
    assert fri_row.current_answer() == (Answer.MISSED, ())

    _tick(fri_row, 0, True)
    process_events()

    # One goal ticked, marked-missed cleared: this is now a partial day (1 of 5 kept), not the
    # explicit all-missed answer.
    assert fri_row.current_answer() == (
        Answer.MISSED,
        tuple(gid for gid, _ in catchup_goal_rows(fri_row)[1:]),
    )
    assert fri_row.state_label.get_label() == "1 of 5 kept · 4 missed"
    assert fri_row.action_button.get_visible() is False


def test_combined_answers_summary_matches_engine(seeded_state, seeded_window, process_events):
    window = seeded_window

    dialog = _open_dialog(seeded_state, window)
    process_events()

    goal_ids = _goal_ids(seeded_state)
    goal2_id = goal_ids[2]

    wed_row = _row_by_day(dialog, WED)
    for i in range(5):
        _tick(wed_row, i, True)
    fri_row = _row_by_day(dialog, FRI)
    for i in range(5):
        if i != 2:
            _tick(fri_row, i, True)
    sat_row = _row_by_day(dialog, SAT)
    for i in range(5):
        _tick(sat_row, i, True)
    process_events()

    expected_preview = engine.catch_up_preview(
        _hard_streak_data(seeded_state),
        seeded_state.today(),
        _settings(seeded_state),
        {
            WED: (Answer.KEPT, ()),
            FRI: (Answer.MISSED, (goal2_id,)),
            SAT: (Answer.KEPT, ()),
        },
    )
    assert dialog.result_label.get_label() == expected_preview.summary
    assert dialog.result_label.get_label() == (
        "Run 3 ends on 11 September at 48 days. Run 4 starts on 12 September at 2 days. "
        "1 day unconfirmed."
    )
    assert "error" in dialog.result_label.get_css_classes()
    assert "dim-label" not in dialog.result_label.get_css_classes()
    assert dialog.save_button.get_sensitive()


def test_clicking_all_ticks_off_again_reverts_to_unconfirmed(
    seeded_state, seeded_window, process_events
):
    window = seeded_window

    dialog = _open_dialog(seeded_state, window)
    process_events()

    wed_row = _row_by_day(dialog, WED)
    for i in range(5):
        _tick(wed_row, i, True)
    process_events()
    assert wed_row.state_label.get_label() == "All 5 kept"

    for i in range(5):
        _tick(wed_row, i, False)
    process_events()

    assert wed_row.state_label.get_label() == "Unconfirmed"
    assert wed_row.current_answer() is None
    assert not dialog.save_button.get_sensitive()


def test_save_writes_answers_and_refreshes_the_app(seeded_state, seeded_window, process_events):
    window = seeded_window

    dialog = _open_dialog(seeded_state, window)
    process_events()

    goal_ids = _goal_ids(seeded_state)
    goal2_id = goal_ids[2]

    wed_row = _row_by_day(dialog, WED)
    for i in range(5):
        _tick(wed_row, i, True)
    fri_row = _row_by_day(dialog, FRI)
    for i in range(5):
        if i != 2:
            _tick(fri_row, i, True)
    sat_row = _row_by_day(dialog, SAT)
    for i in range(5):
        _tick(sat_row, i, True)
    process_events()

    assert dialog.save_button.get_sensitive()

    closed = []
    dialog.connect("closed", lambda _d: closed.append(True))
    dialog.save_button.emit("clicked")
    process_events()

    assert closed == [True]

    streak = Streak.get(Streak.name == "75 Hard")
    answers = {
        a.day: a
        for a in DayAnswer.select().where(
            DayAnswer.streak == streak, DayAnswer.day.in_([WED, THU, FRI, SAT])
        )
    }
    assert set(answers) == {WED, FRI, SAT}
    assert answers[WED].status == "kept"
    assert answers[SAT].status == "kept"
    assert answers[FRI].status == "missed"
    assert json.loads(answers[FRI].missed_goal_ids) == [goal2_id]

    today = seeded_state.today()
    settings = seeded_state.settings.to_engine()
    streak_data = next(s for s in seeded_state.streaks if s.name == "75 Hard")
    runs = engine.runs(streak_data, today, settings)
    assert [r.length for r in runs] == [28, 34, 48, 2]

    hard_row = next(r for r in sidebar_rows(window) if r.name_label.get_label() == "75 Hard")
    assert hard_row.count_label.get_label() == "2"

    # Thursday's unconfirmed day now belongs to the closed run 3; `today_view()` banners only
    # cover the open run, so no banner reappears.
    tv = engine.today_view(seeded_state.streaks, today, settings)
    assert [b for b in tv.banners if b.streak_id == streak.id] == []


def test_cancel_writes_nothing(seeded_state, seeded_window, process_events):
    window = seeded_window

    before = DayAnswer.select().count()

    dialog = _open_dialog(seeded_state, window)
    process_events()

    wed_row = _row_by_day(dialog, WED)
    for i in range(5):
        _tick(wed_row, i, True)
    process_events()

    closed = []
    dialog.connect("closed", lambda _d: closed.append(True))
    dialog.cancel_button.emit("clicked")
    process_events()

    assert closed == [True]
    assert DayAnswer.select().count() == before
    assert DayAnswer.get_or_none(DayAnswer.day == WED) is None


def test_open_from_today_banner(seeded_state, seeded_window, process_events):
    window = seeded_window

    today_view = window.today_view
    banner = today_view.banners_box.get_first_child()
    assert banner is not None
    assert banner.streak_id == _hard_streak_data(seeded_state).id

    banner.catch_up_button.emit("clicked")
    process_events()

    assert window.catchup_dialog is not None
    assert window.catchup_dialog.dialog_title.get_subtitle() == "75 Hard · 4 days"


def test_open_from_streak_view_link(seeded_state, seeded_window, process_events):
    window = seeded_window

    streak = Streak.get(Streak.name == "75 Hard")
    hard_data = _hard_streak_data(seeded_state)
    window.streak_view.set_state(seeded_state)
    window.streak_view.configure(hard_data)
    process_events()

    assert window.streak_view.catch_up_link.get_visible()
    window.streak_view.catch_up_link.emit("clicked")
    process_events()

    assert window.catchup_dialog is not None
    assert window.catchup_dialog.dialog_title.get_subtitle() == "75 Hard · 4 days"
    assert window.catchup_dialog.streak_id == streak.id
