# Phase 4 — New / Edit streak dialog (design 4d)

Read `CLAUDE.md`, `docs/design-spec.md` §6 (+ §9), `src/streaks/models.py` (`create_streak`, `update_streak`,
`COLOURS`, `PeriodKind`) and the window code. Available libadwaita 1.9 widgets: `Adw.Dialog`, `Adw.ToggleGroup` /
`Adw.Toggle`, `Adw.EntryRow`, `Adw.SpinRow`, `Adw.SwitchRow`, `Adw.ButtonRow`, `Adw.PreferencesPage/Group`.

## Deliverables (via `scripts/add_ui.py`)
- `streak_dialog` — `StreaksStreakDialog : Adw.Dialog` (`content-width: 560`, `title` "New Streak" / "Edit Streak").
  Template children: `cancel_button`, `save_button` (label "Create" or "Save", `suggested-action`), `name_row`
  (`Adw.EntryRow` "Name"), `colour_row` (`Adw.ActionRow` "Colour") with 5 `Gtk.CheckButton`s `swatch_0..4` in one
  group, class `colour-swatch` and a per-button CSS provider for the colour; `period_group`
  (`Adw.PreferencesGroup` title "Period", description "Every goal in a streak shares this period."), `period_toggle`
  (`Adw.ToggleGroup`, `homogeneous: true`, toggles named `daily`/`weekdays`/`n_per_week`/`monthly` with labels
  "Daily", "Weekdays", "N a week", "Monthly"), `weekday_box` (7 circular `Gtk.ToggleButton`s `weekday_0..6` labels
  "M","T","W","T","F","S","S"; sensitive only when weekdays selected), `times_row` (`Adw.SpinRow` "Times a week",
  1–7, default 3; visible only for n_per_week), `reminder_row` (`Adw.ActionRow` "Reminder" / subtitle "A check-in
  notification each period", suffix `reminder_label` "20:00 ›" or "Off ›", activatable → `reminder_popover` with
  `reminder_switch`, `hour_spin`, `minute_spin`), `skip_row` (`Adw.SwitchRow` "Allow one skip a week" / "A skipped
  period won't break the run"), `goals_group` (`Adw.PreferencesGroup` title bound to "Goals — {n}"), `goals_list`
  (`Gtk.ListBox` rows are `StreaksGoalEditRow`), `add_goal_row` (`Adw.ButtonRow` "Add a goal", `start-icon-name:
  list-add-symbolic`).
- `goal_edit_row` — `StreaksGoalEditRow : Gtk.ListBoxRow`: `handle` (`Gtk.Image list-drag-handle-symbolic`, dim),
  `entry` (`Gtk.Entry`, placeholder "Goal", flat, hexpand), `remove_button` (flat, `window-close-symbolic`; hidden
  when it is the only row). Property `goal_id: int` (0 for new).
- Behaviour: `StreaksStreakDialog.for_new()` / `.for_edit(streak_data)`; `save_button.sensitive` = name non-empty
  and ≥1 non-empty goal (recomputed on every change; whitespace-only counts as empty). Period defaults: Daily; Weekdays
  → Mon–Fri ticked; switching kinds keeps the other kinds' values. Reminder default off (`reminder_label` "Off ›");
  the switch enables the spins; label shows `HH:MM ›`. Save → `models.create_streak(...)`/`update_streak(...)`,
  `state.notify_changed()`, `close()`, and (new) the window selects the new streak's sidebar row. Cancel closes without
  writing. Escape = cancel. Enter in the last goal entry adds a new goal row and focuses it.
- Window: `win.new-streak` presents `StreaksStreakDialog.for_new()`; provide `win.edit-streak` (`int` id) for Phase 5.
- `data/style.css`: `colour-swatch` (20px circle, radius 50 %, no indicator, `background-color` from the provider) and
  `colour-swatch:checked` (ring: `box-shadow: 0 0 0 2px @window_bg_color, 0 0 0 3.5px currentColor` — use the swatch's
  colour via the provider's `color:`), `goal-edit-row` min-height 44.

## Tests (`tests/gui/test_streak_dialog.py`)
- `for_new()`: title "New Streak", save label "Create", save insensitive; period `daily` active; weekday box
  insensitive; times_row hidden; reminder label "Off ›"; goals list has exactly one empty row with its remove button
  hidden; goals group title "Goals — 1".
- Typing a name and a goal → save sensitive; clearing the goal → insensitive.
- Selecting `weekdays` → weekday box sensitive with Mon–Fri active; `n_per_week` → `times_row` visible; `monthly` →
  both hidden/insensitive.
- `add_goal_row` activation appends a row and updates the title "Goals — 2"; removing one restores; the only remaining
  row hides its remove button.
- Reminder popover: switching on + setting 20:00 → label "20:00 ›".
- Save (new): fills "75 Hard", swatch 4 (purple), weekdays Mon/Wed/Fri, allow skip on, reminder 20:00, goals
  ["A", "B"] → DB has a `Streak` with the right fields (`weekdays_mask == 0b0010101`, `reminder_time == 20:00`,
  `allow_skip`), goals positions 0/1, dialog closed, sidebar selection == the new streak, sidebar shows the row.
- `for_edit(seed 75 Hard)`: title "Edit Streak", save "Save", fields prefilled (name, swatch 0 checked, daily, 5 goal
  rows with names, reminder Off); rename goal 2 and delete goal 4, add "New goal", save → `update_streak` result:
  goal 2 renamed in place (same id), goal 4 `removed_on == today`, new goal at position 4; run/history stats unchanged
  (check `engine.runs` length still 3 with length 51).
- Cancel writes nothing.
- Register screen `new-streak` (dialog presented over the seeded window; render the dialog's child at 560×~900 — use
  `dialog.get_child()` after presenting) with the fixture values from design-spec §6 prefilled.

`scripts/check.sh --fast` green; `scripts/screenshot.sh new-streak` viewed with Read and compared to §6. No commits.
