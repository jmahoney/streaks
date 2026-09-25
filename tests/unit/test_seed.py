"""Unit tests for the design fixture itself (``tests/fixtures/seed.py``).

Counts were derived by running the fixture and counting rows; they pin it against drift.
"""

from __future__ import annotations

from datetime import date

from streaks.models import DayAnswer, Goal, GoalCheck, Streak


def test_seed_creates_five_streaks_and_ten_goals(seeded):
    assert len(seeded) == 5
    assert Streak.select().count() == 5
    assert Goal.select().count() == 10


def test_seed_streak_names_and_positions(seeded):
    streaks = list(Streak.select().order_by(Streak.position))
    assert [s.name for s in streaks] == [
        "75 Hard",
        "No snoozing the alarm",
        "Gym, three times a week",
        "Clip fingernails",
        "Couch to 5K",
    ]


def test_seed_goal_counts_per_streak(seeded):
    expected_goal_counts = {
        "75 Hard": 5,
        "No snoozing the alarm": 1,
        "Gym, three times a week": 2,
        "Clip fingernails": 1,
        "Couch to 5K": 1,
    }
    for name, streak in seeded.items():
        assert Goal.select().where(Goal.streak == streak).count() == expected_goal_counts[name]


def test_seed_check_counts_per_streak(seeded):
    expected_check_counts = {
        "75 Hard": 509,
        "No snoozing the alarm": 12,
        "Gym, three times a week": 52,
        "Clip fingernails": 3,
        "Couch to 5K": 31,
    }
    for name, streak in seeded.items():
        goal_ids = [g.id for g in Goal.select().where(Goal.streak == streak)]
        count = GoalCheck.select().where(GoalCheck.goal_id.in_(goal_ids)).count()
        assert count == expected_check_counts[name], name
    assert GoalCheck.select().count() == 607


def test_seed_answer_counts(seeded):
    hard = seeded["75 Hard"]
    hard_answers = DayAnswer.select().where(DayAnswer.streak == hard).count()
    # 2 Mar - 13 May and 17 Jun - 24 Jul, every day, answered missed.
    assert hard_answers == 111
    assert DayAnswer.select().count() == 111
    for name, streak in seeded.items():
        if name == "75 Hard":
            continue
        assert DayAnswer.select().where(DayAnswer.streak == streak).count() == 0


def test_seed_streak_attributes(seeded):
    from streaks.engine import PeriodKind

    expected = {
        "75 Hard": ("#3584e4", PeriodKind.DAILY, date(2026, 2, 2), None),
        "No snoozing the alarm": ("#2ec27e", PeriodKind.WEEKDAYS, date(2026, 8, 27), None),
        "Gym, three times a week": (
            "#9141ac",
            PeriodKind.N_PER_WEEK,
            date(2026, 7, 13),
            None,
        ),
        "Clip fingernails": ("#e5a50a", PeriodKind.MONTHLY, date(2026, 6, 1), None),
        "Couch to 5K": ("#e01b24", PeriodKind.DAILY, date(2026, 2, 2), date(2026, 3, 4)),
    }
    for name, (colour, period_kind, created_on, ended_on) in expected.items():
        streak = seeded[name]
        assert streak.colour == colour, name
        assert streak.period_kind == str(period_kind), name
        assert streak.created_on == created_on, name
        assert streak.ended_on == ended_on, name


def test_seed_goal_names_in_order(seeded):
    hard_goals = [
        g.name
        for g in Goal.select().where(Goal.streak == seeded["75 Hard"]).order_by(Goal.position)
    ]
    assert hard_goals == [
        "Progress photo",
        "45 min outdoors",
        "45 min second workout",
        "Read 10 pages",
        "Stick to the diet",
    ]
    gym_goals = [
        g.name
        for g in Goal.select()
        .where(Goal.streak == seeded["Gym, three times a week"])
        .order_by(Goal.position)
    ]
    assert gym_goals == ["45 min session", "Log the weights"]


def test_seed_single_goal_streaks_take_streak_name(seeded):
    for name in ("No snoozing the alarm", "Clip fingernails", "Couch to 5K"):
        streak = seeded[name]
        (goal,) = Goal.select().where(Goal.streak == streak)
        assert goal.name == name
