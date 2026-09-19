"""JSON export/import of the whole database.

Used by the Preferences "Export everything" action and, in tests, to check that a dump/restore
round-trips losslessly. No GTK here; ``main``/the preferences dialog own the file dialog and
just call ``dump_json``.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time
from typing import Any

from streaks.models import DayAnswer, Goal, GoalCheck, Streak, db

VERSION = 1


def _iso_or_none(value: date | datetime | time | None) -> str | None:
    return value.isoformat() if value is not None else None


def dump() -> dict[str, Any]:
    """Return every table as JSON-able plain dicts (ISO dates/times), plus a version tag."""
    streaks = [
        {
            "id": s.id,
            "name": s.name,
            "colour": s.colour,
            "period_kind": s.period_kind,
            "weekdays_mask": s.weekdays_mask,
            "times_per_week": s.times_per_week,
            "reminder_time": _iso_or_none(s.reminder_time),
            "allow_skip": s.allow_skip,
            "created_on": s.created_on.isoformat(),
            "ended_on": _iso_or_none(s.ended_on),
            "position": s.position,
        }
        for s in Streak.select().order_by(Streak.id)
    ]
    goals = [
        {
            "id": g.id,
            "streak_id": g.streak_id,
            "name": g.name,
            "position": g.position,
            "removed_on": _iso_or_none(g.removed_on),
        }
        for g in Goal.select().order_by(Goal.id)
    ]
    checks = [
        {
            "id": c.id,
            "goal_id": c.goal_id,
            "day": c.day.isoformat(),
            "done_at": c.done_at.isoformat(),
        }
        for c in GoalCheck.select().order_by(GoalCheck.id)
    ]
    answers = [
        {
            "id": a.id,
            "streak_id": a.streak_id,
            "day": a.day.isoformat(),
            "status": a.status,
            "missed_goal_ids": a.missed_goal_ids,
        }
        for a in DayAnswer.select().order_by(DayAnswer.id)
    ]
    return {
        "version": VERSION,
        "streaks": streaks,
        "goals": goals,
        "checks": checks,
        "answers": answers,
    }


def dump_json(path: str) -> None:
    """Write ``dump()`` to ``path`` as pretty-printed JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dump(), f, indent=2)
        f.write("\n")


def load(data: dict[str, Any]) -> None:
    """Restore ``data`` (as produced by ``dump()``) into an empty database, preserving ids."""
    with db.atomic():
        for row in data.get("streaks", []):
            Streak.create(
                id=row["id"],
                name=row["name"],
                colour=row["colour"],
                period_kind=row["period_kind"],
                weekdays_mask=row["weekdays_mask"],
                times_per_week=row["times_per_week"],
                reminder_time=time.fromisoformat(row["reminder_time"])
                if row["reminder_time"]
                else None,
                allow_skip=row["allow_skip"],
                created_on=date.fromisoformat(row["created_on"]),
                ended_on=date.fromisoformat(row["ended_on"]) if row["ended_on"] else None,
                position=row["position"],
            )
        for row in data.get("goals", []):
            Goal.create(
                id=row["id"],
                streak=row["streak_id"],
                name=row["name"],
                position=row["position"],
                removed_on=date.fromisoformat(row["removed_on"]) if row["removed_on"] else None,
            )
        for row in data.get("checks", []):
            GoalCheck.create(
                id=row["id"],
                goal=row["goal_id"],
                day=date.fromisoformat(row["day"]),
                done_at=datetime.fromisoformat(row["done_at"]),
            )
        for row in data.get("answers", []):
            DayAnswer.create(
                id=row["id"],
                streak=row["streak_id"],
                day=date.fromisoformat(row["day"]),
                status=row["status"],
                missed_goal_ids=row["missed_goal_ids"],
            )
