# Phase 5 — Streak history view (design 4b)

Read `CLAUDE.md`, `docs/design-spec.md` §4 (+ §1, §9, §10), `src/streaks/engine.py` (`history`, `History`,
`Cell`, `runs`), `src/streaks/widgets/grid_widgets.py` (`HeatmapWidget`, `StripWidget`) and the window code.

## Deliverables (via `scripts/add_ui.py`)
- `streak_view` — `StreaksStreakView : Adw.Bin`, content page `streak` in the window stack. Outer
  `Gtk.ScrolledWindow` → box margin 24/28 spacing 18:
  1. `tiles_box` (horizontal, homogeneous, spacing 14) with 4 `StreaksStatTile` children `tile_running`,
     `tile_unconfirmed`, `tile_confirmed`, `tile_hit`.
  2. Chart `card` (padding 16 18): `chart_title_label` (heading), `best_label` ("BEST", `caption-heading` accent,
     hidden unless `is_best`), `chart_caption_label` (caption dim, hexpand, wrap), `range_toggle`
     (`Adw.ToggleGroup` toggles `run` "This run" / `lifetime` "Lifetime"), `day_labels_box` (7 labels 10px dim),
     `heatmap` (`HeatmapWidget`), `legend_box` (4 entries built in Python: 11×11 `Gtk.Box` with class
     `chart-legend-swatch` + per-entry provider colour/border, caption label), `catch_up_link` (flat link-styled
     button, hidden when None; emits `catch-up` signal with streak id).
  3. `lower_grid` (`Gtk.Grid`, column-spacing 18, two columns; left column ~1.1× — use `Gtk.Box` homogeneous instead
     if `Gtk.Grid` proportions are awkward; the test checks children, not pixel widths):
     - `goals_card`: header "Per goal, this month" (`heading`, padding 12 16), `goal_bars_list` (`Gtk.ListBox`, rows
       `StreaksGoalBarRow`: `name_label` (ellipsize end), `bar` (`Gtk.ProgressBar` width-request 140), `ratio_label`
       (bold caption, width-chars 5, xalign 1); `bar` gets class `low` when the engine says so).
     - `runs_card`: header "Earlier runs", `runs_list` (`Gtk.ListBox`, rows `StreaksRunRow`: `title_label` "Run 2",
       `meta_label` caption dim, chevron `go-next-symbolic` dim, `strip` (`StripWidget` 7×18 gap 2)); activating a row
       switches the chart to that run (`history(run_index=…)`), with the `run` toggle re-labelled "Run 2" while a
       past run is shown; selecting the current run again restores "This run". Card hidden when no earlier runs.
- `stat_tile` — `StreaksStatTile : Gtk.Box` (`card`, vertical, padding 13 16): `value_label` (`title-1`),
  `caption_label` (caption dim). Style: `stat-accent` class on `value_label` when the tile's style is "accent",
  `dim-label` when "dim".
- Header wiring in the window for the `streak` page: `content_title` = name / `history.header_subtitle`;
  `checkin_button` ("Check in", `suggested-action`) → `win.select-today` and scrolls the Today view to that card
  (call `today_view.scroll_to_streak(id)`); `more_button` (`Gtk.MenuButton` `view-more-symbolic`) with menu
  "Edit…" (`win.edit-streak`), "End streak" (`win.end-streak`), "Delete…" (`win.delete-streak`). End → `Adw.AlertDialog`
  "End this streak?" body "It moves to Ended in the sidebar. Its history stays readable." responses cancel / end
  (destructive) → `models.end_streak(streak, today)`. Delete → `Adw.AlertDialog` "Delete 75 Hard?" body "Every
  check-in for this streak will be removed. This cannot be undone." → `models.delete_streak`, then select Today.
  Both notify state. The header buttons are visible only on the `streak` page (search/menu only on `today`/`empty`).
- `data/style.css`: `stat-accent` (colour `#1a68c7`), `goal-bar.low` / `progressbar.low > trough > progress`
  (`#e5a50a`), `chart-legend-swatch` (11×11 radius 3), `link-button`-like flat accent text for `catch_up_link`.

## Tests (`tests/gui/test_streak_view.py`, seeded, select 75 Hard)
- Tiles: values ["51","4","47","94%"], captions ["days running","unconfirmed","confirmed kept","goals hit"],
  `tile_running.value_label` has `stat-accent`.
- Chart: title "Run 3 · since 25 July", BEST visible, caption text per spec, toggle active `run`, heatmap cell count
  is a multiple of 7 and equals `len(history.weeks) * 7`, the cell for 2026-09-10 is outlined (`#a9c9ef`), the cell
  for 2026-09-08 fill is `#4b8fdb` (4 of 5 = 0.8), for 2026-09-07 `#1a68c7`, today's cell (3 of 5 = 0.6) is
  `#4b8fdb` per the scale (0.6 is not < 0.6), and no cells after today exist in the "this run" grid except padding
  in the final week which uses the `upcoming` colour `#f4f4f2`; legend labels ["all five","some","unconfirmed","missed"], `catch_up_link` label
  "4 days unconfirmed — catch up".
- `range_toggle` → `lifetime`: heatmap has 30×7 cells; cells for 2 Mar–13 May are `#f3c0c4` (missed) — check one.
- Goal bars: 5 rows, names in goal order, ratios ["9/9","9/9","6/9","8/9","9/9"], `bar.fraction` values, row 3's
  bar has class `low`.
- Earlier runs: 2 rows: ("Run 2", "14 May – 16 Jun · 34 days", 34 cells), ("Run 1", "2 Feb – 1 Mar · 28 days",
  28 cells). Activating Run 2 → chart title "Run 2 · 14 May – 16 Jun", BEST hidden, heatmap covers exactly the run's
  weeks; toggling `run` back after selecting current restores.
- Window header on `streak` page: title/subtitle, "Check in" button visible with `suggested-action`; on Today page the
  button is hidden. "Check in" → stack page `today`.
- Ended streak (Couch to 5K): tiles ["31","0","31","100%"]; for ended streaks the first tile shows the best run and
  its caption is "days, best run" (extend `engine.history` for this if Phase 1 did not — keep the change small and
  add a unit test); chart title "Run 1 · 2 Feb – 4 Mar"; `catch_up_link` hidden; header subtitle
  "Daily · 1 goal · ended 4 Mar".
- End streak via the action (respond `end`) → streak has `ended_on == today`, sidebar moves it under ENDED. Delete
  (respond `delete`) → gone from DB and sidebar, page `today`.
- Register screens `streak` (75 Hard, this run) and `streak-lifetime`.

`scripts/check.sh --fast` green; `scripts/screenshot.sh streak streak-lifetime` reviewed with Read against §4.
No commits.
