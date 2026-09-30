# Streaks — design specification

The UI/behaviour spec the app was built against, originally extracted from an HTML design mock.
It is the reference for layout, wording and colours; the golden snapshots in `tests/snapshots/`
are the visual source of truth for what actually ships. Code comments cite its sections as
`design-spec §N`. Every quoted string below is exact and must be wrapped in `_()` in code. The fixture date is **Sunday
13 September 2026**.

Design tokens (px, light theme; libadwaita's Adwaita already provides most of these — use style classes, not custom CSS,
unless the class is listed in §9):

| Token | Value | libadwaita equivalent |
|---|---|---|
| Sidebar width | 280 | `Adw.NavigationSplitView` `min-sidebar-width: 280; max-sidebar-width: 280` |
| Window default | 1160 × 760 (52 header + 708 content) | `default-width/height` |
| Sidebar bg / content bg | `#eceae8` / `#fafafa` | sidebar/window bg (automatic) |
| Card | white, 1px `rgba(0,0,0,.08)` border, radius 12 | `styles ["card"]` |
| Card row height | 46 | `Gtk.ListBox` row, default Adw row height |
| Accent blue | `#3584e4` (`#1a68c7` for chart "all done") | `accent`, `suggested-action` |
| Error red | `#c01c28` / text `#a51d2d` / tint `#fdf2f2` | `error`, `destructive-action` |
| Warning amber | `#e5a50a` | `warning` |
| Section heading | bold 10.5–11px, 0.05em letter-spacing, 45 % black, uppercase | `caption-heading` + `dim-label` (Adw.PreferencesGroup title) |
| Page title | bold 22px | `title-2` |
| Stat number | bold 26px | `title-1` |
| Card title | bold 14px | `heading` |
| Body | 13.5px | default |
| Meta/caption | 11–12px, 50 % black | `caption` + `dim-label` |
| Streak colours (5 swatches) | `#3584e4` blue, `#2ec27e` green, `#e5a50a` yellow, `#e01b24` red, `#9141ac` purple | stored as hex |

Chart cell colour scale (from the design's script), by fraction of goals done that day:

| Status / ratio | Fill | Border |
|---|---|---|
| ratio 0 (nothing done, answered kept) | `#e9e9e7` | — |
| < 0.3 | `#cfe2f8` | — |
| < 0.6 | `#92bdf0` | — |
| < 0.99 | `#4b8fdb` | — |
| 1.0 ("all five") | `#1a68c7` | — |
| unconfirmed (no check-in, no answer) | `#ffffff` | `#a9c9ef` 1px |
| missed | `#f3c0c4` | — |
| upcoming (future) | `#f4f4f2` | — |

Cells: 13×13, radius `max(2, round(13/4))` = 3, gap 4. Strips (banner, earlier runs, catch-up result): 8×22 gap 3
(banner), 7×18 gap 2 (earlier runs), 9×20 gap 3 (catch-up result), radius 2.

### Dark scheme ("Dark variant — amber accent")

Same six views in Adwaita dark; **only colours change, never layout**. Blue at 13px on a `#1e1e20` ground goes muddy
and the chart scale collapses, so dark runs on **amber**: `#ffa348` for fills, buttons and the top of the chart scale,
with dark ink (`#2a1c09`) on the fills rather than white, and `#ffbe6f` for accent-coloured text (flat `accent`
buttons, banner title, catch-up link). Implemented as an accent override in `data/style.css` under
`@media (prefers-color-scheme: dark)` (`--accent-bg-color` / `--accent-fg-color` / `--accent-color`), so every
libadwaita `accent`/`suggested-action`/check/switch picks it up.

| Token | Light | Dark |
|---|---|---|
| Streak colours (stored hex stays the light value) | `#3584e4` `#2ec27e` `#e5a50a` `#e01b24` `#9141ac` | `#ffa348` `#8ff0a4` `#f9f06b` `#e01b24` `#dc8add` |
| Today dot / ended dot | `rgba(0,0,0,.55)` / `#c0bfbc` | `rgba(255,255,255,.61)` / `#5c5c63` |
| Catch-up banner bg / border / title | `#f4f8fe` / `#bcd4f2` / `#1a5fb4` | `#332a1c` / `#5e4a2b` / `#ffbe6f` |
| Check-in card footer | `#fcfcfc` | `#35353a` |
| Stat tile accent number | `#1a68c7` | `#ffa348` |
| Goal bar "low" fill | `#e5a50a` | `#c9822c` |
| Catch-up missed day header bg / border / text | `#fdf2f2` / `#f0d7d9` / `#a51d2d` | `#3a2224` / `#5a2f33` / `#ff938a` |

Chart cell scale in dark (`streaks.theme.DARK_PALETTE`; ratio thresholds unchanged):

| Status / ratio | Light | Dark |
|---|---|---|
| ratio 0 | `#e9e9e7` | `#2c2c30` |
| < 0.3 | `#cfe2f8` | `#4a3a22` |
| < 0.6 | `#92bdf0` | `#8a5f22` |
| < 0.99 | `#4b8fdb` | `#c9822c` |
| 1.0 | `#1a68c7` | `#ffa348` |
| unconfirmed | `#ffffff` + `#a9c9ef` border | hollow (transparent) + `#6b5230` border |
| missed | `#f3c0c4` | `#8e4a50` |
| upcoming | `#f4f4f2` | `#232326` |
| empty-state hint cell (§8) | `#cfe2f8` | `#7a4d18` |

The engine never sees hex: it emits the tokens `engine.CHART_*` (plus `theme.CHART_EMPTY_HINT`) and
`streaks.theme.resolve()` picks the palette for the active scheme when a grid widget or legend swatch paints. Grid
widgets and the streak view repaint on `Adw.StyleManager:dark` (`theme.watch()`), so a live scheme switch needs no
data reload. Dialog backgrounds and everything else not listed here are libadwaita's own dark colours.

---

## 1. Window frame (all screens)

`Adw.ApplicationWindow` → `Adw.NavigationSplitView`.

**Sidebar** (`Adw.NavigationPage`, title "Streaks") → `Adw.ToolbarView`:
- top: `Adw.HeaderBar`. Title "Streaks" (bold 14.5). End: `Gtk.Button` icon `list-add-symbolic`, tooltip "New Streak",
  action `win.new-streak`.
- content: `Gtk.Box` vertical, margin 8, spacing 2 (see §2).

**Content** (`Adw.NavigationPage`) → `Adw.ToolbarView`:
- top: `Adw.HeaderBar`, `title-widget: Adw.WindowTitle` (title + subtitle, see per-screen). End buttons vary per screen:
  - Today: search toggle `edit-find-symbolic` (⌕), primary menu `open-menu-symbolic` (☰).
  - Streak: `Gtk.Button` "Check in" `suggested-action`; `Gtk.MenuButton` icon `view-more-symbolic` (⋯) with menu
    Edit… / End streak / Delete….
  - Empty: primary menu only.
- content: `Gtk.Stack` with pages `empty`, `today`, `streak`.

Primary menu (☰): "Preferences" (`app.preferences`, Ctrl+,), "Keyboard Shortcuts" (Ctrl+?), "About Streaks".

## 2. Sidebar (4a/4b/4f)

Vertical box, padding 8, gap 2:

1. **Today row** — height 40, radius 9, selected bg `#dcd9d5` (= selected sidebar row). Left: 8×8 square (radius 2) at
   55 % black. Label "Today" bold 13.5 when selected, regular when not. Right: badge pill (min-width 20, height 20, padding
   0 6, radius 10, bg accent, bold 11 white) showing the number of streaks with an open check-in today (`2` in the
   fixture). Badge hidden when 0.
2. Section label "RUNNING" — padding 14 10 6.
3. One **streak row** per running streak — height 46, padding 0 10, radius 9. Left: 8×8 circle in the streak colour.
   Middle: name 13.5 (ellipsized), meta caption 11 at 48 % black. Right: current run count, bold 13 at 72 % black.
   Selected row: bg accent, all text white (name bold), dot white at 90 %.
   Fixture rows, in order:
   | name | meta | count |
   |---|---|---|
   | 75 Hard | Daily · 5 goals | 51 |
   | No snoozing the alarm | Mon–Fri | 12 |
   | Gym, three times a week | 3× a week · 2 goals | 9 |
   | Clip fingernails | Monthly | 4 |
4. Section label "ENDED" (only when there are ended streaks and the "Show ended runs in the sidebar" preference is on).
5. Ended rows at 55 % opacity, dot `#c0bfbc`, no count. Fixture: "Couch to 5K" / "Ended 4 Mar · best 31".
6. Spacer (vexpand).
7. Footer caption 11 at 42 % black, padding 0 10 6: "Data is stored locally."

Empty (4f): sidebar content is just a caption at padding 14, 42 % black: "No streaks yet". No Today row, no footer.

Meta string rules (engine): `period_label()` is `"Daily"`, `"Mon–Fri"` (weekday names abbreviated, en-dash for a contiguous range, otherwise comma-separated "Mon, Wed, Fri"), `"{N}× a week"` or `"Monthly"`. A single-goal streak's meta is just the period label; with more goals it is `"{period} · {n} goals"` (`ngettext`). Ended: `"Ended {d Mon} · best {n}"`.

## 3. Today view (4a) — content pane

Content padding 24 28, vertical gap 18, background `#fafafa`.

Header bar: `Adw.WindowTitle` title "Today", subtitle "Sunday 13 September" (`%A %-d %B`).

**Header row** (align end, gap 14):
- Left: title "Sunday 13 September" (bold 22 → `title-2`), subtitle 13 at 52 %: "2 check-ins open · 4 earlier days
  unconfirmed" (digits, joined with " · "; second clause omitted when 0 unconfirmed; "No check-ins open" when 0 open;
  `ngettext` singular/plural per clause, no trailing period).
- Right: `Gtk.Button` "Check in for another day" (bordered, bold 12.5).

**Quiet-days banner** (only when the selected/any running streak has unconfirmed days; one banner per streak with quiet
days, 75 Hard in the fixture): box, bg `#f4f8fe`, border `#bcd4f2`, radius 12, padding 14 16, gap 16.
- Text: bold 13.5 `#1a5fb4` "Four days without a check-in — 9 to 12 September"; below, 12 at 60 %: "The 51-day run
  continues. Unconfirmed days do not end a run."
- Middle: `StripWidget` of the last 24 due days (8×22, gap 3): kept days `#1a68c7`, unconfirmed white w/ `#a9c9ef` border.
- Right: `Gtk.Button` "Catch up" `suggested-action` → opens Catch-up dialog (§5) for that streak.

**Check-in cards**: two columns (grid `repeat(2, minmax(0,1fr))`, gap 18, align start). Each card is appended to the
column that currently has fewer rows (fixture: 75 Hard left; Gym, No snoozing, Clip fingernails right).

`CheckInCard` (`card`, overflow hidden):
- Header row: padding 12 16, bottom border 7 % black. 8×8 colour dot, name bold 14, right meta caption 11.5 at 50 %.
- Goal rows (height 46, padding 0 16, bottom border 6 % black): 24×24 check box (radius 6; unchecked: white with
  `#c0bfbc` border; checked: accent bg, white ✓) — use `Gtk.CheckButton` with `selection-mode` style — label 13.5;
  when done: label at 50 % with strike-through, plus right caption with time done `HH:MM` (11 at 38 %).
- Footer (padding 11 16, bg `#fcfcfc`, gap 10): `Gtk.ProgressBar` (6px, radius 3, track `#e6e4e1`, fill accent),
  caption "3 of 5", flat link-styled button "Mark day missed" (12.5, `#1c71d8`). Footer only for daily/weekday cards
  with >1 goal; single-goal cards have no footer.

**Single-goal card** (a streak with exactly one active goal, when due): one row, padding 12 16, gap 12. A 24×24 check box (`selection-mode`), then a vertical box: [8×8 colour dot, gap 8, name bold 14 (`heading`)] over a subtitle caption 11.5 at 50 % (margin-top 2). There's no header separator and no footer. Subtitle `"{period} · {status}"`, where status is `"done {HH:MM}"` when ticked today, otherwise daily/weekdays `"day {k}"`, n_per_week `"{done} of {N} this week"`, monthly `"{n} days left"` (`"done this month"` once the month is done). When ticked, the name gets `strike` + `dim-label`. Activating the row toggles the check. A weekday streak that isn't due today keeps the "Not today" card. A goal removed mid-period still counts for that period, so a streak collapsed to one goal shows its multi card until the period ends.

Fixture cards:
- **75 Hard** — meta "3 of 5 · day 51"; goals: Progress photo ✓ 07:12, 45 min outdoors ✓ 07:55, 45 min second workout ☐,
  Read 10 pages ☐, Stick to the diet ✓ 21:30; footer 60 %, "3 of 5", Mark day missed.
- **Gym, three times a week** — meta "2 of 3 this week"; goals: 45 min session ☐, Log the weights ☐; no footer.
- **No snoozing the alarm** — meta "Not today"; no goal rows; body caption (padding 12 16, 12.5 at 50 %):
  "Weekdays only. Next check-in Monday 14 September."
- **Clip fingernails** is one row, subtitle "Monthly · 17 days left".

Meta rules (engine): daily/weekdays due today → `"{done} of {n} · day {k}"` (k = day number within current run,
counting today); n_per_week → `"{sessions} of {N} this week"`; weekdays not due → `"Not today"` and body
`"Weekdays only. Next check-in {A d B}."` (or `"{Mon, Wed} only. …"` per mask); monthly → `"Due this month"` (or
`"Done this month"`) and goal-row caption `"{n} days left"`.

Interactions: toggling a goal writes/removes a `GoalCheck` for the check-in day with `done_at = now`; card meta,
progress and time captions update; sidebar badge updates. "Mark day missed" → `Adw.AlertDialog` "Mark today as missed?"
(body "This ends run 3 at 50 days." — engine-computed) → writes `DayAnswer(missed)`. "Check in for another day" →
`Gtk.Popover` with `Gtk.Calendar` limited to the backfill window; picking a day shows the same view for that day with
title "{A d B}" and the header subtitle "Checking in for an earlier day." plus a "Back to today" button.

## 4. Streak history (4b)

Header: `Adw.WindowTitle` "75 Hard" / "Daily · 5 goals · run 3"; end: "Check in" (`suggested-action`) → selects Today
and scrolls to the card; ⋯ menu.

Content padding 24 28, gap 18:

**Stat tiles** — 4 equal `card`s (padding 13 16): number bold 26 (`title-1`) + caption 11.5 at 50 %.
| number | caption | colour |
|---|---|---|
| 51 | days running (the run shown) | `#1a68c7` (accent) |
| 51 | days, longest run (all time, the open run included) | 85 % black |
| 3 | runs (all time, the open run included) | 85 % black |
| 94% | goals hit (all runs, finished kept/partial periods) | 85 % black |
Captions: "days running" / "weeks running" / "months running" per period kind, and likewise "days, longest run".
An ended streak's first tile reads "days, last run". Unconfirmed days show only in the catch-up link.

**Chart card** (padding 16 18):
- Title row (baseline, gap 12): bold 14 "Run 3 · since 25 July"; tag "BEST" bold 10.5 accent (only if this is the best
  run); caption 12 at 50 % (expands): "Shade shows the share of goals completed. Outlined days are unconfirmed."; right:
  `Adw.ToggleGroup` {"This run", "Lifetime"} (pill-ish segmented, 11.5).
- Grid (margin-top 14, gap 6): day-label column 18 wide with labels `M, "", W, "", F, "", ""` (10px at 40 %), then
  weeks as columns (7 cells each, gap 4). "This run" shows the current run from its start (rows Mon–Sun, first column
  padded with `upcoming`-coloured blanks before the start); "Lifetime" shows the last `weeksShown` (30) weeks ending this
  week. The last 3 cells (future days of this week) use `upcoming`. Tooltip per cell: "{done} of {n} goals",
  "no check-in yet — unconfirmed", "missed — run ended", "upcoming".
- Legend (margin-top 14, gap 16): 11×11 radius 3 squares + 11px captions: `#1a68c7` "all five" (word for goal count;
  "all {n}" → "all five", "done" when 1 goal), `#92bdf0` "some", outlined "unconfirmed", `#f3c0c4` "missed". Spacer.
  Right: link button 12 `#1c71d8` "4 days unconfirmed — catch up" (hidden when 0) → Catch-up dialog.

**Lower grid** (columns 1.1fr / 1fr, gap 18):
- **Per goal, all time** card: header row padding 12 16 bold 13.5. Rows (padding 10 16): goal name 13 (ellipsized),
  140×6 bar (track `#ebebe9`), ratio bold 12 at 60 % 7 chars wide right-aligned "109/109". Bar colour accent `#1a68c7`, or
  `#e5a50a` when the ratio is below 75 %. Fixture: Progress photo 109/109, 45 min outdoors 109/109, Second workout
  83/109, Read 10 pages 99/109, Stick to the diet 109/109. Denominator = every kept or partial period across all
  time, today included once anything is ticked; numerator = those where the goal was done (a "Kept" answer counts
  for every goal).
- **Earlier runs** card: header "Earlier runs". One row per finished run, newest first (padding 12 16): bold 13 "Run 2",
  caption 11.5 "14 May – 16 Jun · 34 days", spacer, "›" 12 at 40 %; below, `StripWidget` (7×18, gap 2) one cell per day
  of the run using the chart scale. Fixture: Run 2 (14 May – 16 Jun · 34 days), Run 1 (2 Feb – 1 Mar · 28 days).
  Clicking a row switches the chart to that run (title "Run 2 · 14 May – 16 Jun").

Stats (engine): running = due periods from run start through today inclusive; unconfirmed = past due periods in the run
with no checks and no answer; confirmed kept = periods with status kept; goals hit % = checks done ÷ (goals × due
periods elapsed in the run, excluding today) rounded.

## 5. Catch-up dialog (4c)

`Adw.Dialog`, `content-width: 560`, title "Catch up". `Adw.ToolbarView`:
- top `Adw.HeaderBar` (`show-start-title-buttons: false; show-end-title-buttons: false`): start `Gtk.Button` "Cancel";
  title `Adw.WindowTitle` "Catch up" / "75 Hard · 4 days"; end `Gtk.Button` "Save" `suggested-action` (insensitive until
  at least one day is answered).
- content: `Gtk.ScrolledWindow` (natural-height, no horizontal scrolling) around a box, padding 18, gap 12.
  1. Caption 12.5 at 58 %: "Unticked goals on a day with any ticks are recorded as missed. Days with no ticks stay
     unconfirmed."
  2. One `CatchUpRow` "card" per unconfirmed day (oldest first), gap 12 between cards:
     - **Header** (padding 10 16, bottom border): left, bold 13.5 date "Wednesday 9 September" (`%A %-d %B`) over
       caption 11.5 status text at 55 % opacity (full opacity, red, on a missed/partial day); right, a flat
       accent-text link button, visible except on a ticked (kept/partial) day. Status text and link, derived
       entirely from the day's own ticks:
       | Ticks | Status text | Link |
       |---|---|---|
       | none, not marked missed | "Unconfirmed" | "Mark missed" |
       | none, marked missed (link clicked) | "Missed" | "Undo" |
       | some but not all | "{done} of {n} kept · {missed} missed" | hidden |
       | all | "All {n} kept" ("Kept" for a 1-goal streak) | hidden |
       Clicking "Mark missed" answers the day missed with no goals ticked; "Undo" clears that back to unconfirmed.
       Ticking (or unticking) any goal always clears an explicit "Mark missed".
     - **Goal list**: a `Gtk.ListBox` of one row per active goal (height 38, padding 0 16, top border), each a
       `Gtk.CheckButton` filling the row (unticked by default; the row itself is not activatable, so a click has one
       toggle path). Ticked goals dim to 60 % opacity.
     - A day with any tick short of all goals gets class `missed`: the whole card's border turns red
       (`#f0d7d9`; dark `#5a2f33`), the header background turns red (`#fdf2f2`; dark `#3a2224`), and the header's
       date/status text turn red (`#a51d2d`; dark `#ff938a`) at full opacity — and each *unticked* goal row's label
       also turns that red. A day marked missed via the link (no ticks) gets the same `missed` class on the card,
       but no goal row is individually flagged (none are ticked).
  3. **Result card** (padding 14 16): bold 13 "Result of these answers"; `StripWidget` 9×20 gap 3 of the last 24 due
     days reflecting the pending answers; caption 12, `dim-label` normally, `error` (red) when an answer would end the
     run — sentence(s) from the engine:
     - Ends the run: "Run {idx} ends on {day} at {n} day(s)." (`_ends_sentence`), plus, when a new run begins the same
       save, "Run {next idx} starts on {day} at {n} day(s)." for that run.
     - Otherwise: "Run {idx} continues at {n} day(s)."
     - Either way, appended when any unconfirmed day is left untouched: "{n} day(s) unconfirmed."
     (`engine.catch_up_preview`/`_preview_summary`; `ngettext` singular/plural throughout.)

Fixture state for the `catch-up-missed` snapshot: 9 Sep — all goals ticked (kept); 10 Sep — untouched (stays
unconfirmed); 11 Sep — every goal ticked except "45 min second workout" (partial/missed, red); 12 Sep — all goals
ticked (kept). Result: "Run 3 ends on 11 September at 48 days. Run 4 starts on 12 September at 2 days. 1 day
unconfirmed." Default (`catch-up`) snapshot: nothing ticked on any day; result "Run 3 continues at 51 days. 4 days
unconfirmed."

Save: writes one `DayAnswer` per answered day (derived from ticks, per the table above) in one transaction, closes,
refreshes Today + history.

## 6. New streak dialog (4d) — also used for Edit

`Adw.Dialog`, `content-width: 560`. Header: "Cancel" / title "New Streak" ("Edit Streak" in edit mode) / "Create"
("Save") `suggested-action`, insensitive until name non-empty; in multi mode, needs ≥2 non-empty goals.

Content padding 18, gap 18 (use `Adw.PreferencesPage` + `Adw.PreferencesGroup`s):

1. Group (no title), `card` list:
   - `Adw.EntryRow` **name_row**.
   - `Adw.ActionRow` title "Colour"; suffix: 5 × 20px circles (gap 10) in the swatch colours; selected one has a ring
     (2px white + 1.5px in its colour). `Gtk.CheckButton`s in one group with class `colour-swatch`.
   - Below the list (inside the same group), a flat button **"Add more goals"** (`list-add-symbolic` + label, both `accent`) with the dim hint "— for a checklist, e.g. a morning routine" (hint shown in New mode only).

   **Single mode** (default for New; Edit of a 1-goal streak): name_row title "Name"; Goals group hidden. Save needs a non-empty name. The name is both the streak name and its goal.

   **"Add more goals"** switches to **multi mode**. The name text moves into goal 1 (Edit keeps that goal's id), an empty goal 2 row is added (placeholder "Goal 2"), name_row empties, its title becomes "Streak name", and it takes focus. The button hides. The Goals group (title "Goals", placed **between** group 1 and Period) shows. Its description is "“{text}” moved from the name field to goal 1." (New mode, only when text was moved) or "New goals apply from the current period. Earlier periods keep their recorded shade." (Edit mode).

   Multi-mode goal rows: drag handle, flat entry (placeholder "Goal {n}" by position), remove button. Last row is `Adw.ButtonRow` "Add a goal". Save needs a non-empty streak name and at least 2 non-empty goals. Removing a goal when two remain **collapses back to single mode**: the remaining goal's text goes into name_row (title "Name"), the Goals group hides and "Add more goals" shows.

2. Group title "Period", description (below the list, caption 11.5 at 45 %): "Every goal in a streak shares this period."
   - Row 1 (padding 10, 4 equal columns gap 6): `Adw.ToggleGroup` homogeneous: "Daily" | "Weekdays" | "N a week" |
     "Monthly". Selected: accent bg, bold white; others bg `#f2f1ef`.
   - Row 2 (padding 11 16): 7 × 30px circular `Gtk.ToggleButton`s "M T W T F S S" (gap 8). Sensitive (opacity 1) only
     when "Weekdays" is selected; otherwise opacity .4 (insensitive). Default for Weekdays: Mon–Fri ticked.
   - Row 2b (`Adw.SpinRow` "Times a week", 1–7, default 3) — visible only when "N a week" is selected (not in the mock;
     required for the period to be definable).
   - Row 3: `Adw.ActionRow` "Reminder", subtitle "A check-in notification each period", suffix label "20:00 ›" →
     activates a `Gtk.Popover` with hour/minute `Gtk.SpinButton`s and an "Off" switch. Stored only (delivery deferred).
   - Row 4: `Adw.SwitchRow` "Allow one skip a week", subtitle "A skipped period won't break the run". Default off.

Edit mode adds a last group with `Adw.ButtonRow` "Delete streak" (`destructive-action`). It closes the dialog and runs `win.delete-streak` (the existing confirmation).

Models: a streak with exactly one goal always stores that goal under the streak's name.

Create: inserts `Streak` + `Goal`s (positions in order) in one transaction, closes, selects the new streak in the sidebar.
Edit: updates name/colour/period/reminder/allow_skip; goals removed get `removed_on = today` (newly removed only); new goals get `added_on = today` and count from the current period on.

## 7. Preferences (4e)

`Adw.PreferencesDialog` (content-width 660), one `Adw.PreferencesPage`:

- Group "Check-ins":
  - `Adw.SwitchRow` "Reminders", subtitle "Set per streak" — GSettings `reminders` (default true).
  - `Adw.ActionRow` "Day starts at", subtitle "Late-night check-ins count for the day before", suffix "04:00 ›" (time
    popover) — GSettings `day-start-minutes` (default 240).
  - `Adw.SpinRow` "Backfill window", subtitle "How far back a day can be answered for", value shown as "2 days" —
    GSettings `backfill-days` (default 2, range 0–14).
- Group "Runs":
  - `Adw.SwitchRow` "Keep counting through unconfirmed days", subtitle "Runs end only on a missed goal" —
    `count-through-unconfirmed` (default true). When off, an unconfirmed day older than the backfill window ends the run.
  - `Adw.SwitchRow` "Show ended runs in the sidebar", subtitle "Old runs stay readable either way" — `show-ended`
    (default true).
- Group "Data", description "Data is stored locally.":
  - `Adw.ActionRow` "Export everything", activatable, suffix `go-next-symbolic` → `Gtk.FileDialog.save` default name
    `streaks-export-{YYYY-MM-DD}.json` → `export.dump()` JSON of all tables.
  - `Adw.ActionRow` "Delete all data" (title class `error`), activatable → `Adw.AlertDialog` "Delete all data?" body
    "Every streak, goal and check-in on this machine will be removed. This cannot be undone." responses Cancel /
    "Delete" (destructive) → `models.delete_all()` → window shows the empty state.

Also GSettings: `window-width`, `window-height`, `window-maximized`, `sidebar-selection` (last selected streak id or 0
for Today).

## 8. Empty state (4f)

Sidebar: caption "No streaks yet" (see §2). Content: centred vertical box (gap 16, horizontal padding 80):
- `EmptyGridWidget`: 7 columns × 4 rows of 14×14 cells, radius 4, gap 5, all `#e9e9e7` except the last (bottom-right)
  `#cfe2f8` (`#2c2c30` / `#7a4d18` in dark).
- Title bold 19 "No streaks yet" (margin-top 8) → `title-2`.
- Body 13.5/1.6 at 55 %, max width 420, centred: "A streak is a set of goals repeated on a schedule."
- `Gtk.Button` "Create a streak" `suggested-action` + `pill`, margin-top 4 → `win.new-streak`.

Header title is "Streaks" with the primary menu button only.

## 9. Custom CSS allowed (`data/style.css`)

Only these classes; everything else must be a libadwaita style class:
`colour-dot` (8×8 circle), `today-dot` (square) / `ended-dot`, `streak-blue|green|yellow|red|purple` (a streak's
colour on dots and swatches — `theme.colour_class(stored_hex)`; never an inline provider, so the dark hues apply),
`badge` (pill count), `catchup-banner` (+ `.title`), `catchup-day` (+ `.missed`, `.header`, `.date`, `.status`),
`catchup-goals`, `catchup-goal` (+ `.ticked`, `.missed`), `colour-swatch` (+ `:checked` ring), `stat-accent`
(`#1a68c7` number), `strike` (strike-through label), `goal-bar.low` (amber), `chart-legend-swatch`, `sidebar-footer`.
Cards use `card`; section headings use `caption-heading dim-label`.
Every colour in the stylesheet is a `:root` CSS variable with its dark value in the
`@media (prefers-color-scheme: dark)` block at the end — add new colours the same way.

## 10. Custom widgets (`src/streaks/widgets/`)

All three subclass `Gtk.Widget`, take a list of cell specs (`fill`, `border`, `tooltip`) and draw with `do_snapshot`
(`Gsk.RoundedRect` + `Gtk.Snapshot.append_color`/`append_border`), implementing `do_measure` from cell size/gap and
`query-tooltip` for per-cell tooltips. Colours arrive as `engine.CHART_*` tokens (or plain hex) and are resolved for
the active scheme through `streaks.theme.resolve()` at paint time; the widget has no other logic.
- `HeatmapWidget` — 7 rows × N columns (column-major weeks), cell 13, gap 4, radius 3.
- `StripWidget` — 1 row, configurable `cell_width`, `cell_height`, `gap`, radius 2.
- `EmptyGridWidget` — 7 × 4 fixed grid, cell 14, gap 5, radius 4.
