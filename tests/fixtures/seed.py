"""The design fixture: five illustrative streaks anchored on Sunday 13 September 2026.

This dataset is the source of truth used by both the unit test suite (``tests/unit``) and the
GUI/screenshot scaffold (``tests/gui/screens.py``), so every screen and every expected value in
``docs/phases/01-models-engine.md`` line up with exactly this data. See that file for the literal
per-streak description this module implements.

Importable (``from fixtures.seed import seed``) and runnable directly
(``python3 tests/fixtures/seed.py``, which initialises the on-disk database at
``$STREAKS_DATA_DIR`` and seeds it).
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from streaks.engine import Answer, PeriodKind  # noqa: E402
from streaks.models import (  # noqa: E402
    Goal,
    Streak,
    answer_day,
    create_streak,
    end_streak,
    toggle_goal_check,
)

# The story stops answering/checking in the last active run a few days before the fixture
# "today", to leave some days unconfirmed for the catch-up/banner screens to show.
_UNCONFIRMED_FROM = date(2026, 9, 9)


def _daterange(a: date, b: date) -> Iterator[date]:
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def _goals(streak: Streak) -> list[Goal]:
    return list(Goal.select().where(Goal.streak == streak).order_by(Goal.position))


def _check(goal: Goal, day: date, hour: int, minute: int) -> None:
    toggle_goal_check(goal, day, datetime(day.year, day.month, day.day, hour, minute))


def _apply_daily_run_checks(
    goals: list[Goal], run_start: date, run_end: date, unconfirmed_from: date
) -> None:
    """Check off "75 Hard"-style daily goals for one run, per the brief's day-index rule.

    ``i`` is the day index from the run's own start. ``i % 7 == 3`` checks everything except
    goal 2 ("45 min second workout"); ``i % 11 == 5`` checks only goals 0, 1, 4; otherwise every
    goal is checked. Days from ``unconfirmed_from`` onward are left alone (handled by the caller).
    """
    last_day = min(run_end, unconfirmed_from - timedelta(days=1))
    for day in _daterange(run_start, last_day):
        i = (day - run_start).days
        if i % 7 == 3:
            indices = (0, 1, 3, 4)
        elif i % 11 == 5:
            indices = (0, 1, 4)
        else:
            indices = range(len(goals))
        for gi in indices:
            _check(goals[gi], day, 7, gi * 5)


def _seed_75_hard(today: date) -> Streak:
    streak = create_streak(
        "75 Hard",
        "#3584e4",
        PeriodKind.DAILY,
        [
            "Progress photo",
            "45 min outdoors",
            "45 min second workout",
            "Read 10 pages",
            "Stick to the diet",
        ],
        created_on=date(2026, 2, 2),
    )
    goals = _goals(streak)

    # Run 1: 2 Feb - 1 Mar.
    _apply_daily_run_checks(goals, date(2026, 2, 2), date(2026, 3, 1), _UNCONFIRMED_FROM)
    # 2 Mar - 13 May: every day answered missed.
    for day in _daterange(date(2026, 3, 2), date(2026, 5, 13)):
        answer_day(streak, day, Answer.MISSED)

    # Run 2: 14 May - 16 Jun.
    _apply_daily_run_checks(goals, date(2026, 5, 14), date(2026, 6, 16), _UNCONFIRMED_FROM)
    # 17 Jun - 24 Jul: every day answered missed.
    for day in _daterange(date(2026, 6, 17), date(2026, 7, 24)):
        answer_day(streak, day, Answer.MISSED)

    # Run 3: 25 Jul - today. 9-12 Sep are left unconfirmed (nothing checked, no answer).
    _apply_daily_run_checks(goals, date(2026, 7, 25), today, _UNCONFIRMED_FROM)
    if today >= date(2026, 9, 13):
        _check(goals[0], today, 7, 12)
        _check(goals[1], today, 7, 55)
        _check(goals[4], today, 21, 30)

    return streak


def _seed_no_snoozing(today: date) -> Streak:
    streak = create_streak(
        "No snoozing the alarm",
        "#2ec27e",
        PeriodKind.WEEKDAYS,
        ["Up at first alarm"],
        weekdays_mask=0b0011111,
        created_on=date(2026, 8, 27),
    )
    (goal,) = _goals(streak)
    for day in _daterange(date(2026, 8, 27), date(2026, 9, 11)):
        if day.weekday() < 5:
            _check(goal, day, 6, 30)
    return streak


def _seed_gym(today: date) -> Streak:
    streak = create_streak(
        "Gym, three times a week",
        "#9141ac",
        PeriodKind.N_PER_WEEK,
        ["45 min session", "Log the weights"],
        times_per_week=3,
        created_on=date(2026, 7, 13),
    )
    session_goal, log_goal = _goals(streak)
    for day in _daterange(date(2026, 7, 13), date(2026, 9, 4)):
        if day.weekday() in (0, 2, 4):  # Mon, Wed, Fri
            _check(session_goal, day, 18, 30)
            _check(log_goal, day, 19, 20)
    # This week: only Monday and Wednesday, not Friday.
    for day in (date(2026, 9, 7), date(2026, 9, 9)):
        _check(session_goal, day, 18, 30)
        _check(log_goal, day, 19, 20)
    return streak


def _seed_clip_fingernails(today: date) -> Streak:
    streak = create_streak(
        "Clip fingernails",
        "#e5a50a",
        PeriodKind.MONTHLY,
        ["Clip them"],
        created_on=date(2026, 6, 1),
    )
    (goal,) = _goals(streak)
    for month in (6, 7, 8):
        _check(goal, date(2026, month, 5), 19, 0)
    return streak


def _seed_couch_to_5k(today: date) -> Streak:
    streak = create_streak(
        "Couch to 5K",
        "#e01b24",
        PeriodKind.DAILY,
        ["Run"],
        created_on=date(2026, 2, 2),
    )
    (goal,) = _goals(streak)
    for day in _daterange(date(2026, 2, 2), date(2026, 3, 4)):
        _check(goal, day, 7, 0)
    end_streak(streak, date(2026, 3, 4))
    return streak


def seed(today: date = date(2026, 9, 13)) -> dict[str, Streak]:
    """Populate the (already-initialised) database with the design fixture.

    Returns the created streaks keyed by name, in the order the design spec's sidebar shows
    them (creation order also determines each streak's ``position``).
    """
    return {
        "75 Hard": _seed_75_hard(today),
        "No snoozing the alarm": _seed_no_snoozing(today),
        "Gym, three times a week": _seed_gym(today),
        "Clip fingernails": _seed_clip_fingernails(today),
        "Couch to 5K": _seed_couch_to_5k(today),
    }


if __name__ == "__main__":
    from streaks.models import database_path, init_db

    init_db()
    created = seed()
    print(f"Seeded {len(created)} streaks into {database_path()}")
