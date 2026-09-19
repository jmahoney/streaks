# Phase 1 — models, engine, fixture (no UI)

Read `CLAUDE.md`, `docs/design-spec.md` (all of it — every string the engine produces is defined there) and this file.
Deliverables: `src/streaks/models.py`, `src/streaks/clock.py`, `src/streaks/engine.py`, `src/streaks/words.py`,
`src/streaks/export.py`, `tests/fixtures/seed.py`, `tests/unit/test_models.py`, `tests/unit/test_engine.py`,
`tests/unit/test_export.py`, `tests/unit/test_seed.py`. Add the new `.py` files to `streaks_sources` in `src/meson.build`
and to `po/POTFILES` (`scripts/check_templates.py` enforces this). `scripts/check.sh --unit` must pass; then
`scripts/check.sh --fast` must still pass.

Strict typing everywhere (`from __future__ import annotations`, dataclasses, `Literal`, `enum.StrEnum`). No GTK imports
in `engine.py`, `words.py`, `export.py` or `models.py` except `GLib` for the data dir in `models.py`.

## `clock.py`
```python
def now() -> datetime          # honours STREAKS_FAKE_TODAY (YYYY-MM-DD → that date at 21:45 local) and
                               # STREAKS_FAKE_NOW (ISO datetime) for tests/dev; else datetime.now()
def check_in_day(at: datetime, day_start_minutes: int) -> date   # (at - day_start).date()
def today(day_start_minutes: int) -> date                        # check_in_day(now(), day_start_minutes)
```
Day-start examples (day_start 240 = 04:00): 2026-09-14 03:59 → 2026-09-13; 04:00 → 2026-09-14; day_start 0 → calendar day.

## `models.py` (Peewee)
`database_path()` → `$STREAKS_DATA_DIR/streaks.db` or `GLib.get_user_data_dir()/streaks/streaks.db` (create dir).
Module-level `db = SqliteDatabase(None)`; `init_db(path: str | None = None)` initialises it with
`pragmas={'foreign_keys': 1, 'journal_mode': 'wal'}`, connects, `create_tables`, and sets `user_version = 1` if 0.
Tests bind an in-memory DB instead (fixture in `tests/unit/conftest.py`, per CLAUDE.md).

```python
class PeriodKind(StrEnum): DAILY="daily"; WEEKDAYS="weekdays"; N_PER_WEEK="n_per_week"; MONTHLY="monthly"
class Answer(StrEnum): KEPT="kept"; MISSED="missed"

class Streak(BaseModel):
    name = CharField(); colour = CharField(max_length=7)            # one of COLOURS
    period_kind = CharField(); weekdays_mask = IntegerField(default=0b0011111)  # Mon=bit0 … Sun=bit6
    times_per_week = IntegerField(default=3); reminder_time = TimeField(null=True)
    allow_skip = BooleanField(default=False); created_on = DateField()
    ended_on = DateField(null=True); position = IntegerField(default=0)
class Goal(BaseModel): streak FK (backref goals, on_delete CASCADE); name; position; removed_on = DateField(null=True)
class GoalCheck(BaseModel): goal FK (CASCADE); day = DateField(); done_at = DateTimeField(); unique (goal, day)
class DayAnswer(BaseModel): streak FK (CASCADE); day = DateField(); status = CharField(); missed_goal_ids = TextField(default="[]"); unique (streak, day)
COLOURS = ("#3584e4", "#2ec27e", "#e5a50a", "#e01b24", "#9141ac")
```
Write helpers (each in `db.atomic()`; UI never composes queries):
- `create_streak(name, colour, period_kind, goals: list[str], *, weekdays_mask=…, times_per_week=…, reminder_time=None, allow_skip=False, created_on) -> Streak` — position = max+1, goals get positions 0..n-1. Validates name/goals non-empty, colour in COLOURS.
- `update_streak(streak, *, name, colour, period_kind, weekdays_mask, times_per_week, reminder_time, allow_skip, goals: list[tuple[int | None, str]], today)` — goals list is `(existing_goal_id_or_None, name)` in the desired order; missing existing goals get `removed_on = today`; new ones created; positions rewritten.
- `toggle_goal_check(goal, day, done_at) -> bool` — creates the check if absent (returns True) or deletes it (False).
- `answer_day(streak, day, status: Answer, missed_goal_ids: list[int] = ()) -> DayAnswer` — upsert.
- `clear_answer(streak, day)`.
- `end_streak(streak, on: date)`; `delete_streak(streak)`; `delete_all()` (all four tables); `reorder_streaks(ids)`.
- Read helpers returning plain data for the engine: `load_streak_data(streak) -> StreakData` and
  `load_all(today) -> list[StreakData]` (running first by position, then ended). `StreakData` is a frozen dataclass in
  `engine.py` (see below) so the engine never touches Peewee objects. `load_all` must be at most 4 queries (streaks,
  goals, checks, answers — no per-row queries).

## `engine.py` — pure functions on plain data

```python
@dataclass(frozen=True)
class GoalData: id: int; name: str; position: int; removed_on: date | None
@dataclass(frozen=True)
class CheckData: goal_id: int; day: date; done_at: datetime
@dataclass(frozen=True)
class AnswerData: day: date; status: Answer; missed_goal_ids: tuple[int, ...]
@dataclass(frozen=True)
class StreakData: id; name; colour; period_kind; weekdays_mask; times_per_week; reminder_time; allow_skip;
                  created_on; ended_on; position; goals: tuple[GoalData,...]; checks: tuple[CheckData,...]; answers: tuple[AnswerData,...]

class Status(StrEnum): KEPT="kept"; PARTIAL="partial"; UNCONFIRMED="unconfirmed"; MISSED="missed"; OPEN="open"; NOT_DUE="not_due"; UPCOMING="upcoming"

@dataclass(frozen=True)
class Period: start: date; end: date          # inclusive; day → start==end; week → Mon..Sun; month → 1..last
@dataclass(frozen=True)
class PeriodResult: period: Period; status: Status; done: int; total: int   # done/total = goals (daily/weekdays/monthly) or sessions/N (n_per_week)
@dataclass(frozen=True)
class Run: index: int; start: date; end: date | None; length: int; confirmed: int; unconfirmed: int; is_best: bool; periods: tuple[PeriodResult, ...]
```
Rules (these define the app; tests pin them):
- **Due periods.** daily: every day from `created_on`; weekdays: days whose weekday bit is set; n_per_week: ISO weeks
  (Mon–Sun) from the week containing `created_on`; monthly: calendar months from `created_on`'s month. Periods run up
  to `ended_on` (if set) or `today`. `active_goals(streak, period)` = goals with `removed_on` None or > period.start.
- **Sessions** (n_per_week): a day in the week counts as a session when *all* active goals are checked that day.
- **Period status**: answered missed → MISSED; answered kept → KEPT; else the current period (contains today) →
  OPEN when nothing done, PARTIAL/KEPT by activity (so today with 3/5 is PARTIAL, all done is KEPT); past periods:
  all goals done (or sessions ≥ N) → KEPT; some → PARTIAL; none → UNCONFIRMED. Ratio = done/total.
- **Runs**: walk periods in order. A run starts at the first period that is not MISSED after streak creation or after a
  MISSED period. It ends at the period before the next MISSED (`end`), or is open (`end=None`). `length` = number of
  periods from start through end (or through today's period). `confirmed` = KEPT + PARTIAL (+ OPEN/PARTIAL today counts
  as confirmed only if done > 0). `unconfirmed` = UNCONFIRMED periods in the run. When `allow_skip`, the first MISSED
  period in an ISO week whose previous due period was not MISSED does **not** end the run (it is still shown as missed).
  `is_best` = longest length (ties → the latest). Runs are numbered from 1 in chronological order. Ended streaks
  (`ended_on`) have no open run.
- **Sidebar count** = length of the open run (`current_run(streak).length`), or for ended streaks best length.
- `count_through_unconfirmed=False` variant: an UNCONFIRMED period older than `backfill_days` ends the run like a miss.

Functions (all take `today: date` explicitly; `settings: Settings` frozen dataclass with `day_start_minutes=240,
backfill_days=2, count_through_unconfirmed=True, show_ended=True`):
- `due_periods(streak, today) -> list[Period]`, `period_for(streak, day) -> Period | None`, `is_due(streak, day) -> bool`,
  `next_due_day(streak, after: date) -> date`.
- `evaluate(streak, today, settings) -> list[PeriodResult]`, `runs(streak, today, settings) -> list[Run]`,
  `current_run(...) -> Run | None`, `best_run(...)`.
- `sidebar_meta(streak) -> str` — "Daily · 5 goals", "Mon–Fri · 1 goal", "Mon, Wed, Fri · 2 goals" (non-contiguous),
  "3× a week · 2 goals", "Monthly · 1 goal"; ended: `sidebar_ended_meta(streak, best) -> "Ended 4 Mar · best 31"`.
- `today_view(streaks, today, now, settings) -> TodayView` with `title` ("Sunday 13 September"), `subtitle`
  ("Two check-ins open. Four earlier days are unconfirmed."), `open_count` (badge), `banners: list[Banner]`
  (`streak_id, title "Four days without a check-in — 9 to 12 September", body "Your 51-day run is still counted as
  running. It only ends if you tell me a goal was missed.", strip: list[Cell]`), `cards: list[Card]`.
  Banner day-range wording: "9 to 12 September", cross-month "30 August to 2 September", single day "One day without
  a check-in — 12 September". Body uses the run's `length`.
  `Card`: `streak_id, name, colour, meta, kind: Literal["goals","not_due","monthly"], goals: list[CardGoal(goal_id,
  name, done_at | None, trailing: str | None)], progress: float | None, progress_text ("3 of 5") | None, show_footer,
  body: str | None`. Meta/body strings exactly per design-spec §3, using `words.py`. Column assignment is done by the
  view (not here).
- `history(streak, today, settings, run_index: int | None = None, lifetime=False, weeks_shown=30) -> History` with
  `header_subtitle` ("Daily · 5 goals · run 3"), `tiles: [(value_str, caption, style)]` ("51","days running","accent"),
  `chart_title` ("Run 3 · since 25 July" / "Run 2 · 14 May – 16 Jun"), `is_best`, `weeks: list[list[Cell]]`
  (7 per week, Monday first; leading pad cells before the run start use `upcoming` colour, days after today
  `upcoming`), `day_labels = ["M","","W","","F","",""]`, `legend: list[(colour, border, label)]`, `catch_up_link`
  ("4 days unconfirmed — catch up" or None), `goal_bars: list[(name, ratio_float, "6/9", low: bool)]`, `earlier_runs:
  list[(title "Run 2", meta "14 May – 16 Jun · 34 days", strip: list[Cell], index)]`.
  `Cell` = `(fill: str, border: str | None, tooltip: str)` with the colours/tooltips in design-spec (table at top).
  Tiles: running = current run length; unconfirmed; confirmed; hit % = checks on confirmed past periods ÷
  (active goals × those periods), rounded; captions "days/weeks/months running" per kind.
  Goal bars: this calendar month, denominator = confirmed due days in the month up to today inclusive
  (unconfirmed days excluded), `low` when ratio < 0.75. Lifetime chart = last `weeks_shown` ISO weeks ending this week.
- `catch_up(streak, today, settings) -> CatchUp` with `subtitle` ("75 Hard · 4 days"), `days: list[(date,
  label "Wednesday 9 September")]` (unconfirmed days of the current run, oldest first) and
  `catch_up_preview(streak, today, settings, answers: dict[date, tuple[Answer, tuple[int,...]]]) -> Preview` with
  `row_state: dict[date, str]` ("Unanswered" / "All five goals" / "Missed — which goals?" / "Untick the goals you
  missed"), `row_warning: dict[date, str]` ("Saving this ends the 48-day run on 11 September and starts run 4 on the
  12th."), `strip: list[Cell]` (last 24 due days with the pending answers applied), `summary` ("Run 3 ends at 48 days —
  your best run so far. Run 4 is on 2 days. Thursday stays hollow — unanswered, and it doesn't break anything." /
  "Run 3 stays at 51 days. Thursday stays hollow — …" / "All four days confirmed. Run 3 stays at 51 days.").
  Also `mark_missed_preview(streak, today, settings) -> str` ("This ends run 3 at 50 days." — today excluded).

## `words.py`
`number_word(n) -> str` ("one"…"twelve", else digits), `Number_word` capitalised, `ordinal_day(d) -> "12th"`,
`fmt_day(d) -> "9 September"`, `fmt_day_short(d) -> "4 Mar"`, `fmt_weekday_day(d) -> "Wednesday 9 September"`,
`fmt_range(a, b) -> "14 May – 16 Jun"` (en dash, spaces), `weekday_names_short`, `time_hm(dt) -> "07:12"`.
Strings that reach the user go through `gettext` (`_`, `ngettext`); import `gettext` and use `gettext.gettext as _`
at module level so the modules work without the launcher's `gettext.install`.

## `export.py`
`dump() -> dict` (all tables as JSON-able dicts, ISO dates, `"version": 1`), `dump_json(path)`, `load(data)` restores
into an empty DB (used by tests for round-trip). Export must not include anything but these tables.

## `tests/fixtures/seed.py`
`seed(today: date = date(2026, 9, 13)) -> dict[str, Streak]` — importable and runnable (`python3 tests/fixtures/seed.py`
initialises the DB at `$STREAKS_DATA_DIR` and seeds it). Exact dataset:

1. **75 Hard** — `#3584e4`, daily, created 2026-02-02, goals in order: "Progress photo", "45 min outdoors",
   "45 min second workout", "Read 10 pages", "Stick to the diet". Run 1 = 2 Feb–1 Mar, then every day 2 Mar–13 May
   answered MISSED; Run 2 = 14 May–16 Jun, then 17 Jun–24 Jul MISSED; Run 3 = 25 Jul–today. Checks on every run day
   before 9 Sep by day index `i` from that run's start: `i % 7 == 3` → goals [0,1,3,4]; `i % 11 == 5` → [0,1,4];
   else all five; `done_at` = day 07:00 + goal_index × 5 min. 9–12 Sep: nothing. Today: goals 0 at 07:12, 1 at 07:55,
   4 at 21:30.
2. **No snoozing the alarm** — `#2ec27e`, weekdays mask Mon–Fri, created 2026-08-27, goal "Up at first alarm"; checked
   every due day 27 Aug–11 Sep at 06:30.
3. **Gym, three times a week** — `#9141ac`, n_per_week 3, created 2026-07-13, goals "45 min session", "Log the weights";
   both checked on Mon/Wed/Fri of every week 13 Jul–4 Sep (18:30/19:20); this week Mon 7 and Wed 9 Sep only.
4. **Clip fingernails** — `#e5a50a`, monthly, created 2026-06-01, goal "Clip them"; checked on the 5th of Jun, Jul, Aug.
5. **Couch to 5K** — `#e01b24`, daily, created 2026-02-02, ended_on 2026-03-04, goal "Run"; checked every day 2 Feb–4 Mar.

Expected values (tests assert these literally — they were computed independently):
- 75 Hard: runs lengths [28, 34, 51]; run 3 start 25 Jul, `end None`, confirmed 47, unconfirmed 4, is_best; partial days
  in run 3: 28 Jul, 30 Jul, 4 Aug, 10, 11, 18, 21, 25 Aug, 1 Sep, 8 Sep (+ today); hit % 94; tiles ["51","4","47","94%"];
  goal bars this month [9/9, 9/9, 6/9 (low), 8/9, 9/9]; earlier runs metas "14 May – 16 Jun · 34 days",
  "2 Feb – 1 Mar · 28 days"; card meta "3 of 5 · day 51"; sidebar meta "Daily · 5 goals", count 51; banner title
  "Four days without a check-in — 9 to 12 September"; catch-up days Wed 9…Sat 12; preview with {Wed 9: kept, Fri 11: missed
  goal 2, Sat 12: kept} → warning "Saving this ends the 48-day run on 11 September and starts run 4 on the 12th.",
  summary "Run 3 ends at 48 days — your best run so far. Run 4 is on 2 days. Thursday stays hollow — unanswered, and
  it doesn't break anything."; mark-missed preview "This ends run 3 at 50 days."
- No snoozing: count 12, meta "Mon–Fri · 1 goal", card kind not_due, meta "Not today", body "Weekdays only. Next
  check-in Monday 14 September."
- Gym: count 9, meta "3× a week · 2 goals", card meta "2 of 3 this week", no footer.
- Clip fingernails: count 4, meta "Monthly · 1 goal", card meta "Due this month", goal trailing "17 days left".
- Couch to 5K: ended, best 31, sidebar "Ended 4 Mar · best 31".
- Today view: title "Sunday 13 September", subtitle "Two check-ins open. Four earlier days are unconfirmed.",
  open_count 2. Definition: a streak is "open" today when it is due today and has ≥1 active goal not yet done; a
  monthly streak counts as open only during the last 7 days of the month. So 75 Hard and Gym are open; No snoozing
  (not due) and Clip fingernails (17 days left) are not. Cards in order 75 Hard, Gym, No snoozing, Clip fingernails.

## Tests
- `tests/unit/conftest.py`: autouse in-memory DB fixture binding all models (per CLAUDE.md); `seeded` fixture calling
  `seed()`; `today` fixture = `date(2026, 9, 13)`; default `Settings()`.
- `test_models.py`: create/update/toggle/answer/end/delete/delete_all/reorder, uniqueness constraints, `load_all` query
  count (use `peewee` query logging or `db.execute_sql` counter) ≤ 4.
- `test_engine.py`: parametrised tables for `check_in_day`, `due_periods` per kind (incl. month lengths, Feb, ISO week
  crossing a year), `period_status` cases, `runs` (miss ends, consecutive misses, allow_skip forgiveness once per week,
  unconfirmed continues, count_through_unconfirmed=False), every expected value listed above, all `words.py` helpers,
  heatmap cell colours for each status/ratio, banner wording variants, subtitle variants (0/1/2 open, 0 unconfirmed).
- `test_seed.py`: seed creates 5 streaks / 10 goals and the exact check counts you derive.
- `test_export.py`: dump → delete_all → load → dump equal.
Tests must not depend on wall-clock time or locale (force `C`/English formatting in `words.py`).
Run `ruff format` + `ruff check --fix` before finishing. Do not git commit.
