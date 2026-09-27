"""Peewee data layer: SQLite-backed models and the functions that create, read and update them.
``engine.py`` derives runs, statuses and history from the plain-data snapshots these functions
load (``load_all()``/``load_streak_data()``).

``Answer`` and ``PeriodKind`` are defined in ``engine.py`` (which has no dependencies) and
re-exported here so both the database layer and the pure engine can share them without a
circular import.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date, datetime, time

from gi.repository import GLib
from peewee import (
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    ForeignKeyField,
    IntegerField,
    Model,
    PeeweeException,
    SqliteDatabase,
    TextField,
    TimeField,
    fn,
)
from playhouse.migrate import SqliteMigrator, migrate

from streaks.engine import (
    WEEKDAYS_MON_TO_FRI,
    Answer,
    AnswerData,
    CheckData,
    GoalData,
    PeriodKind,
    StreakData,
)

__all__ = [
    "Answer",
    "PeriodKind",
    "COLOURS",
    "db",
    "BaseModel",
    "Streak",
    "Goal",
    "GoalCheck",
    "DayAnswer",
    "database_path",
    "init_db",
    "DatabaseInitError",
    "SCHEMA_VERSION",
    "create_streak",
    "update_streak",
    "toggle_goal_check",
    "answer_day",
    "clear_answer",
    "end_streak",
    "delete_streak",
    "delete_all",
    "reorder_streaks",
    "load_streak_data",
    "load_all",
]

COLOURS = ("#3584e4", "#2ec27e", "#e5a50a", "#e01b24", "#9141ac")

# v2 adds the single-goal name invariant: a streak with exactly one active goal always names
# that goal after the streak (see `create_streak`/`update_streak`/`_sync_single_goal_names`).
# v3 adds `Goal.added_on`, so a goal added mid-streak counts from its own period on instead of
# retroactively changing periods that predate it (see `engine.active_goals`).
SCHEMA_VERSION = 3

db = SqliteDatabase(None)


class BaseModel(Model):
    class Meta:
        database = db


class Streak(BaseModel):
    name = CharField()
    colour = CharField(max_length=7)
    period_kind = CharField()
    weekdays_mask = IntegerField(default=WEEKDAYS_MON_TO_FRI)
    times_per_week = IntegerField(default=3)
    reminder_time = TimeField(null=True)
    allow_skip = BooleanField(default=False)
    created_on = DateField()
    ended_on = DateField(null=True)
    position = IntegerField(default=0)


class Goal(BaseModel):
    streak = ForeignKeyField(Streak, backref="goals", on_delete="CASCADE")
    name = CharField()
    position = IntegerField(default=0)
    removed_on = DateField(null=True)
    added_on = DateField(null=True)  # NULL means "always existed" (rows predating this column)


class GoalCheck(BaseModel):
    goal = ForeignKeyField(Goal, backref="checks", on_delete="CASCADE")
    day = DateField()
    done_at = DateTimeField()

    class Meta:
        indexes = ((("goal", "day"), True),)


class DayAnswer(BaseModel):
    streak = ForeignKeyField(Streak, backref="answers", on_delete="CASCADE")
    day = DateField()
    status = CharField()
    missed_goal_ids = TextField(default="[]")

    class Meta:
        indexes = ((("streak", "day"), True),)


MODELS = (Streak, Goal, GoalCheck, DayAnswer)


class DatabaseInitError(RuntimeError):
    """Raised by ``init_db()`` when the on-disk database can't be created or opened.

    Carries the path that was attempted (even if resolving/creating the data directory itself is
    what failed), wrapping any ``OSError``/``peewee`` exception so ``main.py`` can show the path
    and reason in a dialog before quitting.
    """

    def __init__(self, path: str, reason: str):
        super().__init__(f"can't open the database at {path}: {reason}")
        self.path = path
        self.reason = reason


FLATPAK_INFO_PATH = "/.flatpak-info"


def _is_uninstalled_flatpak_build() -> bool:
    """True when running from ``flatpak build`` (GNOME Builder, ``flatpak-builder --run``)
    rather than an installed app; that instance is marked ``build=true`` in ``/.flatpak-info``."""
    info = GLib.KeyFile()
    try:
        info.load_from_file(FLATPAK_INFO_PATH, GLib.KeyFileFlags.NONE)
        return info.get_boolean("Instance", "build")
    except GLib.Error:
        return False


def _default_data_dir() -> str:
    data_dir = os.environ.get("STREAKS_DATA_DIR")
    if not data_dir:
        # Builder normally uses the `.Devel` manifest, which has its own data dir. This guards
        # against building the release manifest there instead: that shares the installed app's
        # ID, and so its data dir, but must still never open the real database.
        name = "streaks-devel" if _is_uninstalled_flatpak_build() else "streaks"
        data_dir = os.path.join(GLib.get_user_data_dir(), name)
    return data_dir


def database_path() -> str:
    """Resolve the sandboxed on-disk database path, creating its directory.

    Raises ``DatabaseInitError`` if the data directory can't be created (e.g. a file already
    sits where the directory should be).
    """
    data_dir = _default_data_dir()
    try:
        os.makedirs(data_dir, exist_ok=True)
    except OSError as exc:
        raise DatabaseInitError(data_dir, str(exc)) from exc
    return os.path.join(data_dir, "streaks.db")


def init_db(path: str | None = None) -> SqliteDatabase:
    """Initialise the module-level production database and create tables if needed.

    Raises ``DatabaseInitError``, wrapping any ``OSError``/``peewee`` exception so ``main.py``
    can show the path and reason in a dialog before quitting, if the path can't be resolved,
    opened, or written to — e.g. a corrupt file or one sitting where the data directory should
    be.
    """
    if path is None:
        path = database_path()
    try:
        db.init(path, pragmas={"foreign_keys": 1, "journal_mode": "wal"})
        db.connect(reuse_if_open=True)
        db.create_tables(MODELS)
        if db.pragma("user_version") < SCHEMA_VERSION:
            _add_goal_added_on_column()
            _sync_single_goal_names()
            db.pragma("user_version", SCHEMA_VERSION)
    except (OSError, PeeweeException) as exc:
        raise DatabaseInitError(path, str(exc)) from exc
    return db


def _sync_single_goal_names() -> None:
    """Bring a database up to the single-goal name invariant: for every streak with exactly one
    active goal, rename that goal to match the streak's name."""
    with db.atomic():
        for streak in Streak.select():
            active_goals = list(
                Goal.select().where(Goal.streak == streak, Goal.removed_on.is_null())
            )
            if len(active_goals) == 1 and active_goals[0].name != streak.name:
                active_goals[0].name = streak.name
                active_goals[0].save()


def _add_goal_added_on_column() -> None:
    """Bring a pre-v3 database up to the v3 schema: add `Goal.added_on` if it isn't already
    there. A fresh database created by `create_tables` already has it."""
    existing_columns = {c.name for c in db.get_columns("goal")}
    if "added_on" not in existing_columns:
        migrator = SqliteMigrator(db)
        migrate(migrator.add_column("goal", "added_on", Goal.added_on))


def create_streak(
    name: str,
    colour: str,
    period_kind: PeriodKind | str,
    goals: list[str],
    *,
    weekdays_mask: int = WEEKDAYS_MON_TO_FRI,
    times_per_week: int = 3,
    reminder_time: time | None = None,
    allow_skip: bool = False,
    created_on: date,
) -> Streak:
    """Create a streak with its goals in one transaction.

    A one-goal streak stores its goal under the streak's name.
    """
    name = name.strip()
    if not name:
        raise ValueError("name must not be empty")
    goal_names = [g.strip() for g in goals if g.strip()]
    if not goal_names:
        raise ValueError("at least one goal is required")
    if len(goal_names) == 1:
        goal_names = [name]
    if colour not in COLOURS:
        raise ValueError(f"invalid colour: {colour}")
    with db.atomic():
        max_position = Streak.select(fn.MAX(Streak.position)).scalar()
        position = 0 if max_position is None else max_position + 1
        streak = Streak.create(
            name=name,
            colour=colour,
            period_kind=str(period_kind),
            weekdays_mask=weekdays_mask,
            times_per_week=times_per_week,
            reminder_time=reminder_time,
            allow_skip=allow_skip,
            created_on=created_on,
            position=position,
        )
        for i, goal_name in enumerate(goal_names):
            Goal.create(streak=streak, name=goal_name, position=i, added_on=created_on)
    return streak


def update_streak(
    streak: Streak,
    *,
    name: str,
    colour: str,
    period_kind: PeriodKind | str,
    weekdays_mask: int,
    times_per_week: int,
    reminder_time: time | None,
    allow_skip: bool,
    goals: list[tuple[int | None, str]],
    today: date,
) -> Streak:
    """Update a streak's fields and reconcile its goal list.

    A one-goal streak stores its goal under the streak's name.
    """
    name = name.strip()
    if not name:
        raise ValueError("name must not be empty")
    if colour not in COLOURS:
        raise ValueError(f"invalid colour: {colour}")
    goal_entries = [(gid, gname.strip()) for gid, gname in goals if gname.strip()]
    if not goal_entries:
        raise ValueError("at least one goal is required")
    if len(goal_entries) == 1:
        goal_entries = [(goal_entries[0][0], name)]
    with db.atomic():
        streak.name = name
        streak.colour = colour
        streak.period_kind = str(period_kind)
        streak.weekdays_mask = weekdays_mask
        streak.times_per_week = times_per_week
        streak.reminder_time = reminder_time
        streak.allow_skip = allow_skip
        streak.save()

        existing_ids = {g.id for g in streak.goals if g.removed_on is None}
        kept_ids = {gid for gid, _ in goal_entries if gid is not None}
        removed_ids = existing_ids - kept_ids
        if removed_ids:
            Goal.update(removed_on=today).where(Goal.id.in_(removed_ids)).execute()
        for position, (gid, goal_name) in enumerate(goal_entries):
            if gid is None:
                Goal.create(streak=streak, name=goal_name, position=position, added_on=today)
            else:
                Goal.update(name=goal_name, position=position).where(Goal.id == gid).execute()
    return streak


def toggle_goal_check(goal: Goal, day: date, done_at: datetime) -> bool:
    """Create the check for ``day`` if absent, else remove it. Returns the new state."""
    with db.atomic():
        existing = GoalCheck.get_or_none(GoalCheck.goal == goal, GoalCheck.day == day)
        if existing is not None:
            existing.delete_instance()
            return False
        GoalCheck.create(goal=goal, day=day, done_at=done_at)
        return True


def answer_day(
    streak: Streak, day: date, status: Answer, missed_goal_ids: list[int] = ()
) -> DayAnswer:
    """Upsert the answer for ``day``."""
    with db.atomic():
        answer, created = DayAnswer.get_or_create(
            streak=streak,
            day=day,
            defaults={
                "status": str(status),
                "missed_goal_ids": json.dumps(list(missed_goal_ids)),
            },
        )
        if not created:
            answer.status = str(status)
            answer.missed_goal_ids = json.dumps(list(missed_goal_ids))
            answer.save()
        return answer


def clear_answer(streak: Streak, day: date) -> None:
    """Remove any answer recorded for ``day``."""
    DayAnswer.delete().where(DayAnswer.streak == streak, DayAnswer.day == day).execute()


def end_streak(streak: Streak, on: date) -> None:
    """Mark a streak as ended."""
    streak.ended_on = on
    streak.save()


def delete_streak(streak: Streak) -> None:
    """Delete a streak and (via ``ON DELETE CASCADE``) its goals/checks/answers."""
    streak.delete_instance()


def delete_all() -> None:
    """Wipe every table. Used by the Preferences 'Delete all data' action and tests."""
    with db.atomic():
        DayAnswer.delete().execute()
        GoalCheck.delete().execute()
        Goal.delete().execute()
        Streak.delete().execute()


def reorder_streaks(ids: list[int]) -> None:
    """Rewrite streak positions to match the given id order."""
    with db.atomic():
        for position, streak_id in enumerate(ids):
            Streak.update(position=position).where(Streak.id == streak_id).execute()


def _build_streak_data(
    streak: Streak,
    goals: list[Goal],
    checks_by_goal: dict[int, list[GoalCheck]],
    answers: list[DayAnswer],
) -> StreakData:
    goal_data = tuple(
        GoalData(
            id=g.id,
            name=g.name,
            position=g.position,
            removed_on=g.removed_on,
            added_on=g.added_on,
        )
        for g in goals
    )
    check_data = tuple(
        sorted(
            (
                CheckData(goal_id=c.goal_id, day=c.day, done_at=c.done_at)
                for g in goals
                for c in checks_by_goal.get(g.id, [])
            ),
            key=lambda c: (c.day, c.goal_id),
        )
    )
    answer_data = tuple(
        sorted(
            (
                AnswerData(
                    day=a.day,
                    status=Answer(a.status),
                    missed_goal_ids=tuple(json.loads(a.missed_goal_ids)),
                )
                for a in answers
            ),
            key=lambda a: a.day,
        )
    )
    return StreakData(
        id=streak.id,
        name=streak.name,
        colour=streak.colour,
        period_kind=PeriodKind(streak.period_kind),
        weekdays_mask=streak.weekdays_mask,
        times_per_week=streak.times_per_week,
        reminder_time=streak.reminder_time,
        allow_skip=streak.allow_skip,
        created_on=streak.created_on,
        ended_on=streak.ended_on,
        position=streak.position,
        goals=goal_data,
        checks=check_data,
        answers=answer_data,
    )


def load_streak_data(streak: Streak) -> StreakData:
    """Load one streak's plain-data snapshot for the engine."""
    goals = list(Goal.select().where(Goal.streak == streak).order_by(Goal.position))
    goal_ids = [g.id for g in goals]
    checks_by_goal: dict[int, list[GoalCheck]] = defaultdict(list)
    if goal_ids:
        for check in GoalCheck.select().where(GoalCheck.goal_id.in_(goal_ids)):
            checks_by_goal[check.goal_id].append(check)
    answers = list(DayAnswer.select().where(DayAnswer.streak == streak))
    return _build_streak_data(streak, goals, checks_by_goal, answers)


def load_all() -> list[StreakData]:
    """Load every streak's plain-data snapshot in at most 4 queries.

    Running streaks come first (ordered by position), then ended streaks.
    """
    streaks = list(Streak.select())
    streak_ids = [s.id for s in streaks]

    goals_by_streak: dict[int, list[Goal]] = defaultdict(list)
    if streak_ids:
        for goal in Goal.select().where(Goal.streak_id.in_(streak_ids)).order_by(Goal.position):
            goals_by_streak[goal.streak_id].append(goal)

    goal_ids = [g.id for goals in goals_by_streak.values() for g in goals]
    checks_by_goal: dict[int, list[GoalCheck]] = defaultdict(list)
    if goal_ids:
        for check in GoalCheck.select().where(GoalCheck.goal_id.in_(goal_ids)):
            checks_by_goal[check.goal_id].append(check)

    answers_by_streak: dict[int, list[DayAnswer]] = defaultdict(list)
    if streak_ids:
        for answer in DayAnswer.select().where(DayAnswer.streak_id.in_(streak_ids)):
            answers_by_streak[answer.streak_id].append(answer)

    result = [
        _build_streak_data(
            s, goals_by_streak.get(s.id, []), checks_by_goal, answers_by_streak.get(s.id, [])
        )
        for s in streaks
    ]
    result.sort(key=lambda sd: (sd.ended_on is not None, sd.position))
    return result
