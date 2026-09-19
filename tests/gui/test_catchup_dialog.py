"""Tests for the catch-up dialog (design-spec §5), against the seeded "75 Hard" streak.

The unconfirmed days are Wed 9 - Sat 12 September 2026; the fixture's fake "today" is Sunday 13
September 2026 (``tests/gui/screens.py:SEEDED_TODAY``). Every string/number asserted here is
cross-checked against ``engine.catch_up``/``engine.catch_up_preview`` directly, per the phase
brief ("trust the engine for every string and number").
"""

import json
from datetime import date, datetime, time

from streaks import engine
from streaks.catchup_dialog import StreaksCatchupDialog
from streaks.engine import Answer
from streaks.models import DayAnswer, Goal, Streak
from streaks.window import StreaksWindow

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
    return next(r for r in dialog._rows if r.day == day)


def _settings(state):
    return state.settings.to_engine()


def test_initial_state(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    dialog = _open_dialog(seeded_state, window)
    process_events()

    assert dialog.dialog_title.get_subtitle() == "75 Hard · 4 days"
    assert dialog.intro_label.get_label() == (
        "For each day: kept it, missed something, or leave it unanswered. Only "
        "“missed” ends the run."
    )

    assert [r.day for r in dialog._rows] == [WED, THU, FRI, SAT]
    expected_dates = [
        "Wednesday 9 September",
        "Thursday 10 September",
        "Friday 11 September",
        "Saturday 12 September",
    ]
    for row, expected in zip(dialog._rows, expected_dates, strict=True):
        assert row.date_label.get_label() == expected
        assert row.state_label.get_label() == "Unanswered"
        assert not row.kept_button.get_active()
        assert not row.missed_button.get_active()
        assert not row.goals_revealer.get_reveal_child()

    assert not dialog.save_button.get_sensitive()

    cells = dialog.result_strip._cells
    assert len(cells) == 24
    bordered = [i for i, c in enumerate(cells) if c.border is not None]
    assert len(bordered) == 4

    expected_preview = engine.catch_up_preview(
        _hard_streak_data(seeded_state), seeded_state.today(), _settings(seeded_state), {}
    )
    assert dialog.result_label.get_label() == expected_preview.summary
    assert (
        dialog.result_label.get_label()
        == "Run 3 stays at 51 days. Wednesday, Thursday, Friday, Saturday stay hollow — "
        "unanswered, and they don't break anything."
    )

    window.destroy()


def test_kept_on_wednesday(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    dialog = _open_dialog(seeded_state, window)
    process_events()

    wed_row = _row_by_day(dialog, WED)
    wed_row.kept_button.set_active(True)
    process_events()

    assert wed_row.state_label.get_label() == "All five goals"
    assert dialog.save_button.get_sensitive()

    expected_preview = engine.catch_up_preview(
        _hard_streak_data(seeded_state),
        seeded_state.today(),
        _settings(seeded_state),
        {WED: (Answer.KEPT, ())},
    )
    assert [(c.fill, c.border) for c in dialog.result_strip._cells] == [
        (c.fill, c.border) for c in expected_preview.strip
    ]
    # The strip ends at today; Wednesday is 5th-from-last. "Kept" renders it as a full day.
    assert dialog.result_strip._cells[-5].fill == engine.CHART_FULL
    assert dialog.result_strip._cells[-5].border is None

    window.destroy()


def test_missed_on_friday_requires_unticking_a_goal(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    dialog = _open_dialog(seeded_state, window)
    process_events()

    fri_row = _row_by_day(dialog, FRI)
    fri_row.missed_button.set_active(True)
    process_events()

    assert "missed" in fri_row.get_css_classes()
    assert fri_row.goals_revealer.get_reveal_child()
    assert len(fri_row._goal_checks) == 5
    assert all(check.get_active() for _gid, check in fri_row._goal_checks)
    assert fri_row.state_label.get_label() == "Untick the goals you missed"
    assert not dialog.save_button.get_sensitive()

    # Untick "45 min second workout" (goal index 2 for 75 Hard).
    goal_id, check = fri_row._goal_checks[2]
    goal = Goal.get_by_id(goal_id)
    assert goal.name == "45 min second workout"
    check.set_active(False)
    process_events()

    assert fri_row.state_label.get_label() == "Missed — which goals?"
    assert dialog.save_button.get_sensitive()
    assert fri_row.warning_label.get_visible()
    assert fri_row.warning_label.get_label() == (
        "Saving this ends the 48-day run on 11 September and starts run 4 on the 12th."
    )

    window.destroy()


def test_combined_answers_summary_matches_engine_and_brief(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    dialog = _open_dialog(seeded_state, window)
    process_events()

    goal_ids = _goal_ids(seeded_state)
    goal2_id = goal_ids[2]

    _row_by_day(dialog, WED).kept_button.set_active(True)
    fri_row = _row_by_day(dialog, FRI)
    fri_row.missed_button.set_active(True)
    next(check for gid, check in fri_row._goal_checks if gid == goal2_id).set_active(False)
    _row_by_day(dialog, SAT).kept_button.set_active(True)
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
        "Run 3 ends at 48 days — your best run so far. Run 4 is on 2 days. Thursday stays "
        "hollow — unanswered, and it doesn't break anything."
    )
    assert dialog.save_button.get_sensitive()

    window.destroy()


def test_clicking_active_kept_again_reverts_to_unanswered(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    dialog = _open_dialog(seeded_state, window)
    process_events()

    wed_row = _row_by_day(dialog, WED)
    wed_row.kept_button.set_active(True)
    process_events()
    assert wed_row.state_label.get_label() == "All five goals"

    wed_row.kept_button.set_active(False)
    process_events()

    assert wed_row.state_label.get_label() == "Unanswered"
    assert not wed_row.kept_button.get_active()
    assert not dialog.save_button.get_sensitive()

    window.destroy()


def test_save_writes_answers_and_refreshes_the_app(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    dialog = _open_dialog(seeded_state, window)
    process_events()

    goal_ids = _goal_ids(seeded_state)
    goal2_id = goal_ids[2]

    _row_by_day(dialog, WED).kept_button.set_active(True)
    fri_row = _row_by_day(dialog, FRI)
    fri_row.missed_button.set_active(True)
    next(check for gid, check in fri_row._goal_checks if gid == goal2_id).set_active(False)
    _row_by_day(dialog, SAT).kept_button.set_active(True)
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

    hard_row = next(
        r
        for r in _all_sidebar_rows(window)
        if getattr(r, "name_label", None) and r.name_label.get_label() == "75 Hard"
    )
    assert hard_row.count_label.get_label() == "2"

    # NB: per the engine, Thursday's now-orphaned unconfirmed day belongs to run 3, which has
    # since ended -- `engine.today_view()`'s banners only ever look at the *current* (open) run,
    # so no catch-up banner reappears for 75 Hard. See the phase report for this discrepancy
    # against the brief, which expected a "One day without a check-in" banner here.
    tv = engine.today_view(
        seeded_state.streaks, today, datetime.combine(today, time(10, 0)), settings
    )
    assert [b for b in tv.banners if b.streak_id == streak.id] == []

    window.destroy()


def _all_sidebar_rows(window):
    rows = []
    child = window.sidebar_list.get_first_child()
    while child is not None:
        if hasattr(child, "name_label"):
            rows.append(child)
        child = child.get_next_sibling()
    return rows


def test_cancel_writes_nothing(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    before = DayAnswer.select().count()

    dialog = _open_dialog(seeded_state, window)
    process_events()

    _row_by_day(dialog, WED).kept_button.set_active(True)
    process_events()

    closed = []
    dialog.connect("closed", lambda _d: closed.append(True))
    dialog.cancel_button.emit("clicked")
    process_events()

    assert closed == [True]
    assert DayAnswer.select().count() == before
    assert DayAnswer.get_or_none(DayAnswer.day == WED) is None

    window.destroy()


def test_open_from_today_banner(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    today_view = window.today_view
    banner = today_view.banners_box.get_first_child()
    assert banner is not None
    assert banner.streak_id == _hard_streak_data(seeded_state).id

    banner.catch_up_button.emit("clicked")
    process_events()

    assert today_view.catchup_dialog is not None
    assert today_view.catchup_dialog.dialog_title.get_subtitle() == "75 Hard · 4 days"

    window.destroy()


def test_open_from_streak_view_link(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

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

    window.destroy()
