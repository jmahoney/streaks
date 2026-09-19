# Phase 2 — window shell, sidebar, empty state (design 4f + the sidebar of 4a/4b)

Read `CLAUDE.md`, `docs/design-spec.md` §1, §2, §8, §9, §10 and this file. Phase 1's `engine.py`/`models.py` exist —
use them; do not add display logic to views (strings and numbers come from the engine).

## Deliverables
- `src/streaks/ui/window.blp` + `src/streaks/window.py` (`StreaksWindow`) — replace the Phase 0 placeholder.
- `src/streaks/ui/sidebar_row.blp` + `src/streaks/sidebar_row.py` (`StreaksSidebarRow : Gtk.ListBoxRow`).
- `src/streaks/ui/empty_view.blp` + `src/streaks/empty_view.py` (`StreaksEmptyView : Adw.Bin`).
- `src/streaks/widgets/__init__.py`, `src/streaks/widgets/grid_widgets.py` — `EmptyGridWidget`, `HeatmapWidget`,
  `StripWidget` (design-spec §10; all three now, since they share one drawing routine; later phases just use them).
- `src/streaks/settings.py` — `AppSettings` wrapper over `Gio.Settings("com.cheerschopper.Streaks")` exposing the
  engine `Settings` dataclass (`to_engine()`), `bind_window_state(window)`, and a `changed` GObject signal.
- `src/streaks/state.py` — `AppState`: owns the DB (`models.init_db()` at startup unless already bound), the
  `AppSettings`, `today()` via `clock`, `reload()` → `list[StreakData]` via `models.load_all`, and a `changed`
  signal emitted after every write helper the UI calls (views subscribe and rebuild).
- `data/style.css` — the classes from §9 that this phase needs: `colour-dot`, `today-dot`, `badge`, `sidebar-footer`,
  `sidebar-empty`.
- Use `scripts/add_ui.py <name>` to create/register each new blp/py pair so build lists stay in sync.
- Tests: `tests/gui/test_window.py` (replace), `tests/gui/test_sidebar.py`, `tests/gui/test_empty_view.py`,
  `tests/gui/test_widgets.py`.

## Behaviour
- `StreaksWindow`: `Adw.NavigationSplitView` (`min-sidebar-width: 280; max-sidebar-width: 280; sidebar-width-fraction:
  0.25`) with sidebar `Adw.NavigationPage` (title "Streaks", tag `sidebar`) and content `Adw.NavigationPage` (tag
  `content`). Content: `Adw.ToolbarView` → `Adw.HeaderBar` with `Adw.WindowTitle content_title` and end buttons
  `search_button` (`Gtk.ToggleButton`, icon `edit-find-symbolic`), `menu_button` (`Gtk.MenuButton`, icon
  `open-menu-symbolic`, menu model `primary_menu` with Preferences / Keyboard Shortcuts / About Streaks; actions
  `app.preferences`, `win.show-help-overlay`, `app.about` — only `about` needs to work now, the others may be
  present-but-no-op actions). Content `Gtk.Stack content_stack` with named pages `empty` (`StreaksEmptyView`), `today`
  (placeholder `Adw.StatusPage` titled "Today" for now) and `streak` (placeholder `Adw.StatusPage` titled by the
  selected streak name). Window actions: `win.new-streak` (Ctrl+N; for now a no-op that logs — Phase 4 wires it),
  `win.select-today`.
- Sidebar: `Adw.ToolbarView` → `Adw.HeaderBar` (title "Streaks", end `Gtk.Button new_button` icon `list-add-symbolic`,
  tooltip "New Streak", `action-name: "win.new-streak"`) → `Gtk.Box` vertical margin 8 spacing 2:
  `Gtk.ListBox sidebar_list` (`selection-mode: single`, styles `["navigation-sidebar"]`) whose rows are built in
  Python from `engine` data: the Today row (`StreaksSidebarRow` with `kind=today`, badge count from
  `engine.today_view(...).open_count`), then running streaks, then ended ones (only if `settings.show_ended`).
  Section headings "Running"/"Ended" are set with `set_header_func` as `Gtk.Label` styles `["caption-heading",
  "dim-label"]`, uppercase via `Gtk.Label` text "RUNNING"/"ENDED" (translatable, already uppercase in the string).
  A vexpand spacer then `Gtk.Label footer_label` "Everything stays on this machine." styles `["caption","dim-label",
  "sidebar-footer"]`. When there are no streaks: hide `sidebar_list` + footer and show `Gtk.Label sidebar_empty_label`
  "No streaks yet" (styles `caption dim-label sidebar-empty`); content stack shows `empty`.
- `StreaksSidebarRow` template children: `dot` (`Gtk.Box` 8×8, classes `colour-dot`; `today-dot` for Today), `name_label`,
  `meta_label` (caption dim-label; hidden for Today), `count_label` (bold; hidden for Today and ended), `badge_label`
  (`badge`; only for Today; hidden when 0). Colour applied via a per-row `Gtk.CssProvider` on `dot`
  (`background-color: <hex>`) — the only allowed inline CSS. Properties: `streak_id: int` (0 = Today).
  Ended rows get `opacity: 0.55`.
- Selection: `row-selected` → `state.selection = streak_id`; window switches `content_stack` to `today`/`streak`, sets
  `content_title` (Today: "Today" / "Sunday 13 September"; streak: name / `history.header_subtitle`). Selection is
  persisted to GSettings `sidebar-selection` and restored at startup (fall back to Today).
- After `state.changed`, the sidebar rebuilds rows but keeps the selection.
- `StreaksEmptyView`: per §8; button `create_button` "Create a streak" (`suggested-action`, `pill`) with
  `action-name: "win.new-streak"`.
- `EmptyGridWidget`/`HeatmapWidget`/`StripWidget`: `Gtk.Widget` subclasses with `set_cells(cells: list[Cell])`
  (`Cell` from engine), `cell_width`, `cell_height`, `gap`, `radius`, and for the heatmap `columns` derived from
  `len(cells)/7`. Implement `do_measure` (fixed natural size from cells), `do_snapshot` (rounded rects via
  `Gsk.RoundedRect.init_from_rect` + `Gtk.Snapshot.push_rounded_clip`/`append_color`, borders via `append_border`),
  `has_tooltip` + `query-tooltip` returning the cell tooltip under the pointer. Colours parsed with `Gdk.RGBA.parse`.
  Expose `cell_at(x, y) -> int | None` for tests.

## Tests (all with the seeded in-memory DB from `tests/gui/conftest.py`: create a `seeded_state` fixture that binds an
in-memory DB, seeds it, and returns an `AppState` with `Settings()` defaults and fake today)
- Window: split view sidebar min/max width 280; sidebar page title "Streaks"; content stack has pages
  `empty`,`today`,`streak`; `default-size` 1160×760; `content_title` shows "Today"/"Sunday 13 September" at start.
- Sidebar rows from seed: order [Today, 75 Hard, No snoozing…, Gym…, Clip fingernails, Couch to 5K]; each row's
  `name_label`, `meta_label`, `count_label` text equal the engine values ("Daily · 5 goals", "51", …, "Ended 4 Mar ·
  best 31" with count hidden); Today badge "2"; header labels "RUNNING" before 75 Hard and "ENDED" before Couch to 5K;
  dot colour of the 75 Hard row is `#3584e4` (read back from the provider/`Gtk.Widget.get_css_classes` or a `colour`
  property); ended row opacity 0.55; footer text.
- Selecting the 75 Hard row → stack page `streak`, title "75 Hard", subtitle "Daily · 5 goals · run 3"; selecting Today
  → page `today`. Selection survives `state.changed`. Restored from `sidebar-selection` at construction.
- `show_ended=False` → no ENDED section, no Couch to 5K row.
- Empty DB → content page `empty`, `sidebar_empty_label` visible, list hidden; empty view labels equal §8 strings;
  `create_button` has `suggested-action` and `pill` classes and `action-name` `win.new-streak`.
- Widgets: `EmptyGridWidget` natural size = 7×14 + 6×5 by 4×14 + 3×5; `HeatmapWidget` with 7×30 cells natural width
  30×13 + 29×4; `cell_at()` maps a point to the right index; tooltip text for a cell; `StripWidget` sizes.
  Render each widget offscreen via `Gtk.WidgetPaintable` → `Gtk.Snapshot` → `Gsk.Renderer.render_texture`
  (put the widget in a realized window first) and assert the centre pixel of cell 0 equals its fill colour
  (`Gdk.Texture.download` → bytes; tolerance ±2 per channel).

`scripts/check.sh --fast` must be fully green; run `ruff format` and `ruff check --fix`. Do not git commit.
