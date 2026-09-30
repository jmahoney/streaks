"""Unit tests for the pure engine (``streaks.engine``); ``streaks.clock`` and ``streaks.words``
have their own test modules.

Two kinds of tests live here: parametrised tables against small, hand-built ``StreakData``
values (no database involved), and literal-value checks against the design fixture
(``tests/fixtures/seed.py``), pinned by the ``seeded``/``today``/``settings`` fixtures from
``tests/unit/conftest.py``. The rules these tests pin are documented in ``docs/engine-rules.md``;
the fixture's literal values are documented in ``tests/fixtures/seed.py``'s module docstring.
"""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timedelta

from streaks.engine import (
    CHART_FULL,
    CHART_HIGH,
    CHART_HOLLOW,
    CHART_LOW,
    CHART_MID,
    CHART_MISSED,
    CHART_UNCONFIRMED_BORDER,
    CHART_UPCOMING,
    WEEKDAYS_MON_TO_FRI,
    Answer,
    AnswerData,
    CheckData,
    GoalData,
    Period,
    PeriodKind,
    Settings,
    Status,
    StreakData,
    Tile,
    active_goals,
    best_run,
    catch_up,
    catch_up_preview,
    current_goals,
    current_run,
    due_periods,
    evaluate,
    history,
    is_due,
    mark_missed_preview,
    next_due_day,
    open_count,
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
# Chart cells / tooltips, via history()'s activity chart.
# ----------------------------------------------------------------------------------------------


def _week_of(streak, today, settings=None):
    """The one-week lifetime `history()` chart for a streak created on a Monday, flattened
    Mon..Sun. Lifetime (not the default per-run chart) renders every evaluated day, including a
    day whose miss ended its run — a run's own chart never does, since a hard miss is the
    boundary between runs and belongs to neither."""
    h = history(streak, today, settings or Settings(), chart="lifetime", weeks_shown=1)
    assert len(h.weeks) == 1
    return h.weeks[0]


def test_history_chart_fill_by_ratio_and_status():
    """One week, Monday to Sunday: a ratio ladder (low/mid/high/full), an unconfirmed day, an
    explicit miss, and (Sunday, after today) an upcoming day."""
    monday = date(2026, 9, 1)
    monday -= timedelta(days=monday.weekday())
    today = monday + timedelta(days=5)  # Saturday
    s = _mk(
        monday,
        day_checks={
            monday: {0},  # 1/5 -> ratio 0.2 < 0.3
            monday + timedelta(days=1): {0, 1},  # 2/5 -> ratio 0.4 < 0.6
            monday + timedelta(days=2): {0, 1, 2, 3},  # 4/5 -> ratio 0.8 < 0.99
            monday + timedelta(days=3): {0, 1, 2, 3, 4},  # 5/5 -> ratio 1.0
            # monday + 4 (Friday): no checks, no answer -> unconfirmed.
        },
        answers={today: Answer.MISSED},  # Saturday (today), explicitly missed
        n_goals=5,
    )
    week = _week_of(s, today)

    assert week[0].fill == CHART_LOW
    assert week[1].fill == CHART_MID
    assert week[2].fill == CHART_HIGH
    assert week[3].fill == CHART_FULL
    assert week[3].border is None
    assert week[3].tooltip == "5 of 5 goals"

    friday = week[4]
    assert friday.fill == CHART_HOLLOW
    assert friday.border == CHART_UNCONFIRMED_BORDER
    assert "unconfirmed" in friday.tooltip

    saturday = week[5]
    assert saturday.fill == CHART_MISSED
    assert saturday.border is None
    assert saturday.tooltip == "missed — run ended"

    sunday = week[6]
    assert sunday.fill == CHART_UPCOMING
    assert sunday.border is None
    assert sunday.tooltip == "upcoming"


def test_history_chart_todays_cell_with_nothing_done_is_hollow():
    """Today itself, checked in nothing yet, renders the same hollow/bordered cell as a past
    unconfirmed day."""
    today = date(2026, 1, 5)
    s = _mk(today, n_goals=1)
    cell = _week_of(s, today)[today.weekday()]
    assert cell.fill == CHART_HOLLOW
    assert cell.border == CHART_UNCONFIRMED_BORDER


# ----------------------------------------------------------------------------------------------
# Banner wording, via today_view()'s quiet-days banner.
# ----------------------------------------------------------------------------------------------


def _banner_for(streak, today):
    tv = today_view([streak], today, Settings())
    return next(b for b in tv.banners if b.streak_id == streak.id)


def test_banner_title_single_day():
    created = date(2026, 9, 1)
    today = date(2026, 9, 13)
    checked = {created + timedelta(days=i): {0} for i in range((today - created).days) if i != 11}
    s = _mk(created, day_checks=checked, n_goals=1)  # every day kept except 12 Sep; today open
    assert _banner_for(s, today).title == "One day without a check-in — 12 September"


def test_banner_title_same_month_range():
    created = date(2026, 9, 1)
    today = date(2026, 9, 13)
    checked = {
        created + timedelta(days=i): {0}
        for i in range((today - created).days)
        if i not in (8, 9, 10, 11)  # 9-12 Sep unconfirmed
    }
    s = _mk(created, day_checks=checked, n_goals=1)
    assert _banner_for(s, today).title == "Four days without a check-in — 9 to 12 September"


def test_banner_title_cross_month_range():
    created = date(2026, 8, 1)
    today = date(2026, 9, 13)
    gap = (date(2026, 8, 30), date(2026, 9, 2))  # 4 days, straddling the month boundary
    checked = {
        created + timedelta(days=i): {0}
        for i in range((today - created).days)
        if not (gap[0] <= created + timedelta(days=i) <= gap[1])
    }
    s = _mk(created, day_checks=checked, n_goals=1)
    assert _banner_for(s, today).title == "Four days without a check-in — 30 August to 2 September"


# ----------------------------------------------------------------------------------------------
# Today-view subtitle wording, via today_view().
# ----------------------------------------------------------------------------------------------


def test_subtitle_no_check_ins_open():
    today = date(2026, 1, 5)
    s = _mk(today, day_checks={today: {0}}, n_goals=1)  # today already fully checked in
    assert today_view([s], today, Settings()).subtitle == "No check-ins open"


def test_subtitle_open_check_ins_counted():
    today = date(2026, 1, 5)
    open_streak = _mk(today, n_goals=1)  # created today, nothing checked yet -> open
    assert today_view([open_streak], today, Settings()).subtitle == "1 check-in open"
    assert today_view([open_streak, open_streak], today, Settings()).subtitle == "2 check-ins open"


def test_subtitle_unconfirmed_days_counted():
    created = date(2026, 9, 1)
    today = date(2026, 9, 3)
    # 1 Sep kept, 2 Sep unconfirmed, today (3 Sep) checked -> not open.
    s = _mk(created, day_checks={created: {0}, today: {0}}, n_goals=1)
    assert today_view([s], today, Settings()).subtitle == (
        "No check-ins open · 1 earlier day unconfirmed"
    )


def test_subtitle_unconfirmed_days_pluralised():
    created = date(2026, 9, 1)
    today = date(2026, 9, 7)
    # 2-5 Sep unconfirmed (4 days); 1 and 6 Sep kept; today (7 Sep) checked -> not open.
    s = _mk(
        created,
        day_checks={created: {0}, date(2026, 9, 6): {0}, today: {0}},
        n_goals=1,
    )
    assert today_view([s], today, Settings()).subtitle == (
        "No check-ins open · 4 earlier days unconfirmed"
    )


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
    # Note: a naive day count gives 47/4 for this fixture, but the engine (authoritative per its
    # run-length rules) computes 48/2 — trust the engine here.
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
    from streaks.engine import AnswerData

    hard = next(s for s in load_all() if s.name == "75 Hard")
    day = date(2026, 9, 10)
    assert not any(a.day == day for a in hard.answers)
    with_answer = dataclasses.replace(
        hard, answers=(*hard.answers, AnswerData(day=day, status=Answer.KEPT, missed_goal_ids=()))
    )
    result = next(pr for pr in evaluate(with_answer, today, settings) if pr.period.start == day)
    assert result.status == Status.KEPT
    assert result.done == result.total == 5

    run = current_run(with_answer, today, settings)
    monday0 = run.start - timedelta(days=run.start.weekday())
    flat = [c for week in history(with_answer, today, settings).weeks for c in week]
    assert flat[(day - monday0).days].fill == CHART_FULL


def test_current_goals_skips_removed_and_orders_by_position():
    streak = _mk(date(2026, 9, 1), n_goals=3)
    reordered = (
        dataclasses.replace(streak.goals[0], position=2),
        dataclasses.replace(streak.goals[1], removed_on=date(2026, 9, 5)),
        dataclasses.replace(streak.goals[2], position=0),
    )
    streak = dataclasses.replace(streak, goals=reordered)
    assert [g.name for g in current_goals(streak)] == ["g2", "g0"]


def test_open_count_counts_streaks_with_unticked_goals_today():
    today = date(2026, 9, 14)  # a Monday
    untouched = _mk(date(2026, 9, 1))
    done = _mk(date(2026, 9, 1), day_checks={today: {0, 1}})
    half = _mk(date(2026, 9, 1), day_checks={today: {0}})
    ended = _mk(date(2026, 9, 1), ended_on=date(2026, 9, 10))
    weekend_only = _mk(date(2026, 9, 1), period_kind=PeriodKind.WEEKDAYS, weekdays_mask=0b1100000)
    assert open_count([untouched, done, half, ended, weekend_only], today) == 2
