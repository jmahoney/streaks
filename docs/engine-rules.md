# Engine rules

This is the set of rules `streaks.engine` applies to turn check-ins and missed-day answers into
period statuses, runs and counts. `tests/unit/test_engine.py` pins each of them.

Every rule below is evaluated for a `today` date and a `Settings` (`day_start_minutes`,
`backfill_days`, `count_through_unconfirmed`, `show_ended`). `today` itself comes from
`streaks.clock.today(day_start_minutes)`, so `day_start_minutes` decides which calendar day a
late-night check-in belongs to before any of these rules run.

## Due periods

A streak's due periods depend on its `period_kind`:

- **daily** — every day from `created_on`.
- **weekdays** — the days whose bit is set in `weekdays_mask`.
- **n_per_week** — ISO weeks (Monday–Sunday), starting with the week that contains `created_on`.
- **monthly** — calendar months, starting with `created_on`'s month.

Periods run up to `ended_on` if the streak has ended, otherwise up to `today`.

A goal counts as active for a period when its `removed_on` is unset, or later than the period's
start date.

## Sessions

For an `n_per_week` streak, a day counts as a session when every active goal is checked on that
day. A period's `done` count is the number of session days in its week; `total` is
`times_per_week`.

## Period status

A period that has an explicit answer takes its status from that answer: `missed` → `MISSED`;
`kept` → `KEPT` (and its `done` count is raised to `total`, regardless of which individual goals
were actually checked).

An unanswered period that contains `today` is the *current* period:

- `OPEN` when nothing is done yet.
- `KEPT` when every goal (or session) is done.
- `PARTIAL` otherwise — for example 3 of 5 goals done.

An unanswered period entirely in the past is:

- `KEPT` when everything was done.
- `PARTIAL` when some of it was done.
- `UNCONFIRMED` when nothing was done and no one said what happened.

A period's ratio is `done / total` (0 when `total` is 0).

## Runs

A run is a stretch of consecutive due periods that stay clear of being effectively missed. It
starts at the first such period — either right after the streak was created, or right after an
effectively missed period — and it runs through the last clear period before the next effectively
missed one. When no later period is effectively missed, the run stays open (`end` is `None`) and
covers every due period up to today's.

A period counts as effectively missed when its status is `MISSED`; the `count_through_unconfirmed`
setting can also make an `UNCONFIRMED` period count as one (see below).

When a streak's `allow_skip` is set, the first `MISSED` period in an ISO week is forgiven once:
the run carries on through it, provided the period immediately before it also carried the run
through. The period still displays as missed; only its effect on the run length is waived, and
only the first such period in a given week gets this treatment. Forgiveness is reserved for a
genuine `MISSED` answer — a period that counts as effectively missed only through the
`count_through_unconfirmed` rule keeps its full effect on the run.

A run's `length` is the number of periods in it. `confirmed` is the count of `KEPT` and `PARTIAL`
periods; today's period joins that count once at least one goal is done and it becomes `PARTIAL`
— up to that point it is `OPEN` and stays out of the count. `unconfirmed` is the count of
`UNCONFIRMED` periods in the run.

Runs are numbered from 1 in chronological order. The longest run is `is_best`; if several runs
tie for longest, the latest one wins. An ended streak (`ended_on` set) has no open run: every run
it ever had is closed.

## Sidebar count

The number shown next to a running streak is the length of its open run. The number shown for an
ended streak is the length of its best run.

## `count_through_unconfirmed`

With `count_through_unconfirmed=True` (the default), an `UNCONFIRMED` period stays part of its
run for as long as it remains unconfirmed — the run simply carries an unconfirmed period, and its
length grows through it while a check-in or an answer is still pending.

With `count_through_unconfirmed=False`, an `UNCONFIRMED` period is given a grace window of
`backfill_days` days past its end. Once that window has passed, the period counts as effectively
missed for run purposes — it ends the run the same way an actual `MISSED` answer would.
