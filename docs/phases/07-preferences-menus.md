# Phase 7 — Preferences dialog, primary menu, search, window state (design 4e)

Read `CLAUDE.md`, `docs/design-spec.md` §7 (+ §1), `src/streaks/settings.py` (`AppSettings`), `export.py`,
`models.delete_all`, and the window code.

## Deliverables
- `preferences_dialog` (via `scripts/add_ui.py`) — `StreaksPreferencesDialog : Adw.PreferencesDialog`
  (`content-width: 660`), one `Adw.PreferencesPage` with groups:
  - "Check-ins": `reminders_row` (`Adw.SwitchRow` "Reminders" / "Per streak, at the time you set"),
    `day_start_row` (`Adw.ActionRow` "Day starts at" / "Late-night check-ins count for the day before", suffix
    `day_start_label` "04:00" + `go-next-symbolic`, activatable → `day_start_popover` with hour/minute spins),
    `backfill_row` (`Adw.SpinRow` "Backfill window" / "How far back a day can be answered for", 0–14; the row's
    value is shown as "2 days" via a suffix label `backfill_label` bound to the value with `ngettext("%d day",
    "%d days")` while the spin itself stays numeric).
  - "Runs": `count_through_row` (`Adw.SwitchRow` "Keep counting through unconfirmed days" / "A run ends only when you
    mark a goal missed"), `show_ended_row` (`Adw.SwitchRow` "Show ended runs in the sidebar" / "Old runs stay readable
    either way").
  - "Data" (description "Everything stays on this machine. There is no account."): `export_row` (`Adw.ActionRow`
    "Export everything", activatable, suffix `go-next-symbolic`) → `Gtk.FileDialog.save` (initial name
    `streaks-export-YYYY-MM-DD.json`) → `export.dump_json(path)`; `delete_row` (`Adw.ActionRow` "Delete all data",
    title has class `error`, activatable) → `Adw.AlertDialog` heading "Delete all data?" body "Every streak, goal and
    check-in on this machine will be removed. This cannot be undone." responses cancel / delete (destructive) →
    `models.delete_all()` → `state.notify_changed()` (window shows the empty state).
  - All rows bind to `Gio.Settings` keys with `settings.bind(...)` (`reminders`, `backfill-days`,
    `count-through-unconfirmed`, `show-ended`); `day-start-minutes` via the popover. `AppSettings.changed` →
    `state.notify_changed()` so views re-evaluate (e.g. hiding ENDED when `show-ended` is off, run recomputation when
    `count-through-unconfirmed` changes).
- `src/streaks/main.py`: `app.preferences` (Ctrl+comma) presents the dialog over the active window; keep `app.about`;
  add `win.show-help-overlay` via `src/streaks/ui/shortcuts.blp` (`Gtk.ShortcutsWindow` with sections: New streak
  Ctrl+N, Preferences Ctrl+comma, Search Ctrl+F, Quit Ctrl+Q, Keyboard shortcuts Ctrl+question) registered in
  the gresource as `gtk/help-overlay.ui` so GTK auto-wires it.
- Sidebar search: `search_button` toggles a `Gtk.SearchBar` (`search_bar`, `search_entry`) above the sidebar list;
  typing filters streak rows by case-insensitive substring of name (Today row and headers stay; empty section headers
  hide); Ctrl+F focuses it; Escape closes and clears.
- Window state: bind `window-width`/`window-height`/`window-maximized` (save on close, restore at construction)
  via `AppSettings.bind_window_state(window)`.
- Export format: `{"version": 1, "exported_at": ISO, "streaks": [...], "goals": [...], "checks": [...], "answers":
  [...]}` — whatever Phase 1's `export.dump()` produces; do not change it.

## Tests (`tests/gui/test_preferences.py`, memory GSettings backend)
- Row titles/subtitles exact; group description; `delete_row` title has `error` class.
- Toggling `show_ended_row` off → GSettings `show-ended` False → the seeded window's sidebar loses the ENDED
  section; on → back.
- `backfill_row` value 5 → `backfill-days` 5 and `backfill_label` "5 days"; 1 → "1 day".
- `day_start_popover`: set 02:30 → `day-start-minutes` 150 and `day_start_label` "02:30"; `clock.today(150)` at fake
  now 2026-09-14 02:00 (`STREAKS_FAKE_NOW`) → 2026-09-13.
- `count_through_row` off → 75 Hard's runs change (an unconfirmed day older than backfill ends the run): sidebar
  count for 75 Hard becomes the engine's new value; assert equality with `engine.current_run(...)` under
  `Settings(count_through_unconfirmed=False)`.
- Export: monkeypatch `Gtk.FileDialog.save` to call back with a tmp path (or call the dialog's `_export_to(path)`
  helper directly), assert the JSON loads, has `version == 1` and 5 streaks.
- Delete all: activate `delete_row`, respond `delete` → all tables empty, window stack page `empty`.
- Search: type "gym" → only the Gym row (+ Today row) visible; clear → all back; Escape closes the bar.
- Window state: set default size 900×650 and `close()` → GSettings keys updated; a new window reads them back.
- Shortcuts window: `win.show-help-overlay` activates without error and the overlay lists "New streak".
- Screen `preferences` (dialog child at 660 × natural height).

`scripts/check.sh --fast` green; screenshot reviewed against §7. No commits.
