"""Unit tests for the pure engine (``streaks.engine``) and its helpers (``streaks.clock``,
``streaks.words``).

Two kinds of tests live here: parametrised tables against small, hand-built ``StreakData``
values (no database involved), and literal-value checks against the design fixture
(``tests/fixtures/seed.py``), pinned by the ``seeded``/``today``/``settings`` fixtures from
``tests/unit/conftest.py``. The rules these tests pin are documented in ``docs/engine-rules.md``;
the fixture's literal values are documented in ``tests/fixtures/seed.py``'s module docstring.
"""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timedelta

import pytest

from streaks import clock, words
from streaks.engine import (
    CHART_FULL,
    CHART_HIGH,
    CHART_HOLLOW,
    CHART_LOW,
    CHART_MID,
    CHART_MISSED,
    CHART_UNCONFIRMED_BORDER,
    CHART_UPCOMING,
    CHART_ZERO,
    WEEKDAYS_MON_TO_FRI,
    Answer,
    AnswerData,
    CheckData,
    GoalData,
    Period,
    PeriodKind,
    PeriodResult,
    Settings,
    Status,
    StreakData,
    Tile,
    _banner_title,
    _cell_for_result,
    _open_sentence,
    _unconfirmed_sentence,
    _upcoming_cell,
    active_goals,
    best_run,
    catch_up,
    catch_up_preview,
    current_run,
    due_periods,
    evaluate,
    history,
    is_due,
    mark_missed_preview,
    next_due_day,
    period_for,
    period_label,
    runs,
    sidebar_ended_meta,
    sidebar_meta,
    today_view,
)
from streaks.models import load_all

# ----------------------------------------------------------------------------------------------
# Test helpers.
# ----------------------------------------------------------------------------------------------


def _mk(
    created_on: date,
    day_checks: dict[date, set[int]] | None = None,
    answers: dict[date, Answer] | None = None,
    missed_goals: dict[date, tuple[int, ...]] | None = None,
    n_goals: int = 2,
    **kwargs,
) -> StreakData:
    """Build a small ``StreakData`` for pure-function tests, without touching the database."""
    goals = tuple(
        GoalData(id=i + 1, name=f"g{i}", position=i, removed_on=None) for i in range(n_goals)
    )
    checks = [
        CheckData(goal_id=i + 1, day=day, done_at=datetime(day.year, day.month, day.day, 7, 0))
        for day, idxs in (day_checks or {}).items()
        for i in idxs
    ]
    missed_goals = missed_goals or {}
    answer_data = tuple(
        AnswerData(day=d, status=s, missed_goal_ids=missed_goals.get(d, ()))
        for d, s in (answers or {}).items()
    )
    defaults = dict(
        id=1,
        name="T",
        colour="#3584e4",
        period_kind=PeriodKind.DAILY,
        weekdays_mask=0b0011111,
        times_per_week=3,
        reminder_time=None,
        allow_skip=False,
        created_on=created_on,
        ended_on=None,
        position=0,
    )
    defaults.update(kwargs)
    return StreakData(goals=goals, checks=tuple(checks), answers=answer_data, **defaults)


# ----------------------------------------------------------------------------------------------
# clock.py
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "at,day_start_minutes,expected",
    [
        (datetime(2026, 9, 14, 3, 59), 240, date(2026, 9, 13)),
        (datetime(2026, 9, 14, 4, 0), 240, date(2026, 9, 14)),
        (datetime(2026, 9, 14, 0, 0), 0, date(2026, 9, 14)),
        (datetime(2026, 9, 14, 23, 59), 0, date(2026, 9, 14)),
    ],
)
def test_check_in_day(at, day_start_minutes, expected):
    assert clock.check_in_day(at, day_start_minutes) == expected


def test_now_honours_fake_today(monkeypatch):
    monkeypatch.setenv("STREAKS_FAKE_TODAY", "2026-09-13")
    monkeypatch.delenv("STREAKS_FAKE_NOW", raising=False)
    assert clock.now() == datetime(2026, 9, 13, 21, 45)


def test_now_honours_fake_now(monkeypatch):
    monkeypatch.setenv("STREAKS_FAKE_NOW", "2026-09-13T08:30:00")
    assert clock.now() == datetime(2026, 9, 13, 8, 30)


# ----------------------------------------------------------------------------------------------
# due_periods / period_for / is_due / next_due_day / active_goals
# ----------------------------------------------------------------------------------------------


def test_due_periods_daily():
    s = _mk(date(2026, 1, 1), n_goals=1)
    periods = due_periods(s, date(2026, 1, 5))
    assert periods == [Period(date(2026, 1, d), date(2026, 1, d)) for d in range(1, 6)]


def test_due_periods_weekdays_skips_weekend():
    # 2026-01-01 is a Thursday.
    s = _mk(date(2026, 1, 1), n_goals=1, period_kind=PeriodKind.WEEKDAYS, weekdays_mask=0b0011111)
    periods = due_periods(s, date(2026, 1, 11))
    assert [p.start for p in periods] == [date(2026, 1, d) for d in (1, 2, 5, 6, 7, 8, 9)]


def test_due_periods_n_per_week_crosses_year_boundary():
    # 2026-01-01 (Thursday) falls in the ISO week 2025-12-29 (Mon) .. 2026-01-04 (Sun).
    s = _mk(date(2026, 1, 1), n_goals=1, period_kind=PeriodKind.N_PER_WEEK)
    periods = due_periods(s, date(2026, 1, 1))
    assert periods == [Period(date(2025, 12, 29), date(2026, 1, 4))]


def test_due_periods_monthly_lengths():
    s = _mk(date(2026, 1, 1), n_goals=1, period_kind=PeriodKind.MONTHLY)
    periods = due_periods(s, date(2026, 3, 31))
    assert periods == [
        Period(date(2026, 1, 1), date(2026, 1, 31)),
        Period(date(2026, 2, 1), date(2026, 2, 28)),
        Period(date(2026, 3, 1), date(2026, 3, 31)),
    ]


def test_due_periods_monthly_leap_february():
    s = _mk(date(2028, 1, 1), n_goals=1, period_kind=PeriodKind.MONTHLY)
    periods = due_periods(s, date(2028, 2, 29))
    assert periods[-1] == Period(date(2028, 2, 1), date(2028, 2, 29))


def test_due_periods_stop_at_ended_on():
    s = _mk(date(2026, 1, 1), n_goals=1, ended_on=date(2026, 1, 3))
    periods = due_periods(s, date(2026, 1, 31))
    assert periods == [Period(date(2026, 1, d), date(2026, 1, d)) for d in (1, 2, 3)]


def test_period_for_and_is_due_weekdays():
    s = _mk(date(2026, 1, 1), n_goals=1, period_kind=PeriodKind.WEEKDAYS, weekdays_mask=0b0011111)
    assert is_due(s, date(2026, 1, 3)) is False  # Saturday
    assert is_due(s, date(2026, 1, 5)) is True  # Monday
    assert period_for(s, date(2026, 1, 3)) is None
    assert period_for(s, date(2026, 1, 5)) == Period(date(2026, 1, 5), date(2026, 1, 5))


def test_next_due_day_skips_weekend():
    s = _mk(date(2026, 1, 1), n_goals=1, period_kind=PeriodKind.WEEKDAYS, weekdays_mask=0b0011111)
    assert next_due_day(s, date(2026, 1, 2)) == date(2026, 1, 5)  # Friday -> Monday


def test_active_goals_excludes_removed_before_period_start():
    goals = (
        GoalData(id=1, name="g1", position=0, removed_on=None),
        GoalData(id=2, name="g2", position=1, removed_on=date(2026, 1, 5)),
    )
    s = dataclasses.replace(_mk(date(2026, 1, 1), n_goals=0), goals=goals)
    before = Period(date(2026, 1, 1), date(2026, 1, 1))
    after = Period(date(2026, 1, 10), date(2026, 1, 10))
    assert [g.id for g in active_goals(s, before)] == [1, 2]
    assert [g.id for g in active_goals(s, after)] == [1]


def test_active_goals_excludes_goal_added_after_period_end():
    goals = (
        GoalData(id=1, name="g1", position=0, removed_on=None, added_on=None),
        GoalData(id=2, name="g2", position=1, removed_on=None, added_on=date(2026, 9, 1)),
    )
    s = dataclasses.replace(_mk(date(2026, 5, 1), n_goals=0), goals=goals)
    august = Period(date(2026, 8, 1), date(2026, 8, 31))
    september = Period(date(2026, 9, 1), date(2026, 9, 30))
    assert [g.id for g in active_goals(s, august)] == [1]
    assert [g.id for g in active_goals(s, september)] == [1, 2]


def test_evaluate_new_goal_does_not_change_past_period_status():
    """A goal added mid-streak counts from the period it was added in on; earlier periods keep
    the status they already had, unaffected by the new goal."""
    checks = {
        date(2026, 5, 15): {0},
        date(2026, 6, 15): {0},
        date(2026, 7, 15): {0},
        date(2026, 8, 15): {0},
    }
    goals = (
        GoalData(id=1, name="g1", position=0, removed_on=None, added_on=date(2026, 5, 1)),
        GoalData(id=2, name="g2", position=1, removed_on=None, added_on=date(2026, 9, 1)),
    )
    s = dataclasses.replace(
        _mk(date(2026, 5, 1), checks, n_goals=0, period_kind=PeriodKind.MONTHLY),
        goals=goals,
    )

    results = evaluate(s, date(2026, 9, 10), Settings())
    by_month = {(pr.period.start.year, pr.period.start.month): pr for pr in results}

    for month in (5, 6, 7, 8):
        pr = by_month[(2026, month)]
        assert pr.status == Status.KEPT
        assert pr.total == 1

    assert by_month[(2026, 9)].total == 2


# ----------------------------------------------------------------------------------------------
# evaluate() — period status.
# ----------------------------------------------------------------------------------------------


def test_evaluate_past_period_statuses():
    s = _mk(
        date(2026, 1, 1),
        day_checks={
            date(2026, 1, 5): {0, 1},  # both goals -> KEPT
            date(2026, 1, 6): {0},  # one of two -> PARTIAL
            date(2026, 1, 8): {0},  # answered missed overrides checks -> MISSED
        },
        answers={date(2026, 1, 8): Answer.MISSED},
    )
    results = {pr.period.start: pr for pr in evaluate(s, date(2026, 1, 10), Settings())}
    assert results[date(2026, 1, 5)].status == Status.KEPT
    assert results[date(2026, 1, 6)].status == Status.PARTIAL
    assert results[date(2026, 1, 7)].status == Status.UNCONFIRMED
    assert results[date(2026, 1, 8)].status == Status.MISSED
    assert results[date(2026, 1, 10)].status == Status.OPEN


def test_evaluate_current_period_partial_and_kept():
    partial = _mk(date(2026, 1, 1), day_checks={date(2026, 1, 10): {0}})
    kept = _mk(date(2026, 1, 1), day_checks={date(2026, 1, 10): {0, 1}})
    assert evaluate(partial, date(2026, 1, 10), Settings())[-1].status == Status.PARTIAL
    assert evaluate(kept, date(2026, 1, 10), Settings())[-1].status == Status.KEPT


def test_evaluate_n_per_week_session_needs_all_active_goals():
    s = _mk(
        date(2026, 1, 1),
        day_checks={date(2026, 1, 5): {0}},  # only one of two goals on the 5th: no session
        period_kind=PeriodKind.N_PER_WEEK,
        times_per_week=3,
    )
    pr = evaluate(s, date(2026, 1, 5), Settings())[-1]
    assert pr.done == 0
    assert pr.total == 3


# ----------------------------------------------------------------------------------------------
# runs()
# ----------------------------------------------------------------------------------------------


def test_runs_single_miss_ends_run():
    # Checked every day except the 5th, which is answered missed.
    s = _mk(
        date(2026, 1, 1),
        day_checks={date(2026, 1, d): {0} for d in range(1, 11) if d != 5},
        answers={date(2026, 1, 5): Answer.MISSED},
        n_goals=1,
    )
    result = runs(s, date(2026, 1, 10), Settings())
    assert [r.length for r in result] == [4, 5]
    assert result[0].end == date(2026, 1, 4)
    assert result[1].end is None
    assert result[1].is_best


def test_runs_consecutive_misses_both_end_the_run():
    s = _mk(
        date(2026, 1, 1),
        day_checks={date(2026, 1, d): {0} for d in range(1, 11) if d not in (5, 6)},
        answers={date(2026, 1, 5): Answer.MISSED, date(2026, 1, 6): Answer.MISSED},
        n_goals=1,
    )
    result = runs(s, date(2026, 1, 10), Settings())
    assert [r.length for r in result] == [4, 4]
    assert result[0].end == date(2026, 1, 4)
    assert result[1].start == date(2026, 1, 7)
    assert result[1].end is None


def test_runs_unconfirmed_days_do_not_end_the_run_by_default():
    s = _mk(date(2026, 1, 1), n_goals=1)  # no checks, no answers at all
    result = runs(s, date(2026, 1, 10), Settings())
    assert len(result) == 1
    run = result[0]
    assert run.length == 10
    assert run.end is None
    assert run.unconfirmed == 9  # every day except today (which is OPEN, not UNCONFIRMED)
    assert run.confirmed == 0


def test_runs_count_through_unconfirmed_false_ends_run_past_backfill_window():
    s = _mk(date(2026, 1, 1), n_goals=1)  # no checks, no answers at all
    settings = Settings(count_through_unconfirmed=False, backfill_days=2)
    result = runs(s, date(2026, 1, 10), settings)
    # Days 1-7 are unconfirmed and older than the 2-day backfill window -> hard misses.
    # Days 8-9 are within the window (still soft); day 10 is today (open).
    assert len(result) == 1
    run = result[-1]
    assert run.start == date(2026, 1, 8)
    assert run.length == 3
    assert run.end is None


def test_runs_allow_skip_forgives_first_miss_per_iso_week():
    # 2025-12-29 is a Monday; 2025-12-29..2026-01-04 is one ISO week.
    created = date(2025, 12, 29)
    today = date(2026, 1, 15)
    checked = {
        created + timedelta(days=i): {0}
        for i in range((today - created).days + 1)
        if (created + timedelta(days=i)) not in (date(2025, 12, 29), date(2025, 12, 31))
    }
    s = _mk(
        created,
        day_checks=checked,
        answers={date(2025, 12, 29): Answer.MISSED, date(2025, 12, 31): Answer.MISSED},
        allow_skip=True,
        n_goals=1,
    )
    result = runs(s, today, Settings())
    assert [r.length for r in result] == [2, 15]
    # The forgiven miss (Dec 29) stays inside the run and keeps its MISSED status...
    assert result[0].periods[0].period.start == date(2025, 12, 29)
    assert result[0].periods[0].status == Status.MISSED
    # ...but the run only actually ends at the *second* (un-forgiven) miss, on Dec 31.
    assert result[0].end == date(2025, 12, 30)
    assert result[1].start == date(2026, 1, 1)
    assert result[1].end is None
    assert result[1].is_best


def test_best_run_picks_latest_on_tie():
    s = _mk(
        date(2026, 1, 1),
        day_checks={date(2026, 1, d): {0} for d in (1, 2, 4, 5)},
        answers={date(2026, 1, 3): Answer.MISSED},
        n_goals=1,
    )
    result = runs(s, date(2026, 1, 5), Settings())
    assert [r.length for r in result] == [2, 2]
    assert result[1].is_best is True
    assert result[0].is_best is False


def test_current_run_none_for_ended_streak():
    s = _mk(date(2026, 1, 1), n_goals=1, ended_on=date(2026, 1, 5))
    assert current_run(s, date(2026, 1, 10), Settings()) is None


# ----------------------------------------------------------------------------------------------
# sidebar_meta / sidebar_ended_meta
# ----------------------------------------------------------------------------------------------


def test_sidebar_meta_daily_single_goal():
    # A single-goal streak's meta is the period label alone.
    s = _mk(date(2026, 1, 1), n_goals=1)
    assert sidebar_meta(s) == "Daily"


def test_sidebar_meta_daily():
    s = _mk(date(2026, 1, 1), n_goals=5)
    assert sidebar_meta(s) == "Daily · 5 goals"


def test_sidebar_meta_weekdays_contiguous_range_single_goal():
    s = _mk(date(2026, 1, 1), n_goals=1, period_kind=PeriodKind.WEEKDAYS, weekdays_mask=0b0011111)
    assert sidebar_meta(s) == "Mon–Fri"


def test_sidebar_meta_weekdays_non_contiguous():
    # Mon, Wed, Fri -> bits 0, 2, 4.
    s = _mk(date(2026, 1, 1), n_goals=2, period_kind=PeriodKind.WEEKDAYS, weekdays_mask=0b0010101)
    assert sidebar_meta(s) == "Mon, Wed, Fri · 2 goals"


def test_sidebar_meta_n_per_week():
    s = _mk(date(2026, 1, 1), n_goals=2, period_kind=PeriodKind.N_PER_WEEK, times_per_week=3)
    assert sidebar_meta(s) == "3× a week · 2 goals"


def test_sidebar_meta_monthly_single_goal():
    s = _mk(date(2026, 1, 1), n_goals=1, period_kind=PeriodKind.MONTHLY)
    assert sidebar_meta(s) == "Monthly"


def test_sidebar_ended_meta():
    s = _mk(date(2026, 1, 1), n_goals=1, ended_on=date(2026, 3, 4))
    assert sidebar_ended_meta(s, 31) == "Ended 4 Mar · best 31"


def test_period_label_variants():
    daily = _mk(date(2026, 1, 1), n_goals=1)
    weekdays = _mk(
        date(2026, 1, 1), n_goals=1, period_kind=PeriodKind.WEEKDAYS, weekdays_mask=0b0011111
    )
    n_per_week = _mk(
        date(2026, 1, 1), n_goals=1, period_kind=PeriodKind.N_PER_WEEK, times_per_week=3
    )
    monthly = _mk(date(2026, 1, 1), n_goals=1, period_kind=PeriodKind.MONTHLY)
    assert period_label(daily) == "Daily"
    assert period_label(weekdays) == "Mon–Fri"
    assert period_label(n_per_week) == "3× a week"
    assert period_label(monthly) == "Monthly"


# ----------------------------------------------------------------------------------------------
# Single-goal check-in cards.
# ----------------------------------------------------------------------------------------------


def test_single_card_daily_unticked():
    s = _mk(date(2026, 1, 1), n_goals=1)
    today = date(2026, 1, 5)
    card = today_view([s], today, Settings()).cards[0]
    assert card.single is True
    assert card.kind == "goals"
    assert card.meta == "Daily · day 5"
    assert len(card.goals) == 1
    assert card.goals[0].name == "T"
    assert card.show_footer is False


def test_single_card_daily_ticked_shows_done_time():
    today = date(2026, 1, 5)
    s = _mk(date(2026, 1, 1), n_goals=1)
    s = dataclasses.replace(
        s, checks=(CheckData(goal_id=1, day=today, done_at=datetime(2026, 1, 5, 7, 12)),)
    )
    card = today_view([s], today, Settings()).cards[0]
    assert card.meta == "Daily · done 07:12"
    assert card.goals[0].done_at == datetime(2026, 1, 5, 7, 12)


def test_single_card_monthly_days_left():
    s = _mk(date(2026, 1, 1), n_goals=1, period_kind=PeriodKind.MONTHLY)
    today = date(2026, 1, 14)  # January has 31 days: 17 left.
    card = today_view([s], today, Settings()).cards[0]
    assert card.single is True
    assert card.kind == "monthly"
    assert card.meta == "Monthly · 17 days left"


def test_single_card_monthly_already_done_this_month():
    s = _mk(
        date(2026, 1, 1),
        n_goals=1,
        period_kind=PeriodKind.MONTHLY,
        day_checks={date(2026, 1, 3): {0}},
    )
    today = date(2026, 1, 14)
    card = today_view([s], today, Settings()).cards[0]
    assert card.meta == "Monthly · done this month"


def test_single_card_n_per_week():
    s = _mk(
        date(2026, 1, 1),
        n_goals=1,
        period_kind=PeriodKind.N_PER_WEEK,
        times_per_week=3,
        day_checks={date(2026, 1, 1): {0}},
    )
    today = date(2026, 1, 3)
    card = today_view([s], today, Settings()).cards[0]
    assert card.meta == "3× a week · 1 of 3 this week"


def test_single_goal_not_due_keeps_not_today_card():
    s = _mk(
        date(2026, 1, 5),  # Monday
        n_goals=1,
        period_kind=PeriodKind.WEEKDAYS,
        weekdays_mask=WEEKDAYS_MON_TO_FRI,
    )
    today = date(2026, 1, 11)  # Sunday, not due
    card = today_view([s], today, Settings()).cards[0]
    assert card.kind == "not_due"
    assert card.single is False
    assert card.meta == "Not today"


def test_history_header_subtitle_single_goal_monthly():
    s = _mk(date(2026, 1, 1), n_goals=1, period_kind=PeriodKind.MONTHLY)
    h = history(s, date(2026, 3, 15), Settings())
    assert h.header_subtitle == "Monthly · run 1"


# ----------------------------------------------------------------------------------------------
# Chart cells / tooltips.
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status,done,total,expected_fill",
    [
        (Status.KEPT, 0, 5, CHART_ZERO),  # answered kept, nothing done
        (Status.PARTIAL, 1, 5, CHART_LOW),  # ratio 0.2 < 0.3
        (Status.PARTIAL, 2, 5, CHART_MID),  # ratio 0.4, < 0.6
        (Status.PARTIAL, 4, 5, CHART_HIGH),  # ratio 0.8, < 0.99
        (Status.KEPT, 5, 5, CHART_FULL),  # ratio 1.0
    ],
)
def test_cell_for_result_fill_by_ratio(status, done, total, expected_fill):
    pr = PeriodResult(Period(date(2026, 1, 1), date(2026, 1, 1)), status, done, total)
    cell = _cell_for_result(pr)
    assert cell.fill == expected_fill
    assert cell.border is None


def test_cell_for_result_unconfirmed_and_open_zero():
    unconfirmed = PeriodResult(Period(date(2026, 1, 1), date(2026, 1, 1)), Status.UNCONFIRMED, 0, 5)
    cell = _cell_for_result(unconfirmed)
    assert cell.fill == CHART_HOLLOW
    assert cell.border == CHART_UNCONFIRMED_BORDER
    assert "unconfirmed" in cell.tooltip

    open_zero = PeriodResult(Period(date(2026, 1, 1), date(2026, 1, 1)), Status.OPEN, 0, 5)
    cell = _cell_for_result(open_zero)
    assert cell.fill == CHART_HOLLOW
    assert cell.border == CHART_UNCONFIRMED_BORDER


def test_cell_for_result_missed():
    pr = PeriodResult(Period(date(2026, 1, 1), date(2026, 1, 1)), Status.MISSED, 0, 5)
    cell = _cell_for_result(pr)
    assert cell.fill == CHART_MISSED
    assert cell.tooltip == "missed — run ended"


def test_cell_tooltip_done_of_total():
    pr = PeriodResult(Period(date(2026, 1, 1), date(2026, 1, 1)), Status.KEPT, 5, 5)
    cell = _cell_for_result(pr)
    assert cell.tooltip == "5 of 5 goals"


def test_upcoming_cell():
    cell = _upcoming_cell()
    assert cell.fill == CHART_UPCOMING
    assert cell.tooltip == "upcoming"


# ----------------------------------------------------------------------------------------------
# Banner wording.
# ----------------------------------------------------------------------------------------------


def test_banner_title_single_day():
    assert _banner_title(date(2026, 9, 12), date(2026, 9, 12)) == (
        "One day without a check-in — 12 September"
    )


def test_banner_title_same_month_range():
    assert _banner_title(date(2026, 9, 9), date(2026, 9, 12)) == (
        "Four days without a check-in — 9 to 12 September"
    )


def test_banner_title_cross_month_range():
    assert _banner_title(date(2026, 8, 30), date(2026, 9, 2)) == (
        "Four days without a check-in — 30 August to 2 September"
    )


# ----------------------------------------------------------------------------------------------
# Today-view subtitle wording.
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "n,expected",
    [
        (0, "No check-ins open"),
        (1, "1 check-in open"),
        (2, "2 check-ins open"),
    ],
)
def test_open_sentence(n, expected):
    assert _open_sentence(n) == expected


@pytest.mark.parametrize(
    "n,expected",
    [
        (0, None),
        (1, "1 earlier day unconfirmed"),
        (4, "4 earlier days unconfirmed"),
    ],
)
def test_unconfirmed_sentence(n, expected):
    assert _unconfirmed_sentence(n) == expected


# ----------------------------------------------------------------------------------------------
# words.py
# ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "n,expected",
    [
        (0, "zero"),
        (1, "one"),
        (2, "two"),
        (12, "twelve"),
        (13, "13"),
        (100, "100"),
    ],
)
def test_number_word(n, expected):
    assert words.number_word(n) == expected


def test_number_word_capitalised():
    assert words.sentence_number_word(2) == "Two"
    assert words.sentence_number_word(13) == "13"


@pytest.mark.parametrize(
    "d,expected",
    [
        (date(2026, 9, 1), "1st"),
        (date(2026, 9, 2), "2nd"),
        (date(2026, 9, 3), "3rd"),
        (date(2026, 9, 4), "4th"),
        (date(2026, 9, 11), "11th"),
        (date(2026, 9, 12), "12th"),
        (date(2026, 9, 13), "13th"),
        (date(2026, 9, 21), "21st"),
        (date(2026, 9, 22), "22nd"),
        (date(2026, 9, 23), "23rd"),
    ],
)
def test_ordinal_day(d, expected):
    assert words.ordinal_day(d) == expected


def test_fmt_day():
    assert words.fmt_day(date(2026, 9, 9)) == "9 September"


def test_fmt_day_short():
    assert words.fmt_day_short(date(2026, 3, 4)) == "4 Mar"


def test_fmt_weekday_day():
    assert words.fmt_weekday_day(date(2026, 9, 13)) == "Sunday 13 September"


def test_fmt_range():
    assert words.fmt_range(date(2026, 5, 14), date(2026, 6, 16)) == "14 May – 16 Jun"


def test_time_hm():
    assert words.time_hm(datetime(2026, 9, 13, 7, 12)) == "07:12"


# ================================================================================================
# Literal values from the design fixture. The mock labels 9–12 Sep 2026 as Tue–Fri; the calendar
# says Wed–Sat, and the code follows the calendar.
# ================================================================================================


def _streaks() -> dict[str, StreakData]:
    return {sd.name: sd for sd in load_all()}


def test_fixture_75_hard_runs(seeded, today, settings):
    hard = _streaks()["75 Hard"]
    result = runs(hard, today, settings)
    assert [r.length for r in result] == [28, 34, 51]

    run3 = result[-1]
    assert run3.start == date(2026, 7, 25)
    assert run3.end is None
    assert run3.confirmed == 47
    assert run3.unconfirmed == 4
    assert run3.is_best is True

    partial_days = [pr.period.start for pr in run3.periods if pr.status == Status.PARTIAL]
    expected_partial = [
        date(2026, 7, 28),
        date(2026, 7, 30),
        date(2026, 8, 4),
        date(2026, 8, 10),
        date(2026, 8, 11),
        date(2026, 8, 18),
        date(2026, 8, 21),
        date(2026, 8, 25),
        date(2026, 9, 1),
        date(2026, 9, 8),
        date(2026, 9, 13),
    ]
    assert partial_days == expected_partial


def test_fixture_75_hard_history(seeded, today, settings):
    hard = _streaks()["75 Hard"]
    h = history(hard, today, settings)
    assert h.tiles == [
        Tile("51", "days running", "accent"),
        Tile("51", "days, longest run", "strong"),
        Tile("3", "runs", "strong"),
        Tile("94%", "goals hit", "strong"),
    ]
    bars = {bar.name: (bar.ratio_text, bar.low) for bar in h.goal_bars}
    assert bars["Progress photo"] == ("109/109", False)
    assert bars["45 min outdoors"] == ("109/109", False)
    assert bars["45 min second workout"] == ("83/109", False)
    assert bars["Read 10 pages"] == ("99/109", False)
    assert bars["Stick to the diet"] == ("109/109", False)

    earlier_metas = [r.meta for r in h.earlier_runs]
    assert earlier_metas == ["14 May – 16 Jun · 34 days", "2 Feb – 1 Mar · 28 days"]


def test_history_tiles_and_goal_bars_count_today_in_progress(settings):
    """Three full days then one goal ticked today: the run and longest run both include today,
    goals hit covers the finished days, and each goal bar counts today's ticks too."""
    today = date(2026, 10, 1)
    all_five = {0, 1, 2, 3, 4}
    streak = _mk(
        date(2026, 9, 28),
        day_checks={
            date(2026, 9, 28): all_five,
            date(2026, 9, 29): all_five,
            date(2026, 9, 30): all_five,
            today: {1},
        },
        n_goals=5,
    )
    h = history(streak, today, settings)
    assert h.tiles == [
        Tile("4", "days running", "accent"),
        Tile("4", "days, longest run", "strong"),
        Tile("1", "run", "strong"),
        Tile("100%", "goals hit", "strong"),
    ]
    assert [bar.ratio_text for bar in h.goal_bars] == ["3/4", "4/4", "3/4", "3/4", "3/4"]


def test_history_tiles_span_every_run(settings):
    """The longest run can be an earlier one, the run count includes the open run, and goals
    hit and the goal bars cover every run, not just the one shown."""
    today = date(2026, 9, 8)
    streak = _mk(
        date(2026, 9, 1),
        day_checks={
            date(2026, 9, 1): {0, 1},
            date(2026, 9, 2): {0, 1},
            date(2026, 9, 3): {0, 1},
            date(2026, 9, 4): {0},
            date(2026, 9, 6): {0, 1},
            date(2026, 9, 7): {0, 1},
            date(2026, 9, 8): {0, 1},
        },
        answers={date(2026, 9, 5): Answer.MISSED},
    )
    h = history(streak, today, settings)
    assert h.tiles == [
        Tile("3", "days running", "accent"),
        Tile("4", "days, longest run", "strong"),
        Tile("2", "runs", "strong"),
        Tile("92%", "goals hit", "strong"),
    ]
    assert [bar.ratio_text for bar in h.goal_bars] == ["7/7", "6/7"]

    earlier = history(streak, today, settings, run_index=1)
    assert earlier.tiles[0] == Tile("4", "days running", "accent")
    assert earlier.tiles[1:] == h.tiles[1:]


def test_fixture_75_hard_sidebar_and_card(seeded, today, settings):
    hard = _streaks()["75 Hard"]
    assert sidebar_meta(hard) == "Daily · 5 goals"
    assert current_run(hard, today, settings).length == 51

    tv = today_view(list(load_all()), today, settings)
    card = next(c for c in tv.cards if c.name == "75 Hard")
    assert card.meta == "3 of 5 · day 51"


def test_fixture_75_hard_banner(seeded, today, settings):
    tv = today_view(list(load_all()), today, settings)
    banner = next(b for b in tv.banners if b.streak_id == _streaks()["75 Hard"].id)
    assert banner.title == "Four days without a check-in — 9 to 12 September"
    assert banner.body == "The 51-day run continues. Unconfirmed days do not end a run."


def test_fixture_75_hard_catch_up(seeded, today, settings):
    hard = _streaks()["75 Hard"]
    cu = catch_up(hard, today, settings)
    assert [d.day for d in cu.days] == [
        date(2026, 9, 9),
        date(2026, 9, 10),
        date(2026, 9, 11),
        date(2026, 9, 12),
    ]
    assert cu.subtitle == "75 Hard · 4 days"


def test_fixture_75_hard_catch_up_preview_row_states(seeded, today, settings):
    hard = _streaks()["75 Hard"]
    second_workout = next(g.id for g in hard.goals if g.name == "45 min second workout")
    answers = {
        date(2026, 9, 9): (Answer.KEPT, ()),
        date(2026, 9, 11): (Answer.MISSED, (second_workout,)),
        date(2026, 9, 12): (Answer.KEPT, ()),
    }
    preview = catch_up_preview(hard, today, settings, answers)
    assert preview.row_state == {
        date(2026, 9, 9): "All 5 kept",
        date(2026, 9, 10): "Unconfirmed",
        date(2026, 9, 11): "4 of 5 kept · 1 missed",
        date(2026, 9, 12): "All 5 kept",
    }
    assert preview.ends_run is True


def test_fixture_75_hard_catch_up_preview_summary_ends_with_following(seeded, today, settings):
    # 11 September partial (one goal missed) ends the run; 10 September is left unanswered.
    # Note: the design mock's own arithmetic guessed 47/4 days for this fixture, but the engine
    # (authoritative per its run-length rules) computes 48/2 — trust the engine here.
    hard = _streaks()["75 Hard"]
    second_workout = next(g.id for g in hard.goals if g.name == "45 min second workout")
    answers = {
        date(2026, 9, 9): (Answer.KEPT, ()),
        date(2026, 9, 11): (Answer.MISSED, (second_workout,)),
        date(2026, 9, 12): (Answer.KEPT, ()),
    }
    preview = catch_up_preview(hard, today, settings, answers)
    assert preview.summary == (
        "Run 3 ends on 11 September at 48 days. Run 4 starts on 12 September at 2 days. "
        "1 day unconfirmed."
    )


def test_fixture_75_hard_catch_up_preview_summary_ends_two_unconfirmed_left(
    seeded, today, settings
):
    hard = _streaks()["75 Hard"]
    second_workout = next(g.id for g in hard.goals if g.name == "45 min second workout")
    answers = {date(2026, 9, 11): (Answer.MISSED, (second_workout,))}
    preview = catch_up_preview(hard, today, settings, answers)
    assert preview.summary == (
        "Run 3 ends on 11 September at 48 days. Run 4 starts on 12 September at 2 days. "
        "3 days unconfirmed."
    )


def test_fixture_75_hard_catch_up_preview_summary_ends_no_unconfirmed_left(seeded, today, settings):
    hard = _streaks()["75 Hard"]
    second_workout = next(g.id for g in hard.goals if g.name == "45 min second workout")
    answers = {
        date(2026, 9, 9): (Answer.KEPT, ()),
        date(2026, 9, 10): (Answer.KEPT, ()),
        date(2026, 9, 11): (Answer.MISSED, (second_workout,)),
        date(2026, 9, 12): (Answer.KEPT, ()),
    }
    preview = catch_up_preview(hard, today, settings, answers)
    assert (
        preview.summary
        == "Run 3 ends on 11 September at 48 days. Run 4 starts on 12 September at 2 days."
    )


def test_fixture_75_hard_catch_up_preview_summary_continues(seeded, today, settings):
    hard = _streaks()["75 Hard"]
    answers = {date(2026, 9, 9): (Answer.KEPT, ()), date(2026, 9, 12): (Answer.KEPT, ())}
    preview = catch_up_preview(hard, today, settings, answers)
    assert preview.ends_run is False
    assert preview.summary == "Run 3 continues at 51 days. 2 days unconfirmed."


def test_fixture_75_hard_catch_up_preview_summary_continues_none_unconfirmed_left(
    seeded, today, settings
):
    hard = _streaks()["75 Hard"]
    answers = {date(2026, 9, d): (Answer.KEPT, ()) for d in (9, 10, 11, 12)}
    preview = catch_up_preview(hard, today, settings, answers)
    assert preview.ends_run is False
    assert preview.summary == "Run 3 continues at 51 days."


def test_catch_up_preview_row_state_variants():
    s = _mk(date(2026, 1, 1), n_goals=2)
    today = date(2026, 1, 5)
    answers = {
        date(2026, 1, 1): (Answer.KEPT, ()),
        date(2026, 1, 2): (Answer.MISSED, (2,)),
        date(2026, 1, 3): (Answer.MISSED, ()),
    }
    preview = catch_up_preview(s, today, Settings(), answers)
    assert preview.row_state == {
        date(2026, 1, 1): "All 2 kept",
        date(2026, 1, 2): "1 of 2 kept · 1 missed",
        date(2026, 1, 3): "Missed",
        date(2026, 1, 4): "Unconfirmed",
    }


def test_catch_up_preview_row_state_one_goal_streak_says_kept():
    s = _mk(date(2026, 1, 1), n_goals=1)
    preview = catch_up_preview(
        s, date(2026, 1, 3), Settings(), {date(2026, 1, 1): (Answer.KEPT, ())}
    )
    assert preview.row_state[date(2026, 1, 1)] == "Kept"


def test_catch_up_preview_summary_ends_without_a_following_run():
    # Weekdays-only streak, today a Saturday it isn't due: marking the last unconfirmed weekday
    # missed leaves no due period afterwards, so there's no following run to report.
    s = _mk(
        date(2026, 1, 5),  # Monday
        n_goals=1,
        period_kind=PeriodKind.WEEKDAYS,
        weekdays_mask=WEEKDAYS_MON_TO_FRI,
    )
    today = date(2026, 1, 10)  # Saturday, not due
    preview = catch_up_preview(s, today, Settings(), {date(2026, 1, 9): (Answer.MISSED, ())})
    assert preview.ends_run is True
    assert preview.summary == "Run 1 ends on 9 January at 4 days. 4 days unconfirmed."


def test_catch_up_preview_summary_ends_day_skips_allow_skip_forgiven_miss():
    # Monday 5 Jan 2026 created, allow_skip on. 5-11 Jan is one ISO week; allow_skip forgives the
    # first miss in it, so the 6 Jan miss (first, forgiven) does not end the run, but the 8 Jan
    # miss (second in the week, un-forgiven) does. The summary must name 8 January, not 6 January.
    created = date(2026, 1, 5)
    s = _mk(
        created,
        day_checks={date(2026, 1, 5): {0}, date(2026, 1, 7): {0}, date(2026, 1, 9): {0}},
        n_goals=1,
        allow_skip=True,
    )
    today = date(2026, 1, 10)  # Saturday
    answers = {
        date(2026, 1, 6): (Answer.MISSED, ()),
        date(2026, 1, 8): (Answer.MISSED, ()),
    }
    preview = catch_up_preview(s, today, Settings(), answers)
    assert preview.ends_run is True
    assert preview.summary == (
        "Run 1 ends on 8 January at 3 days. Run 2 starts on 9 January at 2 days."
    )


def test_fixture_75_hard_mark_missed_preview(seeded, today, settings):
    hard = _streaks()["75 Hard"]
    assert mark_missed_preview(hard, today, today, settings) == "This ends run 3 at 50 days."


def test_mark_missed_preview_for_an_earlier_day_ends_the_run_before_it(settings):
    today = date(2026, 9, 10)
    streak = _mk(date(2026, 9, 1), day_checks={date(2026, 9, d): {0, 1} for d in range(1, 11)})
    assert (
        mark_missed_preview(streak, date(2026, 9, 9), today, settings)
        == "This ends run 1 at 8 days."
    )


def test_fixture_no_snoozing(seeded, today, settings):
    streak = _streaks()["No snoozing the alarm"]
    assert current_run(streak, today, settings).length == 12
    assert sidebar_meta(streak) == "Mon–Fri"

    tv = today_view(list(load_all()), today, settings)
    card = next(c for c in tv.cards if c.name == "No snoozing the alarm")
    assert card.kind == "not_due"
    assert card.meta == "Not today"
    assert card.body == "Weekdays only. Next check-in Monday 14 September."


def test_fixture_gym(seeded, today, settings):
    streak = _streaks()["Gym, three times a week"]
    assert current_run(streak, today, settings).length == 9
    assert sidebar_meta(streak) == "3× a week · 2 goals"

    tv = today_view(list(load_all()), today, settings)
    card = next(c for c in tv.cards if c.name == "Gym, three times a week")
    assert card.meta == "2 of 3 this week"
    assert card.show_footer is False

    h = history(streak, today, settings)
    assert h.tiles == [
        Tile("9", "weeks running", "accent"),
        Tile("9", "weeks, longest run", "strong"),
        Tile("1", "run", "strong"),
        Tile("88%", "goals hit", "strong"),
    ]
    bars = {bar.name: (bar.ratio_text, bar.low) for bar in h.goal_bars}
    assert bars == {"45 min session": ("8/9", False), "Log the weights": ("5/9", True)}


def test_fixture_clip_fingernails(seeded, today, settings):
    streak = _streaks()["Clip fingernails"]
    assert current_run(streak, today, settings).length == 4
    assert sidebar_meta(streak) == "Monthly"

    tv = today_view(list(load_all()), today, settings)
    card = next(c for c in tv.cards if c.name == "Clip fingernails")
    assert card.single is True
    assert card.meta == "Monthly · 17 days left"
    assert len(card.goals) == 1
    assert card.goals[0].name == "Clip fingernails"


def test_fixture_couch_to_5k(seeded, today, settings):
    streak = _streaks()["Couch to 5K"]
    assert streak.ended_on == date(2026, 3, 4)
    best = best_run(streak, today, settings)
    assert best.length == 31
    assert sidebar_ended_meta(streak, best.length) == "Ended 4 Mar · best 31"


def test_fixture_couch_to_5k_history_ended_streak(seeded, today, settings):
    """For an ended streak the first tile reports the last run and the header subtitle says when
    it ended."""
    streak = _streaks()["Couch to 5K"]
    h = history(streak, today, settings)
    assert h.tiles == [
        Tile("31", "days, last run", "accent"),
        Tile("31", "days, longest run", "strong"),
        Tile("1", "run", "strong"),
        Tile("100%", "goals hit", "strong"),
    ]
    assert h.header_subtitle == "Daily · ended 4 Mar"
    assert h.chart_title == "Run 1 · 2 Feb – 4 Mar"
    assert h.catch_up_link is None


def test_fixture_today_view(seeded, today, settings):
    tv = today_view(list(load_all()), today, settings)
    assert tv.title == "Sunday 13 September"
    assert tv.subtitle == "2 check-ins open · 4 earlier days unconfirmed"
    assert tv.open_count == 2
    assert [c.name for c in tv.cards] == [
        "75 Hard",
        "Gym, three times a week",
        "No snoozing the alarm",
        "Clip fingernails",
    ]
    # Today never shows a card for an ended streak — "Couch to 5K" (ended 4 Mar) has no card
    # above, confirmed explicitly here too.
    assert "Couch to 5K" not in [c.name for c in tv.cards]


def test_ended_streak_has_no_catch_up_link_even_with_unconfirmed_periods(today, settings):
    """An ended streak's history never offers a catch-up link, even if its last (closed) run
    happens to still contain unconfirmed periods — there's no open run left to catch up on."""
    streak = _mk(
        date(2026, 1, 1),
        day_checks={date(2026, 1, 1): {0, 1}},
        # 2-3 Jan: never checked, never answered -> unconfirmed periods inside the run.
        ended_on=date(2026, 1, 4),
    )
    h = history(streak, today, settings)
    assert h.catch_up_link is None


def test_kept_answer_counts_as_all_goals_done(seeded, today, settings):
    """A day answered "Kept" (e.g. via catch-up) renders as a full cell and counts every goal."""
    from streaks.engine import CHART_FULL, Answer, AnswerData, Status, _cell_for_result, evaluate

    hard = next(s for s in load_all() if s.name == "75 Hard")
    day = date(2026, 9, 10)
    assert not any(a.day == day for a in hard.answers)
    with_answer = dataclasses.replace(
        hard, answers=(*hard.answers, AnswerData(day=day, status=Answer.KEPT, missed_goal_ids=()))
    )
    result = next(pr for pr in evaluate(with_answer, today, settings) if pr.period.start == day)
    assert result.status == Status.KEPT
    assert result.done == result.total == 5
    assert _cell_for_result(result).fill == CHART_FULL
