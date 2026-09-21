"""Unit tests for the pure engine (``streaks.engine``) and its helpers (``streaks.clock``,
``streaks.words``).

Two kinds of tests live here: parametrised tables against small, hand-built ``StreakData``
values (no database involved), and literal-value checks against the design fixture
(``tests/fixtures/seed.py``), pinned by the ``seeded``/``today``/``settings`` fixtures from
``tests/unit/conftest.py``. The fixture's literal values come from
``docs/phases/01-models-engine.md`` and were computed independently of this code.
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


def test_sidebar_meta_daily():
    s = _mk(date(2026, 1, 1), n_goals=5)
    assert sidebar_meta(s) == "Daily · 5 goals"


def test_sidebar_meta_weekdays_contiguous_range():
    s = _mk(date(2026, 1, 1), n_goals=1, period_kind=PeriodKind.WEEKDAYS, weekdays_mask=0b0011111)
    assert sidebar_meta(s) == "Mon–Fri · 1 goal"


def test_sidebar_meta_weekdays_non_contiguous():
    # Mon, Wed, Fri -> bits 0, 2, 4.
    s = _mk(date(2026, 1, 1), n_goals=2, period_kind=PeriodKind.WEEKDAYS, weekdays_mask=0b0010101)
    assert sidebar_meta(s) == "Mon, Wed, Fri · 2 goals"


def test_sidebar_meta_n_per_week():
    s = _mk(date(2026, 1, 1), n_goals=2, period_kind=PeriodKind.N_PER_WEEK, times_per_week=3)
    assert sidebar_meta(s) == "3× a week · 2 goals"


def test_sidebar_meta_monthly():
    s = _mk(date(2026, 1, 1), n_goals=1, period_kind=PeriodKind.MONTHLY)
    assert sidebar_meta(s) == "Monthly · 1 goal"


def test_sidebar_ended_meta():
    s = _mk(date(2026, 1, 1), n_goals=1, ended_on=date(2026, 3, 4))
    assert sidebar_ended_meta(s, 31) == "Ended 4 Mar · best 31"


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
        (0, "No check-ins open."),
        (1, "One check-in open."),
        (2, "Two check-ins open."),
    ],
)
def test_open_sentence(n, expected):
    assert _open_sentence(n) == expected


@pytest.mark.parametrize(
    "n,expected",
    [
        (0, None),
        (1, "One earlier day is unconfirmed."),
        (4, "Four earlier days are unconfirmed."),
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
    assert words.Number_word(2) == "Two"
    assert words.Number_word(13) == "13"


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
# Literal-value tests against the design fixture (tests/fixtures/seed.py).
#
# All numbers/strings below come straight from the "Expected values" list in
# docs/phases/01-models-engine.md, which states they were computed independently of this code.
# The one deliberate deviation (documented in the handback report) is weekday *names*: the brief's
# prose labels 9/10/11/12 September 2026 as Tue/Wed/Thu/Fri, but 13 September 2026 is a Sunday (by
# both `datetime` and the Unix `date` command), which makes 9/10/11/12 September Wed/Thu/Fri/Sat.
# Dates and counts are asserted as given; weekday-name strings use the calendar's actual names.
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
        ("51", "days running", "accent"),
        ("4", "unconfirmed", "dim"),
        ("47", "confirmed kept", "strong"),
        ("94%", "goals hit", "strong"),
    ]
    bars = {name: (ratio_text, low) for name, _ratio, ratio_text, low in h.goal_bars}
    assert bars["Progress photo"] == ("9/9", False)
    assert bars["45 min outdoors"] == ("9/9", False)
    assert bars["45 min second workout"] == ("6/9", True)
    assert bars["Read 10 pages"] == ("8/9", False)
    assert bars["Stick to the diet"] == ("9/9", False)

    earlier_metas = [meta for (_title, meta, _strip, _idx) in h.earlier_runs]
    assert earlier_metas == ["14 May – 16 Jun · 34 days", "2 Feb – 1 Mar · 28 days"]


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
    assert banner.body == (
        "Your 51-day run is still counted as running. It only ends if you tell me a goal "
        "was missed."
    )


def test_fixture_75_hard_catch_up(seeded, today, settings):
    hard = _streaks()["75 Hard"]
    cu = catch_up(hard, today, settings)
    assert [d for d, _label in cu.days] == [
        date(2026, 9, 9),
        date(2026, 9, 10),
        date(2026, 9, 11),
        date(2026, 9, 12),
    ]
    assert cu.subtitle == "75 Hard · 4 days"


def test_fixture_75_hard_catch_up_preview(seeded, today, settings):
    hard = _streaks()["75 Hard"]
    answers = {
        date(2026, 9, 9): (Answer.KEPT, ()),
        date(2026, 9, 11): (Answer.MISSED, (2,)),
        date(2026, 9, 12): (Answer.KEPT, ()),
    }
    preview = catch_up_preview(hard, today, settings, answers)
    assert preview.row_warning[date(2026, 9, 11)] == (
        "Saving this ends the 48-day run on 11 September and starts run 4 on the 12th."
    )
    assert preview.summary == (
        "Run 3 ends at 48 days — your best run so far. Run 4 is on 2 days. Thursday stays "
        "hollow — unanswered, and it doesn't break anything."
    )


def test_fixture_75_hard_mark_missed_preview(seeded, today, settings):
    hard = _streaks()["75 Hard"]
    assert mark_missed_preview(hard, today, settings) == "This ends run 3 at 50 days."


def test_fixture_no_snoozing(seeded, today, settings):
    streak = _streaks()["No snoozing the alarm"]
    assert current_run(streak, today, settings).length == 12
    assert sidebar_meta(streak) == "Mon–Fri · 1 goal"

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


def test_fixture_clip_fingernails(seeded, today, settings):
    streak = _streaks()["Clip fingernails"]
    assert current_run(streak, today, settings).length == 4
    assert sidebar_meta(streak) == "Monthly · 1 goal"

    tv = today_view(list(load_all()), today, settings)
    card = next(c for c in tv.cards if c.name == "Clip fingernails")
    assert card.meta == "Due this month"
    assert card.goals[0].trailing == "17 days left"


def test_fixture_couch_to_5k(seeded, today, settings):
    streak = _streaks()["Couch to 5K"]
    assert streak.ended_on == date(2026, 3, 4)
    best = best_run(streak, today, settings)
    assert best.length == 31
    assert sidebar_ended_meta(streak, best.length) == "Ended 4 Mar · best 31"


def test_fixture_couch_to_5k_history_ended_streak(seeded, today, settings):
    """Phase 5: for an ended streak, the first stat tile reports the best run (not "still
    running"), and the header subtitle says when it ended rather than which run is showing."""
    streak = _streaks()["Couch to 5K"]
    h = history(streak, today, settings)
    assert h.tiles == [
        ("31", "days, best run", "accent"),
        ("0", "unconfirmed", "dim"),
        ("31", "confirmed kept", "strong"),
        ("100%", "goals hit", "strong"),
    ]
    assert h.header_subtitle == "Daily · 1 goal · ended 4 Mar"
    assert h.chart_title == "Run 1 · 2 Feb – 4 Mar"
    assert h.catch_up_link is None


def test_fixture_today_view(seeded, today, settings):
    tv = today_view(list(load_all()), today, settings)
    assert tv.title == "Sunday 13 September"
    assert tv.subtitle == "Two check-ins open. Four earlier days are unconfirmed."
    assert tv.open_count == 2
    assert [c.name for c in tv.cards] == [
        "75 Hard",
        "Gym, three times a week",
        "No snoozing the alarm",
        "Clip fingernails",
    ]
    # Phase 8 deliverable 5: Today never shows a card for an ended streak — "Couch to 5K" (ended
    # 4 Mar) has no card above, confirmed explicitly here too.
    assert "Couch to 5K" not in [c.name for c in tv.cards]


def test_ended_streak_has_no_catch_up_link_even_with_unconfirmed_periods(today, settings):
    """Phase 8 deliverable 5: an ended streak's history never offers a catch-up link, even if its
    last (closed) run happens to still contain unconfirmed periods — there's no open run left to
    catch up on (``engine.catch_up()`` needs ``current_run()``, which is always ``None`` once a
    streak has ended)."""
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
