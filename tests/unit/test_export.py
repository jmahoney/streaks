"""Unit tests for ``streaks.export``: a dump/delete_all/load round trip must be lossless."""

from __future__ import annotations

from datetime import date

from streaks import export
from streaks.models import delete_all


def test_dump_is_empty_for_a_fresh_database():
    data = export.dump()
    assert data == {"version": 1, "streaks": [], "goals": [], "checks": [], "answers": []}


def test_dump_delete_all_load_round_trips(seeded, today):
    before = export.dump()
    assert before["streaks"]  # sanity: the fixture actually seeded something
    assert before["goals"]
    assert before["checks"]
    assert before["answers"]

    delete_all()
    assert export.dump() == {"version": 1, "streaks": [], "goals": [], "checks": [], "answers": []}

    export.load(before)
    after = export.dump()

    assert after == before


def test_dump_json_writes_a_file(seeded, tmp_path):
    path = tmp_path / "export.json"
    export.dump_json(str(path))

    import json

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    assert data == export.dump()


def test_dump_load_round_trips_goal_added_on():
    from streaks.models import COLOURS, PeriodKind, create_streak, update_streak

    streak = create_streak("A", COLOURS[0], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))
    update_streak(
        streak,
        name="A",
        colour=COLOURS[0],
        period_kind=PeriodKind.DAILY,
        weekdays_mask=31,
        times_per_week=3,
        reminder_time=None,
        allow_skip=False,
        goals=[(g.id, "g1") for g in streak.goals] + [(None, "g2")],
        today=date(2026, 2, 1),
    )

    before = export.dump()
    added_ons = {g["name"]: g["added_on"] for g in before["goals"]}
    assert added_ons == {"g1": "2026-01-01", "g2": "2026-02-01"}

    delete_all()
    export.load(before)
    after = export.dump()

    assert after == before


def test_load_preserves_ended_on_and_reminder_time():
    from streaks.models import COLOURS, PeriodKind, create_streak, end_streak

    streak = create_streak("A", COLOURS[0], PeriodKind.DAILY, ["g1"], created_on=date(2026, 1, 1))
    end_streak(streak, date(2026, 2, 1))

    before = export.dump()
    delete_all()
    export.load(before)
    after = export.dump()

    assert after == before
    assert after["streaks"][0]["ended_on"] == "2026-02-01"
