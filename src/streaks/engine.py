"""Pure engine: streak/run/history computation over plain data.

No GTK, no Peewee. Everything here operates on the frozen dataclasses below, which the
database layer (``models.py``) builds from its ORM rows. ``evaluate()`` is the single
source of per-period truth for a streak; every other function either calls it once and
reuses the result, or calls ``runs()`` (which itself calls ``evaluate()`` once).
"""

from __future__ import annotations

import bisect
import calendar
import dataclasses
import gettext
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from typing import Literal

from streaks import words

_ = gettext.gettext
ngettext = gettext.ngettext


# --------------------------------------------------------------------------------------
# Enums shared with the database layer (defined here, since this module has no
# dependencies, and re-exported from models.py to avoid a circular import).
# --------------------------------------------------------------------------------------


class PeriodKind(StrEnum):
    DAILY = "daily"
    WEEKDAYS = "weekdays"
    N_PER_WEEK = "n_per_week"
    MONTHLY = "monthly"


class Answer(StrEnum):
    KEPT = "kept"
    MISSED = "missed"


class Status(StrEnum):
    KEPT = "kept"
    PARTIAL = "partial"
    UNCONFIRMED = "unconfirmed"
    MISSED = "missed"
    OPEN = "open"
    NOT_DUE = "not_due"
    UPCOMING = "upcoming"


# --------------------------------------------------------------------------------------
# Plain data mirrors of the database rows.
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class GoalData:
    id: int
    name: str
    position: int
    removed_on: date | None


@dataclass(frozen=True)
class CheckData:
    goal_id: int
    day: date
    done_at: datetime


@dataclass(frozen=True)
class AnswerData:
    day: date
    status: Answer
    missed_goal_ids: tuple[int, ...]


@dataclass(frozen=True)
class StreakData:
    id: int
    name: str
    colour: str
    period_kind: PeriodKind
    weekdays_mask: int
    times_per_week: int
    reminder_time: time | None
    allow_skip: bool
    created_on: date
    ended_on: date | None
    position: int
    goals: tuple[GoalData, ...]
    checks: tuple[CheckData, ...]
    answers: tuple[AnswerData, ...]


@dataclass(frozen=True)
class Settings:
    day_start_minutes: int = 240
    backfill_days: int = 2
    count_through_unconfirmed: bool = True
    show_ended: bool = True


@dataclass(frozen=True)
class Period:
    start: date
    end: date


@dataclass(frozen=True)
class PeriodResult:
    period: Period
    status: Status
    done: int
    total: int

    @property
    def ratio(self) -> float:
        return self.done / self.total if self.total else 0.0


@dataclass(frozen=True)
class Run:
    index: int
    start: date
    end: date | None
    length: int
    confirmed: int
    unconfirmed: int
    is_best: bool
    periods: tuple[PeriodResult, ...]


@dataclass(frozen=True)
class Cell:
    fill: str
    border: str | None
    tooltip: str


@dataclass(frozen=True)
class CardGoal:
    goal_id: int
    name: str
    done_at: datetime | None
    trailing: str | None


@dataclass(frozen=True)
class Card:
    streak_id: int
    name: str
    colour: str
    meta: str
    kind: Literal["goals", "not_due", "monthly"]
    goals: list[CardGoal]
    progress: float | None
    progress_text: str | None
    show_footer: bool
    body: str | None


@dataclass(frozen=True)
class Banner:
    streak_id: int
    title: str
    body: str
    strip: list[Cell]


@dataclass(frozen=True)
class TodayView:
    title: str
    subtitle: str
    open_count: int
    banners: list[Banner]
    cards: list[Card]


@dataclass(frozen=True)
class History:
    header_subtitle: str
    tiles: list[tuple[str, str, str]]
    chart_title: str
    is_best: bool
    weeks: list[list[Cell]]
    day_labels: list[str]
    legend: list[tuple[str, str | None, str]]
    catch_up_link: str | None
    goal_bars: list[tuple[str, float, str, bool]]
    earlier_runs: list[tuple[str, str, list[Cell], int]]


@dataclass(frozen=True)
class CatchUp:
    subtitle: str
    days: list[tuple[date, str]]


@dataclass(frozen=True)
class Preview:
    row_state: dict[date, str]
    row_warning: dict[date, str]
    strip: list[Cell]
    summary: str


# --------------------------------------------------------------------------------------
# Chart colours (design-spec "Chart cell colour scale").
# --------------------------------------------------------------------------------------

CHART_ZERO = "#e9e9e7"
CHART_LOW = "#cfe2f8"
CHART_MID = "#92bdf0"
CHART_HIGH = "#4b8fdb"
CHART_FULL = "#1a68c7"
CHART_WHITE = "#ffffff"
CHART_UNCONFIRMED_BORDER = "#a9c9ef"
CHART_MISSED = "#f3c0c4"
CHART_UPCOMING = "#f4f4f2"


# --------------------------------------------------------------------------------------
# Due periods.
# --------------------------------------------------------------------------------------


def _daterange(a: date, b: date):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def _week_periods(created_on: date, end: date) -> list[Period]:
    start = created_on - timedelta(days=created_on.weekday())
    last_week_start = end - timedelta(days=end.weekday())
    periods = []
    w = start
    while w <= last_week_start:
        periods.append(Period(w, w + timedelta(days=6)))
        w += timedelta(days=7)
    return periods


def _month_periods(created_on: date, end: date) -> list[Period]:
    periods = []
    y, m = created_on.year, created_on.month
    while (y, m) <= (end.year, end.month):
        last_day = calendar.monthrange(y, m)[1]
        periods.append(Period(date(y, m, 1), date(y, m, last_day)))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return periods


def due_periods(streak: StreakData, today: date) -> list[Period]:
    """All periods due for this streak, from creation through today (or ``ended_on``)."""
    end = streak.ended_on or today
    if end < streak.created_on:
        return []
    if streak.period_kind == PeriodKind.DAILY:
        return [Period(d, d) for d in _daterange(streak.created_on, end)]
    if streak.period_kind == PeriodKind.WEEKDAYS:
        return [
            Period(d, d)
            for d in _daterange(streak.created_on, end)
            if streak.weekdays_mask & (1 << d.weekday())
        ]
    if streak.period_kind == PeriodKind.N_PER_WEEK:
        return _week_periods(streak.created_on, end)
    if streak.period_kind == PeriodKind.MONTHLY:
        return _month_periods(streak.created_on, end)
    raise ValueError(f"unknown period kind: {streak.period_kind}")


def period_for(streak: StreakData, day: date) -> Period | None:
    """The period containing ``day``, or ``None`` if the streak isn't due that day."""
    if day < streak.created_on:
        return None
    if streak.ended_on is not None and day > streak.ended_on:
        return None
    if streak.period_kind == PeriodKind.DAILY:
        return Period(day, day)
    if streak.period_kind == PeriodKind.WEEKDAYS:
        if not (streak.weekdays_mask & (1 << day.weekday())):
            return None
        return Period(day, day)
    if streak.period_kind == PeriodKind.N_PER_WEEK:
        start = day - timedelta(days=day.weekday())
        return Period(start, start + timedelta(days=6))
    if streak.period_kind == PeriodKind.MONTHLY:
        last_day = calendar.monthrange(day.year, day.month)[1]
        return Period(date(day.year, day.month, 1), date(day.year, day.month, last_day))
    raise ValueError(f"unknown period kind: {streak.period_kind}")


def is_due(streak: StreakData, day: date) -> bool:
    """Whether the streak has an active period covering ``day``."""
    if day < streak.created_on:
        return False
    if streak.ended_on is not None and day > streak.ended_on:
        return False
    if streak.period_kind == PeriodKind.WEEKDAYS:
        return bool(streak.weekdays_mask & (1 << day.weekday()))
    return True


def next_due_day(streak: StreakData, after: date) -> date:
    """The next day (after ``after``) the streak is due."""
    d = after + timedelta(days=1)
    if streak.period_kind == PeriodKind.WEEKDAYS:
        while not (streak.weekdays_mask & (1 << d.weekday())):
            d += timedelta(days=1)
    return d


def active_goals(streak: StreakData, period: Period) -> tuple[GoalData, ...]:
    """Goals that existed for (at least part of) ``period``, in position order."""
    return tuple(
        sorted(
            (g for g in streak.goals if g.removed_on is None or g.removed_on > period.start),
            key=lambda g: g.position,
        )
    )


# --------------------------------------------------------------------------------------
# evaluate() — the single per-period pass.
# --------------------------------------------------------------------------------------


def _checks_by_goal(streak: StreakData) -> dict[int, list[date]]:
    m: dict[int, list[date]] = defaultdict(list)
    for c in streak.checks:
        m[c.goal_id].append(c.day)
    for days in m.values():
        days.sort()
    return m


def _has_check_on(days: list[date], d: date) -> bool:
    i = bisect.bisect_left(days, d)
    return i < len(days) and days[i] == d


def _has_check_in_range(days: list[date], start: date, end: date) -> bool:
    i = bisect.bisect_left(days, start)
    return i < len(days) and days[i] <= end


def _period_totals(
    streak: StreakData,
    period: Period,
    goals: tuple[GoalData, ...],
    checks_by_goal: dict[int, list[date]],
) -> tuple[int, int]:
    if streak.period_kind == PeriodKind.N_PER_WEEK:
        total = streak.times_per_week
        if not goals:
            return 0, total
        done = 0
        d = period.start
        while d <= period.end:
            if all(_has_check_on(checks_by_goal.get(g.id, []), d) for g in goals):
                done += 1
            d += timedelta(days=1)
        return done, total
    total = len(goals)
    done = sum(
        1
        for g in goals
        if _has_check_in_range(checks_by_goal.get(g.id, []), period.start, period.end)
    )
    return done, total


def _find_answer(period: Period, answers_by_day: dict[date, AnswerData]) -> AnswerData | None:
    d = period.start
    while d <= period.end:
        if d in answers_by_day:
            return answers_by_day[d]
        d += timedelta(days=1)
    return None


def evaluate(streak: StreakData, today: date, settings: Settings) -> list[PeriodResult]:
    """Compute the status of every due period for this streak. Call this once and reuse."""
    periods = due_periods(streak, today)
    answers_by_day = {a.day: a for a in streak.answers}
    checks_by_goal = _checks_by_goal(streak)

    results: list[PeriodResult] = []
    for period in periods:
        goals = active_goals(streak, period)
        done, total = _period_totals(streak, period, goals, checks_by_goal)
        answer = _find_answer(period, answers_by_day)
        if answer is not None:
            if answer.status == Answer.MISSED:
                status = Status.MISSED
            else:
                # An explicit "Kept" answer means every goal was done that day, whether or
                # not the goals were ticked individually (catch-up: "All five goals").
                status = Status.KEPT
                done = max(done, total)
            results.append(PeriodResult(period, status, done, total))
            continue

        is_current = period.start <= today <= period.end
        if is_current:
            if done == 0:
                status = Status.OPEN
            elif total and done >= total:
                status = Status.KEPT
            else:
                status = Status.PARTIAL
        else:
            if total and done >= total:
                status = Status.KEPT
            elif done > 0:
                status = Status.PARTIAL
            else:
                status = Status.UNCONFIRMED
        results.append(PeriodResult(period, status, done, total))
    return results


# --------------------------------------------------------------------------------------
# Runs.
# --------------------------------------------------------------------------------------


def _effective_missed(
    streak: StreakData, results: list[PeriodResult], today: date, settings: Settings
) -> list[bool]:
    effective = [False] * len(results)
    forgiven_weeks: set[tuple[int, int]] = set()
    for i, pr in enumerate(results):
        hard = pr.status == Status.MISSED
        if not hard and not settings.count_through_unconfirmed and pr.status == Status.UNCONFIRMED:
            if (today - pr.period.end).days > settings.backfill_days:
                hard = True
        if hard and pr.status == Status.MISSED and streak.allow_skip:
            week_key = pr.period.start.isocalendar()[:2]
            prev_hard = i > 0 and effective[i - 1]
            if week_key not in forgiven_weeks and not prev_hard:
                forgiven_weeks.add(week_key)
                hard = False
        effective[i] = hard
    return effective


def _finalize_run(periods_in_run: list[PeriodResult], index: int, ended: bool) -> Run:
    confirmed = sum(1 for pr in periods_in_run if pr.status in (Status.KEPT, Status.PARTIAL))
    unconfirmed = sum(1 for pr in periods_in_run if pr.status == Status.UNCONFIRMED)
    start = periods_in_run[0].period.start
    end_date = periods_in_run[-1].period.end if ended else None
    return Run(
        index=index,
        start=start,
        end=end_date,
        length=len(periods_in_run),
        confirmed=confirmed,
        unconfirmed=unconfirmed,
        is_best=False,
        periods=tuple(periods_in_run),
    )


def runs(streak: StreakData, today: date, settings: Settings) -> list[Run]:
    """All runs for this streak, chronological, numbered from 1."""
    results = evaluate(streak, today, settings)
    if not results:
        return []

    effective_missed = _effective_missed(streak, results, today, settings)

    run_list: list[Run] = []
    bucket: list[PeriodResult] = []
    for pr, missed in zip(results, effective_missed, strict=True):
        if missed:
            if bucket:
                run_list.append(_finalize_run(bucket, len(run_list) + 1, ended=True))
                bucket = []
            continue
        bucket.append(pr)
    if bucket:
        run_list.append(_finalize_run(bucket, len(run_list) + 1, ended=streak.ended_on is not None))

    if run_list:
        max_len = max(r.length for r in run_list)
        best_i = max(i for i, r in enumerate(run_list) if r.length == max_len)
        run_list = [
            dataclasses.replace(r, is_best=True) if i == best_i else r
            for i, r in enumerate(run_list)
        ]
    return run_list


def current_run(streak: StreakData, today: date, settings: Settings) -> Run | None:
    """The open run, if any. Ended streaks never have one."""
    if streak.ended_on is not None:
        return None
    for r in runs(streak, today, settings):
        if r.end is None:
            return r
    return None


def best_run(streak: StreakData, today: date, settings: Settings) -> Run | None:
    for r in runs(streak, today, settings):
        if r.is_best:
            return r
    return None


def sidebar_count(streak: StreakData, today: date, settings: Settings) -> int:
    """The number shown next to a streak in the sidebar."""
    if streak.ended_on is not None:
        b = best_run(streak, today, settings)
        return b.length if b else 0
    c = current_run(streak, today, settings)
    return c.length if c else 0


# --------------------------------------------------------------------------------------
# Sidebar meta strings.
# --------------------------------------------------------------------------------------


def _weekday_label(mask: int) -> str:
    days = [i for i in range(7) if mask & (1 << i)]
    if not days:
        return ""
    names = [words.weekday_names_short[i] for i in days]
    if len(days) == 1:
        return names[0]
    if days == list(range(days[0], days[-1] + 1)):
        return f"{names[0]}–{names[-1]}"
    return ", ".join(names)


def _goal_word(n: int) -> str:
    return ngettext("%(n)d goal", "%(n)d goals", n) % {"n": n}


def sidebar_meta(streak: StreakData) -> str:
    n = sum(1 for g in streak.goals if g.removed_on is None)
    goal_word = _goal_word(n)
    if streak.period_kind == PeriodKind.DAILY:
        return _("Daily · %(goals)s") % {"goals": goal_word}
    if streak.period_kind == PeriodKind.WEEKDAYS:
        label = _weekday_label(streak.weekdays_mask)
        return _("%(days)s · %(goals)s") % {"days": label, "goals": goal_word}
    if streak.period_kind == PeriodKind.N_PER_WEEK:
        return _("%(n)d× a week · %(goals)s") % {
            "n": streak.times_per_week,
            "goals": goal_word,
        }
    if streak.period_kind == PeriodKind.MONTHLY:
        return _("Monthly · %(goals)s") % {"goals": goal_word}
    raise ValueError(f"unknown period kind: {streak.period_kind}")


def sidebar_ended_meta(streak: StreakData, best: int) -> str:
    return _("Ended %(date)s · best %(best)d") % {
        "date": words.fmt_day_short(streak.ended_on),
        "best": best,
    }


# --------------------------------------------------------------------------------------
# Chart cells.
# --------------------------------------------------------------------------------------


def _tooltip_for(pr: PeriodResult) -> str:
    if pr.status == Status.MISSED:
        return _("missed — run ended")
    if pr.status == Status.UNCONFIRMED or (pr.status == Status.OPEN and pr.done == 0):
        return _("no check-in yet — unconfirmed")
    return ngettext("%(done)d of %(n)d goal", "%(done)d of %(n)d goals", pr.total) % {
        "done": pr.done,
        "n": pr.total,
    }


def _cell_for_result(pr: PeriodResult) -> Cell:
    if pr.status == Status.MISSED:
        return Cell(CHART_MISSED, None, _tooltip_for(pr))
    if pr.status == Status.UNCONFIRMED or (pr.status == Status.OPEN and pr.done == 0):
        return Cell(CHART_WHITE, CHART_UNCONFIRMED_BORDER, _tooltip_for(pr))
    ratio = pr.ratio
    if ratio == 0:
        fill = CHART_ZERO
    elif ratio < 0.3:
        fill = CHART_LOW
    elif ratio < 0.6:
        fill = CHART_MID
    elif ratio < 0.99:
        fill = CHART_HIGH
    else:
        fill = CHART_FULL
    return Cell(fill, None, _tooltip_for(pr))


def _upcoming_cell() -> Cell:
    return Cell(CHART_UPCOMING, None, _("upcoming"))


def _banner_strip(results: tuple[PeriodResult, ...]) -> list[Cell]:
    last = list(results[-24:])
    cells = []
    for pr in last:
        if pr.status == Status.UNCONFIRMED:
            cells.append(Cell(CHART_WHITE, CHART_UNCONFIRMED_BORDER, _tooltip_for(pr)))
        else:
            cells.append(Cell(CHART_FULL, None, _tooltip_for(pr)))
    return cells


# --------------------------------------------------------------------------------------
# Today view.
# --------------------------------------------------------------------------------------


def _open_sentence(n: int) -> str:
    if n == 0:
        return _("No check-ins open.")
    if n == 1:
        return _("One check-in open.")
    return _("%(n)s check-ins open.") % {"n": words.Number_word(n)}


def _unconfirmed_sentence(n: int) -> str | None:
    if n == 0:
        return None
    if n == 1:
        return _("One earlier day is unconfirmed.")
    return _("%(n)s earlier days are unconfirmed.") % {"n": words.Number_word(n)}


def _banner_title(start: date, end: date) -> str:
    n = (end - start).days + 1
    if n == 1:
        return _("One day without a check-in — %(day)s") % {"day": words.fmt_day(end)}
    if start.month == end.month:
        range_str = f"{start.day} to {words.fmt_day(end)}"
    else:
        range_str = f"{words.fmt_day(start)} to {words.fmt_day(end)}"
    return _("%(n)s days without a check-in — %(range)s") % {
        "n": words.Number_word(n),
        "range": range_str,
    }


def _unconfirmed_span(run: Run) -> tuple[date, date] | None:
    periods = run.periods
    i = len(periods) - 1
    while i >= 0 and periods[i].status != Status.UNCONFIRMED:
        i -= 1
    if i < 0:
        return None
    end = periods[i].period.end
    j = i
    while j - 1 >= 0 and periods[j - 1].status == Status.UNCONFIRMED:
        j -= 1
    start = periods[j].period.start
    return start, end


def _result_for_period(results: list[PeriodResult], period: Period) -> PeriodResult | None:
    for pr in results:
        if pr.period.start == period.start and pr.period.end == period.end:
            return pr
    return None


def _is_open_today(streak: StreakData, today: date) -> bool:
    if streak.ended_on is not None:
        return False
    if streak.period_kind == PeriodKind.WEEKDAYS and not is_due(streak, today):
        return False
    period = period_for(streak, today)
    if period is None:
        return False
    if streak.period_kind == PeriodKind.MONTHLY:
        days_left = (period.end - today).days
        if days_left >= 7:
            return False
    goals = active_goals(streak, period)
    checked_today = {c.goal_id for c in streak.checks if c.day == today}
    return any(g.id not in checked_today for g in goals)


def _build_card(
    streak: StreakData, today: date, settings: Settings, results: list[PeriodResult]
) -> Card:
    if streak.period_kind == PeriodKind.WEEKDAYS and not is_due(streak, today):
        nxt = next_due_day(streak, today)
        standard_weekdays = 0b0011111
        if streak.weekdays_mask == standard_weekdays:
            body = _("Weekdays only. Next check-in %(day)s.") % {"day": words.fmt_weekday_day(nxt)}
        else:
            body = _("%(days)s only. Next check-in %(day)s.") % {
                "days": _weekday_label(streak.weekdays_mask),
                "day": words.fmt_weekday_day(nxt),
            }
        return Card(
            streak_id=streak.id,
            name=streak.name,
            colour=streak.colour,
            meta=_("Not today"),
            kind="not_due",
            goals=[],
            progress=None,
            progress_text=None,
            show_footer=False,
            body=body,
        )

    period = period_for(streak, today)
    pr = _result_for_period(results, period) if period else None
    goals = active_goals(streak, period) if period else ()
    checks_today = {c.goal_id: c.done_at for c in streak.checks if c.day == today}
    done = pr.done if pr else 0
    total = pr.total if pr else len(goals)

    if streak.period_kind == PeriodKind.MONTHLY:
        meta = _("Done this month") if total and done >= total else _("Due this month")
        days_left = (period.end - today).days if period else 0
        card_goals = [
            CardGoal(
                goal_id=g.id,
                name=g.name,
                done_at=checks_today.get(g.id),
                trailing=ngettext("%(n)d day left", "%(n)d days left", days_left)
                % {"n": days_left},
            )
            for g in goals
        ]
        return Card(
            streak_id=streak.id,
            name=streak.name,
            colour=streak.colour,
            meta=meta,
            kind="monthly",
            goals=card_goals,
            progress=None,
            progress_text=None,
            show_footer=False,
            body=None,
        )

    if streak.period_kind == PeriodKind.N_PER_WEEK:
        meta = _("%(done)d of %(n)d this week") % {"done": done, "n": streak.times_per_week}
    else:
        run = current_run(streak, today, settings)
        day_number = run.length if run else 1
        meta = _("%(done)d of %(n)d · day %(k)d") % {
            "done": done,
            "n": total,
            "k": day_number,
        }

    card_goals = [
        CardGoal(goal_id=g.id, name=g.name, done_at=checks_today.get(g.id), trailing=None)
        for g in goals
    ]
    show_footer = streak.period_kind in (PeriodKind.DAILY, PeriodKind.WEEKDAYS) and total > 1
    return Card(
        streak_id=streak.id,
        name=streak.name,
        colour=streak.colour,
        meta=meta,
        kind="goals",
        goals=card_goals,
        progress=(done / total) if show_footer and total else None,
        progress_text=(_("%(done)d of %(n)d") % {"done": done, "n": total})
        if show_footer
        else None,
        show_footer=show_footer,
        body=None,
    )


# Today cards show actionable check-ins before "not due"/monthly filler cards; ties keep the
# streaks' relative (sidebar/position) order, since `list.sort` is stable.
_CARD_KIND_ORDER = {"goals": 0, "not_due": 1, "monthly": 2}


def today_view(
    streaks: list[StreakData], today: date, now: datetime, settings: Settings
) -> TodayView:
    banners: list[Banner] = []
    cards: list[Card] = []
    open_count = 0
    unconfirmed_total = 0

    for streak in streaks:
        if streak.ended_on is not None:
            continue
        results = evaluate(streak, today, settings)
        cards.append(_build_card(streak, today, settings, results))
        if _is_open_today(streak, today):
            open_count += 1
        run = current_run(streak, today, settings)
        if run and run.unconfirmed > 0:
            unconfirmed_total += run.unconfirmed
            span = _unconfirmed_span(run)
            if span is not None:
                start_d, end_d = span
                banners.append(
                    Banner(
                        streak_id=streak.id,
                        title=_banner_title(start_d, end_d),
                        body=_(
                            "Your %(n)s-day run is still counted as running. It only "
                            "ends if you tell me a goal was missed."
                        )
                        % {"n": run.length},
                        strip=_banner_strip(run.periods),
                    )
                )

    cards.sort(key=lambda c: _CARD_KIND_ORDER.get(c.kind, 99))

    title = words.fmt_weekday_day(today)
    subtitle = " ".join(
        s for s in (_open_sentence(open_count), _unconfirmed_sentence(unconfirmed_total)) if s
    )
    return TodayView(
        title=title, subtitle=subtitle, open_count=open_count, banners=banners, cards=cards
    )


# --------------------------------------------------------------------------------------
# History.
# --------------------------------------------------------------------------------------


def _tile_caption(period_kind: PeriodKind) -> str:
    if period_kind == PeriodKind.N_PER_WEEK:
        return _("weeks running")
    if period_kind == PeriodKind.MONTHLY:
        return _("months running")
    return _("days running")


def _tile_caption_ended(period_kind: PeriodKind) -> str:
    """The first stat tile's caption for an ended streak (design-spec §4): it reports the
    streak's best run rather than a still-running count."""
    if period_kind == PeriodKind.N_PER_WEEK:
        return _("weeks, best run")
    if period_kind == PeriodKind.MONTHLY:
        return _("months, best run")
    return _("days, best run")


def _goals_hit_percent(run: Run, today: date) -> int:
    eligible = [
        pr
        for pr in run.periods
        if pr.status in (Status.KEPT, Status.PARTIAL)
        and not (pr.period.start <= today <= pr.period.end)
    ]
    total_total = sum(pr.total for pr in eligible)
    if total_total == 0:
        return 0
    total_done = sum(pr.done for pr in eligible)
    return round(100 * total_done / total_total)


def _day_result_map(
    results: tuple[PeriodResult, ...] | list[PeriodResult],
) -> dict[date, PeriodResult]:
    m: dict[date, PeriodResult] = {}
    for pr in results:
        d = pr.period.start
        while d <= pr.period.end:
            m[d] = pr
            d += timedelta(days=1)
    return m


def _weeks_grid(
    day_map: dict[date, PeriodResult], grid_start: date, grid_end: date, today: date
) -> list[list[Cell]]:
    weeks: list[list[Cell]] = []
    week_start = grid_start - timedelta(days=grid_start.weekday())
    while week_start <= grid_end:
        cells = []
        for i in range(7):
            d = week_start + timedelta(days=i)
            if d > today or d not in day_map:
                cells.append(_upcoming_cell())
            else:
                cells.append(_cell_for_result(day_map[d]))
        weeks.append(cells)
        week_start += timedelta(days=7)
    return weeks


def _run_weeks(run: Run, today: date) -> list[list[Cell]]:
    day_map = _day_result_map(run.periods)
    grid_end = run.end if run.end is not None else today
    return _weeks_grid(day_map, run.start, grid_end, today)


def _lifetime_weeks(
    streak: StreakData, today: date, settings: Settings, weeks_shown: int
) -> list[list[Cell]]:
    results = evaluate(streak, today, settings)
    day_map = _day_result_map(results)
    this_week_start = today - timedelta(days=today.weekday())
    grid_start = this_week_start - timedelta(days=7 * (weeks_shown - 1))
    grid_end = this_week_start + timedelta(days=6)
    return _weeks_grid(day_map, grid_start, grid_end, today)


def _legend(n_goals: int) -> list[tuple[str, str | None, str]]:
    all_label = (
        _("done") if n_goals == 1 else _("all %(word)s") % {"word": words.number_word(n_goals)}
    )
    return [
        (CHART_FULL, None, all_label),
        (CHART_MID, None, _("some")),
        (CHART_WHITE, CHART_UNCONFIRMED_BORDER, _("unconfirmed")),
        (CHART_MISSED, None, _("missed")),
    ]


def _goal_bars(
    streak: StreakData, today: date, settings: Settings
) -> list[tuple[str, float, str, bool]]:
    results = evaluate(streak, today, settings)
    day_map = _day_result_map(results)
    month_start = date(today.year, today.month, 1)
    confirmed_days = [
        d
        for d in _daterange(month_start, today)
        if d in day_map and day_map[d].status in (Status.KEPT, Status.PARTIAL)
    ]
    denom = len(confirmed_days)
    checks_by_goal: dict[int, set[date]] = defaultdict(set)
    for c in streak.checks:
        checks_by_goal[c.goal_id].add(c.day)
    bars = []
    for g in sorted(streak.goals, key=lambda g: g.position):
        if g.removed_on is not None and g.removed_on <= month_start:
            continue
        numerator = sum(1 for d in confirmed_days if d in checks_by_goal.get(g.id, ()))
        ratio = numerator / denom if denom else 0.0
        bars.append((g.name, ratio, f"{numerator}/{denom}", ratio < 0.75))
    return bars


def history(
    streak: StreakData,
    today: date,
    settings: Settings,
    run_index: int | None = None,
    lifetime: bool = False,
    weeks_shown: int = 30,
) -> History:
    all_runs = runs(streak, today, settings)
    if not all_runs:
        selected = None
    elif run_index is not None:
        selected = next((r for r in all_runs if r.index == run_index), all_runs[-1])
    else:
        selected = next((r for r in all_runs if r.end is None), all_runs[-1])

    n_goals = sum(1 for g in streak.goals if g.removed_on is None)
    is_ended = streak.ended_on is not None

    if is_ended:
        best = best_run(streak, today, settings)
        running_len = best.length if best else 0
        tile0_caption = _tile_caption_ended(streak.period_kind)
        header_subtitle = _("%(meta)s · ended %(date)s") % {
            "meta": sidebar_meta(streak),
            "date": words.fmt_day_short(streak.ended_on),
        }
    else:
        running_len = selected.length if selected else 0
        tile0_caption = _tile_caption(streak.period_kind)
        header_subtitle = _("%(meta)s · run %(idx)d") % {
            "meta": sidebar_meta(streak),
            "idx": selected.index if selected else 0,
        }

    unconfirmed = selected.unconfirmed if selected else 0
    confirmed = selected.confirmed if selected else 0
    hit_pct = _goals_hit_percent(selected, today) if selected else 0
    tiles: list[tuple[str, str, str]] = [
        (str(running_len), tile0_caption, "accent"),
        (str(unconfirmed), _("unconfirmed"), "dim"),
        (str(confirmed), _("confirmed kept"), "strong"),
        (f"{hit_pct}%", _("goals hit"), "strong"),
    ]

    if lifetime:
        weeks = _lifetime_weeks(streak, today, settings, weeks_shown)
        chart_title = _("Lifetime")
        is_best = False
    elif selected is not None:
        weeks = _run_weeks(selected, today)
        if selected.end is None:
            chart_title = _("Run %(idx)d · since %(date)s") % {
                "idx": selected.index,
                "date": words.fmt_day_short(selected.start),
            }
        else:
            chart_title = _("Run %(idx)d · %(range)s") % {
                "idx": selected.index,
                "range": words.fmt_range(selected.start, selected.end),
            }
        is_best = selected.is_best
    else:
        weeks = []
        chart_title = ""
        is_best = False

    legend = _legend(n_goals)

    catch_up_link = None
    if selected is not None and selected.unconfirmed > 0:
        catch_up_link = ngettext(
            "%(n)d day unconfirmed — catch up",
            "%(n)d days unconfirmed — catch up",
            selected.unconfirmed,
        ) % {"n": selected.unconfirmed}

    goal_bars = _goal_bars(streak, today, settings)

    earlier_runs = []
    for r in reversed([r for r in all_runs if r.end is not None]):
        title = _("Run %(idx)d") % {"idx": r.index}
        meta = _("%(range)s · %(n)d days") % {
            "range": words.fmt_range(r.start, r.end),
            "n": r.length,
        }
        strip = [_cell_for_result(pr) for pr in r.periods]
        earlier_runs.append((title, meta, strip, r.index))

    return History(
        header_subtitle=header_subtitle,
        tiles=tiles,
        chart_title=chart_title,
        is_best=is_best,
        weeks=weeks,
        day_labels=["M", "", "W", "", "F", "", ""],
        legend=legend,
        catch_up_link=catch_up_link,
        goal_bars=goal_bars,
        earlier_runs=earlier_runs,
    )


# --------------------------------------------------------------------------------------
# Catch-up.
# --------------------------------------------------------------------------------------


def catch_up(streak: StreakData, today: date, settings: Settings) -> CatchUp:
    run = current_run(streak, today, settings)
    unconfirmed_days: list[date] = []
    if run is not None:
        unconfirmed_days = [
            pr.period.start for pr in run.periods if pr.status == Status.UNCONFIRMED
        ]
    unconfirmed_days.sort()
    n = len(unconfirmed_days)
    subtitle = ngettext("%(name)s · %(n)d day", "%(name)s · %(n)d days", n) % {
        "name": streak.name,
        "n": n,
    }
    days = [(d, words.fmt_weekday_day(d)) for d in unconfirmed_days]
    return CatchUp(subtitle=subtitle, days=days)


def _with_answers(
    streak: StreakData, answers: dict[date, tuple[Answer, tuple[int, ...]]]
) -> StreakData:
    kept = [a for a in streak.answers if a.day not in answers]
    added = [
        AnswerData(day=d, status=status, missed_goal_ids=tuple(missed_ids))
        for d, (status, missed_ids) in answers.items()
    ]
    return dataclasses.replace(streak, answers=tuple(kept + added))


def catch_up_preview(
    streak: StreakData,
    today: date,
    settings: Settings,
    answers: dict[date, tuple[Answer, tuple[int, ...]]],
) -> Preview:
    cu = catch_up(streak, today, settings)
    unconfirmed_days = [d for d, _label in cu.days]
    n_goals_total = sum(1 for g in streak.goals if g.removed_on is None)

    row_state: dict[date, str] = {}
    for d in unconfirmed_days:
        if d not in answers:
            row_state[d] = _("Unanswered")
            continue
        status, missed_ids = answers[d]
        if status == Answer.KEPT:
            row_state[d] = (
                _("Done")
                if n_goals_total == 1
                else _("All %(word)s goals") % {"word": words.number_word(n_goals_total)}
            )
        elif not missed_ids:
            row_state[d] = _("Untick the goals you missed")
        else:
            row_state[d] = _("Missed — which goals?")

    hypothetical = _with_answers(streak, answers)
    old_run = current_run(streak, today, settings)
    new_runs = runs(hypothetical, today, settings)
    new_run = next((r for r in new_runs if r.start == old_run.start), None) if old_run else None
    following = (
        next((r for r in new_runs if r.index == new_run.index + 1), None)
        if new_run is not None
        else None
    )

    warnings: dict[date, str] = {}
    if new_run is not None and new_run.end is not None:
        for d, (status, _mids) in answers.items():
            if status == Answer.MISSED:
                warnings[d] = _(
                    "Saving this ends the %(len)d-day run on %(day)s and starts run "
                    "%(idx)d on the %(ord)s."
                ) % {
                    "len": new_run.length,
                    "day": words.fmt_day(d),
                    "idx": new_run.index + 1,
                    "ord": words.ordinal_day(following.start) if following else "",
                }

    strip_results = evaluate(hypothetical, today, settings)
    strip = [_cell_for_result(pr) for pr in strip_results[-24:]]

    unanswered_after = [d for d in unconfirmed_days if d not in answers]

    def _hollow_sentence(days: list[date]) -> str:
        names = ", ".join(words.WEEKDAY_NAMES_FULL[d.weekday()] for d in days)
        return ngettext(
            "%(days)s stays hollow — unanswered, and it doesn't break anything.",
            "%(days)s stay hollow — unanswered, and they don't break anything.",
            len(days),
        ) % {"days": names}

    if new_run is not None and new_run.end is not None:
        parts = [
            _("Run %(idx)d ends at %(len)d days%(best)s.")
            % {
                "idx": new_run.index,
                "len": new_run.length,
                "best": _(" — your best run so far") if new_run.is_best else "",
            }
        ]
        if following is not None:
            parts.append(
                _("Run %(idx)d is on %(n)d days.") % {"idx": following.index, "n": following.length}
            )
        if unanswered_after:
            parts.append(_hollow_sentence(unanswered_after))
        summary = " ".join(parts)
    else:
        idx = new_run.index if new_run else (old_run.index if old_run else 0)
        length = new_run.length if new_run else (old_run.length if old_run else 0)
        if unanswered_after:
            summary = " ".join(
                [
                    _("Run %(idx)d stays at %(len)d days.") % {"idx": idx, "len": length},
                    _hollow_sentence(unanswered_after),
                ]
            )
        else:
            summary = _("All %(word)s days confirmed.") % {
                "word": words.number_word(len(unconfirmed_days))
            }

    return Preview(row_state=row_state, row_warning=warnings, strip=strip, summary=summary)


def mark_missed_preview(streak: StreakData, today: date, settings: Settings) -> str:
    """Preview the effect of marking *today* missed (today itself excluded from the count)."""
    hypothetical = _with_answers(streak, {today: (Answer.MISSED, ())})
    old_run = current_run(streak, today, settings)
    new_runs = runs(hypothetical, today, settings)
    ended = next((r for r in new_runs if old_run and r.start == old_run.start), None)
    length = ended.length if ended else 0
    idx = ended.index if ended else (old_run.index if old_run else 0)
    return _("This ends run %(idx)d at %(len)d days.") % {"idx": idx, "len": length}
