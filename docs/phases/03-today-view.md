# Phase 3 — Today view (design 4a content pane)

Read `CLAUDE.md`, `docs/design-spec.md` §3 (and §1, §9, §10 for context), `src/streaks/engine.py` (`today_view`,
`TodayView`, `Card`, `CardGoal`, `Banner`, `mark_missed_preview`) and the Phase 2 window/sidebar code. All strings and
numbers come from the engine — views only place widgets.

## Deliverables (create with `scripts/add_ui.py`)
- `today_view` — `StreaksTodayView : Adw.Bin`. Template children: `scrolled` (`Gtk.ScrolledWindow`, hscroll never),
  `title_label` (`title-2`), `subtitle_label` (`dim-label`), `another_day_button` ("Check in for another day"),
  `back_to_today_button` (hidden unless viewing a past day), `banners_box` (vertical, spacing 18),
  `columns_box` (horizontal, spacing 18, homogeneous) containing `column_left` and `column_right` (vertical boxes,
  spacing 18, valign start). Outer box: margin 24 top/bottom, 28 start/end, spacing 18.
- `catchup_banner` — `StreaksCatchupBanner : Gtk.Box` (`catchup-banner` class): `title_label` (bold, accent text),
  `body_label`, `strip` (`StripWidget` 8×22 gap 3), `catch_up_button` ("Catch up", `suggested-action`). Emits
  signal `catch-up` with `streak_id` (Phase 6 connects the dialog; for now the window logs).
- `checkin_card` — `StreaksCheckinCard : Gtk.Box` (`card`, vertical). Children: `dot`, `name_label` (`heading`),
  `meta_label` (`caption dim-label`), `goals_list` (`Gtk.ListBox`, selection none, activate-on-single-click; rows
  are `StreaksGoalRow`), `body_label` (for `not_due` cards; hidden otherwise), `footer` box (hidden unless
  `card.show_footer`): `progress` (`Gtk.ProgressBar`, hexpand), `progress_label` (caption dim), `missed_button`
  (flat, accent-coloured text "Mark day missed").
- `goal_row` — `StreaksGoalRow : Gtk.ListBoxRow`: `check` (`Gtk.CheckButton`, no label), `name_label`, `time_label`
  (caption dim, right; shows `words.time_hm(done_at)` when done, or `trailing` text such as "17 days left"). Done state:
  `check.active`, `name_label` gets `strike` + `dim-label` classes (strike-through via `Pango.AttrList` strikethrough
  in Python is acceptable). Activating the row toggles the check.
- `data/style.css` additions: `catchup-banner` (bg `#f4f8fe`, border 1px `#bcd4f2`, radius 12, padding 14px 16px),
  `catchup-banner .title` colour `#1a5fb4`, `strike` (`text-decoration: line-through`), `checkin-card .footer`
  (bg `#fcfcfc`, padding 11px 16px), `goal-row` min-height 46px. Keep to these.
- Window wiring: `content_stack` page `today` now holds `StreaksTodayView`; `StreaksTodayView.set_state(state)` and
  `.show_day(day: date | None)` (None = today). Rebuild on `state.changed`. The header `content_title` for Today is
  "Today" / `today_view.title`.
- "Check in for another day": `Gtk.Popover` with a `Gtk.Calendar` (`day_calendar`) limited by
  `settings.backfill_days` (days before the earliest allowed or after today are rejected — `day-selected` handler
  ignores them and the popover shows a caption "Only the last {n} days can be answered"). Choosing a day calls
  `show_day(day)`: title becomes `words.fmt_weekday_day(day)`, subtitle "Checking in for an earlier day.", banners
  hidden, `back_to_today_button` shown. Goal toggles for a past day write `GoalCheck(day=that day, done_at=that day
  at now's time)`.
- Column assignment: append each card to whichever column currently has fewer goal rows (count rows, ties → left).
- "Mark day missed": `Adw.AlertDialog` heading "Mark today as missed?" body `engine.mark_missed_preview(...)`,
  responses `cancel` / `missed` (destructive, default cancel) → `models.answer_day(..., Answer.MISSED)` →
  `state.notify_changed()`.

## Tests (`tests/gui/test_today_view.py`, seeded in-memory DB, fake today 2026-09-13)
- Title/subtitle text; `another_day_button` label; one banner with the exact title/body, strip has 24 cells, last 4
  outlined (`border == "#a9c9ef"`), button label "Catch up".
- Cards: 4 cards, order 75 Hard, Gym, No snoozing, Clip fingernails; `column_left` has [75 Hard],
  `column_right` has [Gym, No snoozing, Clip fingernails]; each card's `name_label`/`meta_label` text equals the
  engine card; 75 Hard rows: names in order, `check.active` pattern [T, T, F, F, T], `time_label`s ["07:12","07:55",
  "", "", "21:30"], footer visible, `progress.fraction == 0.6`, `progress_label` "3 of 5"; Gym: 2 rows, footer hidden;
  No snoozing: 0 rows, `body_label` "Weekdays only. Next check-in Monday 14 September."; Clip fingernails: row
  trailing "17 days left".
- Toggling "Read 10 pages" (`check.set_active(True)` + events) writes a `GoalCheck` for goal id / day 2026-09-13 with
  `done_at` from `clock.now()`, updates `progress_label` to "4 of 5", meta to "4 of 5 · day 51", time label "21:45",
  and the sidebar badge stays "2" (still one goal open); toggling it back deletes the check.
- Toggling the last open 75 Hard goal → badge "1".
- `show_day(2026-09-12)`: title "Saturday 12 September", subtitle "Checking in for an earlier day.", banners hidden,
  back button visible; toggling a goal writes a check with `day == 2026-09-12`; `show_day(None)` restores.
- Calendar limits: selecting 2026-09-10 (outside backfill 2) is ignored; 2026-09-11 is accepted.
- Mark day missed: activate `missed_button`, respond `missed` on the dialog (call `dialog.response("missed")` or the
  handler directly), assert a `DayAnswer(missed)` for today exists and the sidebar count/meta update (run 3 ends).
- No-quiet-days variant: answer 9–12 Sep as kept in the DB, rebuild → `banners_box` has no children, subtitle
  "Two check-ins open."
- Register screens `today` (1160×760 window with Today selected) and `today-quiet` (same, after answering the quiet
  days kept) in `tests/gui/screens.py`.

`scripts/check.sh --fast` fully green; `scripts/screenshot.sh today today-quiet` produces PNGs — view them with Read
and compare to design-spec §3 before reporting. Do not git commit.
