"""Unit tests for the Peewee data layer (``streaks.models``).

Every test runs against the in-memory database bound by the autouse ``in_memory_db`` fixture in
``tests/unit/conftest.py`` — never the user's real database.
"""

from __future__ import annotations

from datetime import date, datetime, time

import pytest
from peewee import IntegrityError

from streaks.engine import Answer, PeriodKind
from streaks.models import (
    COLOURS,
    SCHEMA_VERSION,
    DatabaseInitError,
    DayAnswer,
    Goal,
    GoalCheck,
    Streak,
    answer_day,
    clear_answer,
    create_streak,
    delete_all,
    delete_streak,
    end_streak,
    init_db,
    load_all,
    load_streak_data,
    reorder_streaks,
    toggle_goal_check,
    update_streak,
)


def test_create_streak_sets_position_and_goal_order():
    s1 = create_streak("A", COLOURS[0], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))
    s2 = create_streak("B", COLOURS[1], PeriodKind.DAILY, ["g1", "g2"], created_on=date(2026, 1, 1))

    assert s1.position == 0
    assert s2.position == 1

    goals = list(Goal.select().where(Goal.streak == s2).order_by(Goal.position))
    assert [g.name for g in goals] == ["g1", "g2"]
    assert [g.position for g in goals] == [0, 1]


def test_create_streak_rejects_empty_name():
    with pytest.raises(ValueError):
        create_streak("  ", COLOURS[0], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))


def test_create_streak_rejects_no_goals():
    with pytest.raises(ValueError):
        create_streak("A", COLOURS[0], PeriodKind.DAILY, ["  ", ""], created_on=date(2026, 1, 1))


def test_create_streak_rejects_bad_colour():
    with pytest.raises(ValueError):
        create_streak("A", "#ffffff", PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))


def test_update_streak_renames_and_reconciles_goals():
    streak = create_streak(
        "A", COLOURS[0], PeriodKind.DAILY, ["g1", "g2"], created_on=date(2026, 1, 1)
    )
    goals = list(Goal.select().where(Goal.streak == streak).order_by(Goal.position))
    g1, g2 = goals

    today = date(2026, 2, 1)
    update_streak(
        streak,
        name="A renamed",
        colour=COLOURS[2],
        period_kind=PeriodKind.WEEKDAYS,
        weekdays_mask=0b0011111,
        times_per_week=3,
        reminder_time=None,
        allow_skip=True,
        goals=[(g1.id, "g1 renamed"), (None, "g3")],
        today=today,
    )

    streak = Streak.get_by_id(streak.id)
    assert streak.name == "A renamed"
    assert streak.colour == COLOURS[2]
    assert streak.period_kind == str(PeriodKind.WEEKDAYS)
    assert streak.allow_skip is True

    g2 = Goal.get_by_id(g2.id)
    assert g2.removed_on == today

    remaining = list(Goal.select().where(Goal.streak == streak).order_by(Goal.position))
    assert [g.name for g in remaining if g.removed_on is None] == ["g1 renamed", "g3"]


def test_update_streak_rejects_empty_name_or_goals():
    streak = create_streak("A", COLOURS[0], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))
    with pytest.raises(ValueError):
        update_streak(
            streak,
            name="",
            colour=COLOURS[0],
            period_kind=PeriodKind.DAILY,
            weekdays_mask=0,
            times_per_week=3,
            reminder_time=None,
            allow_skip=False,
            goals=[(None, "g1")],
            today=date(2026, 1, 2),
        )
    with pytest.raises(ValueError):
        update_streak(
            streak,
            name="A",
            colour=COLOURS[0],
            period_kind=PeriodKind.DAILY,
            weekdays_mask=0,
            times_per_week=3,
            reminder_time=None,
            allow_skip=False,
            goals=[(None, "  ")],
            today=date(2026, 1, 2),
        )


def test_create_streak_single_goal_takes_streak_name(today):
    streak = create_streak("Floss", COLOURS[0], PeriodKind.DAILY, ["floss "], created_on=today)
    assert [g.name for g in streak.goals] == ["Floss"]


def test_update_streak_single_goal_takes_streak_name(today):
    streak = create_streak(
        "Grooming", COLOURS[0], PeriodKind.MONTHLY, ["Clip", "Haircut"], created_on=today
    )
    clip = next(g for g in streak.goals if g.name == "Clip")
    update_streak(
        streak,
        name="Clip fingernails",
        colour=COLOURS[0],
        period_kind=PeriodKind.MONTHLY,
        weekdays_mask=31,
        times_per_week=3,
        reminder_time=None,
        allow_skip=False,
        goals=[(clip.id, "Clip")],
        today=today,
    )
    clip = Goal.get_by_id(clip.id)
    assert clip.name == "Clip fingernails" and clip.removed_on is None


def test_update_streak_single_new_goal_takes_streak_name(today):
    """Replacing every goal with one brand-new one still applies the single-goal invariant."""
    streak = create_streak("A", COLOURS[0], PeriodKind.DAILY, ["g1"], created_on=today)
    old_goal = Goal.get(Goal.streak == streak)
    update_streak(
        streak,
        name="B",
        colour=COLOURS[0],
        period_kind=PeriodKind.DAILY,
        weekdays_mask=31,
        times_per_week=3,
        reminder_time=None,
        allow_skip=False,
        goals=[(None, "new goal")],
        today=today,
    )
    new_goal = Goal.get(Goal.streak == streak, Goal.removed_on.is_null())
    assert new_goal.name == "B"
    assert Goal.get_by_id(old_goal.id).removed_on == today


def test_toggle_goal_check_creates_then_removes():
    streak = create_streak("A", COLOURS[0], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))
    goal = Goal.select().where(Goal.streak == streak).get()
    day = date(2026, 1, 1)
    done_at = datetime(2026, 1, 1, 7, 0)

    assert toggle_goal_check(goal, day, done_at) is True
    assert GoalCheck.select().where(GoalCheck.goal == goal, GoalCheck.day == day).count() == 1

    assert toggle_goal_check(goal, day, done_at) is False
    assert GoalCheck.select().where(GoalCheck.goal == goal, GoalCheck.day == day).count() == 0


def test_goal_check_uniqueness_enforced_at_db_level():
    streak = create_streak("A", COLOURS[0], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))
    goal = Goal.select().where(Goal.streak == streak).get()
    day = date(2026, 1, 1)
    GoalCheck.create(goal=goal, day=day, done_at=datetime(2026, 1, 1, 7, 0))
    with pytest.raises(IntegrityError):
        GoalCheck.create(goal=goal, day=day, done_at=datetime(2026, 1, 1, 8, 0))


def test_day_answer_uniqueness_enforced_at_db_level():
    streak = create_streak("A", COLOURS[0], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))
    day = date(2026, 1, 1)
    DayAnswer.create(streak=streak, day=day, status=str(Answer.KEPT))
    with pytest.raises(IntegrityError):
        DayAnswer.create(streak=streak, day=day, status=str(Answer.MISSED))


def test_answer_day_upserts():
    streak = create_streak("A", COLOURS[0], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))
    day = date(2026, 1, 1)

    answer_day(streak, day, Answer.KEPT)
    assert DayAnswer.select().count() == 1
    assert DayAnswer.get().status == str(Answer.KEPT)

    answer_day(streak, day, Answer.MISSED, missed_goal_ids=[1, 2])
    assert DayAnswer.select().count() == 1
    updated = DayAnswer.get()
    assert updated.status == str(Answer.MISSED)
    assert updated.missed_goal_ids == "[1, 2]"


def test_clear_answer_removes_it():
    streak = create_streak("A", COLOURS[0], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))
    day = date(2026, 1, 1)
    answer_day(streak, day, Answer.KEPT)
    clear_answer(streak, day)
    assert DayAnswer.select().count() == 0


def test_end_streak_sets_ended_on():
    streak = create_streak("A", COLOURS[0], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))
    end_streak(streak, date(2026, 3, 1))
    assert Streak.get_by_id(streak.id).ended_on == date(2026, 3, 1)


def test_delete_streak_cascades():
    streak = create_streak("A", COLOURS[0], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))
    goal = Goal.select().where(Goal.streak == streak).get()
    toggle_goal_check(goal, date(2026, 1, 1), datetime(2026, 1, 1, 7, 0))
    answer_day(streak, date(2026, 1, 2), Answer.MISSED)

    delete_streak(streak)

    assert Streak.select().count() == 0
    assert Goal.select().count() == 0
    assert GoalCheck.select().count() == 0
    assert DayAnswer.select().count() == 0


def test_delete_all_wipes_every_table():
    streak = create_streak("A", COLOURS[0], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))
    goal = Goal.select().where(Goal.streak == streak).get()
    toggle_goal_check(goal, date(2026, 1, 1), datetime(2026, 1, 1, 7, 0))
    answer_day(streak, date(2026, 1, 2), Answer.MISSED)

    delete_all()

    assert Streak.select().count() == 0
    assert Goal.select().count() == 0
    assert GoalCheck.select().count() == 0
    assert DayAnswer.select().count() == 0


def test_reorder_streaks():
    s1 = create_streak("A", COLOURS[0], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))
    s2 = create_streak("B", COLOURS[1], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))
    s3 = create_streak("C", COLOURS[2], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))

    reorder_streaks([s3.id, s1.id, s2.id])

    assert Streak.get_by_id(s3.id).position == 0
    assert Streak.get_by_id(s1.id).position == 1
    assert Streak.get_by_id(s2.id).position == 2


def test_load_streak_data_matches_db_state():
    streak = create_streak(
        "A", COLOURS[0], PeriodKind.DAILY, ["g1", "g2"], created_on=date(2026, 1, 1)
    )
    g1, g2 = list(Goal.select().where(Goal.streak == streak).order_by(Goal.position))
    toggle_goal_check(g1, date(2026, 1, 1), datetime(2026, 1, 1, 7, 0))
    answer_day(streak, date(2026, 1, 2), Answer.MISSED, missed_goal_ids=[g2.id])

    data = load_streak_data(streak)

    assert data.id == streak.id
    assert data.period_kind == PeriodKind.DAILY
    assert [g.name for g in data.goals] == ["g1", "g2"]
    assert len(data.checks) == 1
    assert data.checks[0].goal_id == g1.id
    assert len(data.answers) == 1
    assert data.answers[0].status == Answer.MISSED
    assert data.answers[0].missed_goal_ids == (g2.id,)


def test_load_all_orders_running_then_ended_by_position():
    s1 = create_streak("A", COLOURS[0], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))
    create_streak("B", COLOURS[1], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))
    create_streak("C", COLOURS[2], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))
    end_streak(s1, date(2026, 2, 1))

    result = load_all()

    assert [sd.name for sd in result] == ["B", "C", "A"]


def test_load_all_query_count_bounded(monkeypatch):
    for i in range(3):
        streak = create_streak(
            f"S{i}", COLOURS[0], PeriodKind.DAILY, ["g1", "g2"], created_on=date(2026, 1, 1)
        )
        goals = list(Goal.select().where(Goal.streak == streak))
        for g in goals:
            toggle_goal_check(g, date(2026, 1, 1), datetime(2026, 1, 1, 7, 0))
        answer_day(streak, date(2026, 1, 2), Answer.MISSED)

    from streaks.models import db

    calls = {"n": 0}
    original = db.execute_sql

    def counting_execute_sql(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(db, "execute_sql", counting_execute_sql)

    load_all()

    assert calls["n"] <= 4


def test_reminder_time_round_trips():
    streak = create_streak(
        "A",
        COLOURS[0],
        PeriodKind.DAILY,
        ["g1"],
        created_on=date(2026, 1, 1),
        reminder_time=time(20, 0),
    )
    assert Streak.get_by_id(streak.id).reminder_time == time(20, 0)


def test_reminder_time_round_trips_through_update_streak():
    """Editing a streak round-trips ``reminder_time`` (README › Known gaps: nothing schedules a
    notification from it)."""
    streak = create_streak("A", COLOURS[0], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))
    goal = Goal.get(Goal.streak == streak)

    update_streak(
        streak,
        name="A",
        colour=COLOURS[0],
        period_kind=PeriodKind.DAILY,
        weekdays_mask=0b0011111,
        times_per_week=3,
        reminder_time=time(7, 30),
        allow_skip=False,
        goals=[(goal.id, "g1")],
        today=date(2026, 1, 2),
    )
    assert Streak.get_by_id(streak.id).reminder_time == time(7, 30)

    # Turning it back off round-trips to `None` too.
    update_streak(
        streak,
        name="A",
        colour=COLOURS[0],
        period_kind=PeriodKind.DAILY,
        weekdays_mask=0b0011111,
        times_per_week=3,
        reminder_time=None,
        allow_skip=False,
        goals=[(goal.id, "g1")],
        today=date(2026, 1, 2),
    )
    assert Streak.get_by_id(streak.id).reminder_time is None


def test_init_db_raises_database_init_error_for_unwritable_data_dir(tmp_path, monkeypatch):
    """A path where ``STREAKS_DATA_DIR`` should be a directory but is actually a file raises
    ``DatabaseInitError`` (with the attempted path and a reason), never a raw
    ``OSError``/traceback — ``main.py`` shows this in an ``Adw.AlertDialog`` and quits."""
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("this is a file, not a directory")
    monkeypatch.setenv("STREAKS_DATA_DIR", str(blocked))

    with pytest.raises(DatabaseInitError) as exc_info:
        init_db()

    assert exc_info.value.path == str(blocked)
    assert exc_info.value.reason


def test_init_db_raises_database_init_error_for_corrupt_database_file(tmp_path):
    """A path that exists but isn't a valid SQLite database also raises ``DatabaseInitError``,
    wrapping the ``peewee`` exception so ``main.py`` can show the path and reason in a dialog
    before quitting."""
    from streaks.models import MODELS, db

    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"not a sqlite database" * 10)

    try:
        with pytest.raises(DatabaseInitError) as exc_info:
            init_db(str(corrupt))

        assert exc_info.value.path == str(corrupt)
        assert exc_info.value.reason
    finally:
        # `init_db()` rebinds the module-level `db` to `corrupt` before it fails on
        # `create_tables()` — restore the in-memory database the autouse `in_memory_db` fixture
        # set up, so this test doesn't leak a broken connection into whichever test runs next.
        if not db.is_closed():
            db.close()
        db.init(":memory:", pragmas={"foreign_keys": 1})
        db.connect()
        db.create_tables(MODELS)


def test_init_db_syncs_single_goal_names(tmp_path):
    """A pre-v2 database file with a single-goal streak whose goal name drifted from the
    streak's gets synced on open, and ``user_version`` advances to ``SCHEMA_VERSION``."""
    from streaks.models import MODELS, db

    path = str(tmp_path / "s.db")
    try:
        init_db(path)
        streak = create_streak(
            "Clip fingernails", COLOURS[2], PeriodKind.MONTHLY, ["x"], created_on=date(2026, 6, 1)
        )
        Goal.update(name="Clip them").where(Goal.streak == streak).execute()
        db.pragma("user_version", 1)
        db.close()

        init_db(path)

        assert Goal.get(Goal.streak == streak).name == "Clip fingernails"
        assert db.pragma("user_version") == SCHEMA_VERSION
    finally:
        if not db.is_closed():
            db.close()
        db.init(":memory:", pragmas={"foreign_keys": 1})
        db.connect()
        db.create_tables(MODELS)


def test_init_db_leaves_multi_goal_names(tmp_path):
    """The v2 migration sync only touches single-goal streaks; multi-goal streaks keep their
    goal names untouched."""
    from streaks.models import MODELS, db

    path = str(tmp_path / "s.db")
    try:
        init_db(path)
        streak = create_streak(
            "Grooming",
            COLOURS[0],
            PeriodKind.MONTHLY,
            ["Clip", "Haircut"],
            created_on=date(2026, 6, 1),
        )
        db.pragma("user_version", 1)
        db.close()

        init_db(path)

        names = {g.name for g in Goal.select().where(Goal.streak == streak)}
        assert names == {"Clip", "Haircut"}
        assert db.pragma("user_version") == SCHEMA_VERSION
    finally:
        if not db.is_closed():
            db.close()
        db.init(":memory:", pragmas={"foreign_keys": 1})
        db.connect()
        db.create_tables(MODELS)
