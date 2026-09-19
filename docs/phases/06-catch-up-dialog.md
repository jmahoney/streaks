# Phase 6 — Catch-up dialog (design 4c)

Read `CLAUDE.md`, `docs/design-spec.md` §5 (+ §9, §10), `src/streaks/engine.py` (`catch_up`, `catch_up_preview`,
`Preview`), `models.answer_day`, the banner (`StreaksCatchupBanner`) and the streak view's `catch_up_link`.

## Deliverables (via `scripts/add_ui.py`)
- `catchup_dialog` — `StreaksCatchupDialog : Adw.Dialog` (`content-width: 560`, title "Catch up").
  `Adw.ToolbarView` → `Adw.HeaderBar` (`show-start-title-buttons: false; show-end-title-buttons: false`): start
  `cancel_button` "Cancel"; title `Adw.WindowTitle dialog_title` "Catch up" / `catch_up.subtitle` ("75 Hard · 4
  days"); end `save_button` "Save" (`suggested-action`, insensitive until ≥1 day answered and every Missed row has
  ≥1 unticked goal). Content box (margin 18, spacing 14): `intro_label` (caption dim, wrap, the exact §5 sentence),
  `days_list` (`Gtk.ListBox`, `card`, selection none; rows `StreaksCatchupRow`), result `card`: `result_title`
  ("Result of these answers", heading), `result_strip` (`StripWidget` 9×20 gap 3), `result_label` (caption dim, wrap).
- `catchup_row` — `StreaksCatchupRow : Gtk.ListBoxRow` (class `catchup-row`): `date_label` (bold), `state_label`
  (caption dim), `kept_button` / `missed_button` (`Gtk.ToggleButton`s in a `linked` box; kept checked →
  `suggested-action`; missed checked → `destructive-action`; clicking the active one again un-answers the day),
  `goals_revealer` (`Gtk.Revealer`, shown only in Missed state) containing `goals_list` (`Gtk.ListBox` class
  `catchup-goal-list`, rows: `Gtk.CheckButton` + label; all ticked by default; ticked = kept, unticked = missed),
  `warning_label` (caption, `error` class; `Preview.row_warning[day]`). Missed state adds class `missed` to the row.
  Signal `answer-changed`.
- Dialog logic: `StreaksCatchupDialog(state, streak_id)`; `answers: dict[date, tuple[Answer, tuple[int,...]]]`
  rebuilt from rows on every change → `engine.catch_up_preview(...)` → update every row's `state_label` and
  `warning_label`, `result_strip.set_cells(preview.strip)`, `result_label`, and `save_button.sensitive`.
  Save → `models.answer_day(...)` for each answered day in one `db.atomic()`, `state.notify_changed()`, close.
- Wiring: the Today banner's `catch-up` signal and the streak view's `catch_up_link` present the dialog for that
  streak. After save, Today rebuilds (banner disappears when no unconfirmed days remain) and history updates.
- `data/style.css`: `catchup-row.missed` (bg `#fdf2f2`, border-color `#f0d7d9`), `catchup-row.missed .date`
  (`#a51d2d`), `catchup-goal-list` (radius 9, border 1px `#f0d7d9`).

## Tests (`tests/gui/test_catchup_dialog.py`, seeded, streak 75 Hard)
- Subtitle "75 Hard · 4 days"; intro text exact; 4 rows with `date_label`s "Wednesday 9 September" … "Saturday 12
  September" and `state_label` "Unanswered"; both toggles inactive; revealers closed; save insensitive; result strip
  24 cells with the last 4 outlined; `result_label` == engine summary for no answers.
- Kept on Wed 9 → state "All five goals", save sensitive, strip cell 20 filled `#1a68c7`.
- Missed on Fri 11 → row has class `missed`, revealer open with 5 ticked goal checks, state "Untick the goals you
  missed", save insensitive; untick "45 min second workout" → state "Missed — which goals?", `warning_label`
  "Saving this ends the 48-day run on 11 September and starts run 4 on the 12th.", save sensitive.
- With Wed kept, Fri missed(goal 2), Sat kept → `result_label` == "Run 3 ends at 48 days — your best run so far. Run 4
  is on 2 days. Thursday stays hollow — unanswered, and it doesn't break anything." (assert equality with
  `engine.catch_up_preview(...).summary` **and** the literal).
- Clicking the active Kept again → row back to "Unanswered".
- Save → 3 `DayAnswer` rows (Fri 11 with `missed_goal_ids == [goal 2 id]`), dialog closed, `engine.runs` for 75 Hard now
  has 4 runs (lengths 28, 34, 48, 2), sidebar count "2", Today banner title now "One day without a check-in — 10
  September".
- Cancel writes nothing.
- Opening from the banner (`catch_up_button` click) and from the streak view link both present a dialog whose
  subtitle is "75 Hard · 4 days".
- Screens: `catch-up` (all unanswered) and `catch-up-missed` (Wed kept, Fri missed with goal 2 unticked, Sat kept),
  rendered from the dialog child at 560 × natural height.

`scripts/check.sh --fast` green; screenshots reviewed with Read against §5. No commits.
