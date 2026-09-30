"""The design fixture: five illustrative streaks anchored on Sunday 13 September 2026, shared by
the unit test suite (``tests/unit``) and the GUI/screenshot harness (``tests/gui/screens.py``).

Importable (``from fixtures.seed import seed``) and runnable directly
(``python3 tests/fixtures/seed.py``, which initialises the on-disk database at
``$STREAKS_DATA_DIR`` and seeds it).

Five streaks, in sidebar order:

1. **75 Hard** — daily, created 2 Feb 2026, five goals (progress photo, outdoor walk, second
   workout, reading, diet). Run 1 runs 2 Feb-1 Mar, then every day 2 Mar-13 May is answered
   missed. Run 2 runs 14 May-16 Jun, then every day 17 Jun-24 Jul is answered missed. Run 3 runs
   25 Jul to today; within it, a repeating day-index pattern skips the second workout every 7th
   day and checks only three of the five goals every 11th day, so some days land as partial. The
   four days 9-12 September are left with no checks and no answer, so they sit unconfirmed; today
   itself has three of the five goals checked.
2. **No snoozing the alarm** — weekdays (Mon-Fri), created 27 Aug 2026, one goal, checked every
   due day through 11 Sep.
3. **Gym, three times a week** — three sessions a week, created 13 Jul 2026, two goals, both
   checked on Mon/Wed/Fri every week through 4 Sep, except that the weights go unlogged on
   Fridays 24 Jul, 7 Aug and 28 Aug; this week only Monday and Wednesday are checked, leaving
   Friday's session open.
4. **Clip fingernails** — monthly, created 1 Jun 2026, one goal, checked on the 5th of June,
   July and August.
5. **Couch to 5K** — daily, created 2 Feb 2026, ended 4 Mar 2026, one goal checked every day of
   its single run.

Expected values, pinned by ``tests/unit/test_engine.py``:

- 75 Hard: run lengths [28, 34, 51]; run 3 starts 25 Jul with no end, 47 confirmed periods and 4
  unconfirmed, and is the best run; hit rate 94%; all-time goal bars are 109/109, 109/109, 83/109,
  99/109, 109/109; sidebar meta "Daily · 5 goals" at count 51; the banner reads "Four days without a
  check-in — 9 to 12 September"; catch-up lists Wednesday 9 through Saturday 12 September;
  marking today missed would end run 3 at 50 days.
- No snoozing the alarm: count 12, sidebar meta "Mon–Fri", today's card is "Not today" with the
  next check-in on Monday 14 September, since the streak is due only on weekdays.
- Gym, three times a week: count 9, sidebar meta "3× a week · 2 goals", today's card reads "2 of
  3 this week"; goal bars are 45 min session 8/9 and Log the weights 5/9 (low); hit rate 88%.
- Clip fingernails: count 4, sidebar meta "Monthly", today's card is one row, subtitle
  "Monthly · 17 days left".
- Couch to 5K: ended, best run 31 days, sidebar meta "Ended 4 Mar · best 31".
- Today view: title "Sunday 13 September", subtitle "2 check-ins open · 4 earlier days
  unconfirmed" (75 Hard and the gym are open; the four unconfirmed 75 Hard days account for the
  rest). No snoozing the alarm and Clip fingernails also get cards but stay closed today, and
  Couch to 5K, being ended, gets no card at all.

Tests assert these values literally; they pin the fixture against drift.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from streaks.engine import Answer, PeriodKind  # noqa: E402
from streaks.models import (  # noqa: E402
    Goal,
    Streak,
    answer_day,
    create_streak,
    end_streak,
    toggle_goal_check,
)

# The design fixture's pinned "today", shared by the unit and GUI test suites and by
# scripts/render_screens.py.
FIXTURE_TODAY = date(2026, 9, 13)

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
    """Check off "75 Hard"-style daily goals for one run, using a day-index pattern so some days
    are partial.

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


def _seed_no_snoozing() -> Streak:
    streak = create_streak(
        "No snoozing the alarm",
        "#2ec27e",
        PeriodKind.WEEKDAYS,
        ["No snoozing the alarm"],
        weekdays_mask=0b0011111,
        created_on=date(2026, 8, 27),
    )
    (goal,) = _goals(streak)
    for day in _daterange(date(2026, 8, 27), date(2026, 9, 11)):
        if day.weekday() < 5:
            _check(goal, day, 6, 30)
    return streak


def _seed_gym() -> Streak:
    streak = create_streak(
        "Gym, three times a week",
        "#9141ac",
        PeriodKind.N_PER_WEEK,
        ["45 min session", "Log the weights"],
        times_per_week=3,
        created_on=date(2026, 7, 13),
    )
    session_goal, log_goal = _goals(streak)
    unlogged = {date(2026, 7, 24), date(2026, 8, 7), date(2026, 8, 28)}
    for day in _daterange(date(2026, 7, 13), date(2026, 9, 4)):
        if day.weekday() in (0, 2, 4):  # Mon, Wed, Fri
            _check(session_goal, day, 18, 30)
            if day not in unlogged:
                _check(log_goal, day, 19, 20)
    # This week: only Monday and Wednesday, not Friday.
    for day in (date(2026, 9, 7), date(2026, 9, 9)):
        _check(session_goal, day, 18, 30)
        _check(log_goal, day, 19, 20)
    return streak


def _seed_clip_fingernails() -> Streak:
    streak = create_streak(
        "Clip fingernails",
        "#e5a50a",
        PeriodKind.MONTHLY,
        ["Clip fingernails"],
        created_on=date(2026, 6, 1),
    )
    (goal,) = _goals(streak)
    for month in (6, 7, 8):
        _check(goal, date(2026, month, 5), 19, 0)
    return streak


def _seed_couch_to_5k() -> Streak:
    streak = create_streak(
        "Couch to 5K",
        "#e01b24",
        PeriodKind.DAILY,
        ["Couch to 5K"],
        created_on=date(2026, 2, 2),
    )
    (goal,) = _goals(streak)
    for day in _daterange(date(2026, 2, 2), date(2026, 3, 4)):
        _check(goal, day, 7, 0)
    end_streak(streak, date(2026, 3, 4))
    return streak


def seed(today: date = FIXTURE_TODAY) -> dict[str, Streak]:
    """Populate the (already-initialised) database with the design fixture.

    Returns the created streaks keyed by name, in the order the design spec's sidebar shows
    them (creation order also determines each streak's ``position``).
    """
    return {
        "75 Hard": _seed_75_hard(today),
        "No snoozing the alarm": _seed_no_snoozing(),
        "Gym, three times a week": _seed_gym(),
        "Clip fingernails": _seed_clip_fingernails(),
        "Couch to 5K": _seed_couch_to_5k(),
    }


if __name__ == "__main__":
    from streaks.models import database_path, init_db

    init_db()
    created = seed()
    print(f"Seeded {len(created)} streaks into {database_path()}")
