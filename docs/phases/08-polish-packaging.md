# Phase 8 — polish, i18n, Flatpak packaging

Read `CLAUDE.md`, `docs/design-spec.md`, and skim every `src/streaks/*.py` / `.blp`.

## Deliverables
1. **Goal drag-reorder** in the streak dialog: `Gtk.DragSource` on each `StreaksGoalEditRow.handle` and a
   `Gtk.DropTarget` on `goals_list` (content type: the row object via `GObject.TYPE_PYOBJECT` / `Gdk.ContentProvider`).
   Dropping reorders the rows; positions are saved in row order. Also provide keyboard fallback actions
   `row.move-up` / `row.move-down` (Alt+Up/Down when a goal entry is focused). Tests: call the drop handler
   directly with (source row, target index) and assert order; keyboard actions reorder; save persists positions.
2. **Keyboard**: verify the accelerators listed in `shortcuts.blp` all work (`app.set_accels_for_action`); Today view:
   Space/Enter on a focused goal row toggles it (row activation already does; make sure `goals_list` is focusable).
3. **Reminders (stored only)**: ensure `reminder_time` round-trips through create/edit and export; nothing schedules
   notifications yet — document this in `README.md` under "Not yet implemented".
4. **i18n pass**: every user-visible string in `.blp` uses `_("…")`; every Python string uses `_()`/`ngettext` from
   `gettext`; `po/POTFILES` complete (`scripts/check_templates.py` already checks file lists — extend it with a
   check that no `label:`/`title:`/`subtitle:`/`tooltip-text:`/`placeholder-text:` in a `.blp` has an untranslated
   literal, and that `.py` files don't call `Gtk.Label(label="literal")` without `_`). Run `meson compile -C _build
   streaks-pot` and commit the generated `po/streaks.pot`.
5. **Ended-streak read-only behaviour**: Today never shows cards for ended streaks; the streak view for an ended
   streak hides "Check in" and the catch-up link (Phase 5 test exists — confirm) and the ⋯ menu offers only Delete….
6. **Startup robustness**: `models.init_db()` creates the data dir; a corrupt/unwritable DB shows an
   `Adw.AlertDialog` with the path and quits instead of a traceback. Test with `STREAKS_DATA_DIR` pointing at a file.
7. **Flatpak**: `scripts/flatpak.sh build` must succeed (`flatpak-builder --user --install --force-clean`), and
   `flatpak run com.cheerschopper.Streaks` must open the window. Fix whatever the manifest needs (e.g. blueprint
   module build options `-Ddocs=false`, python install paths, `--env=PYTHONPATH` not needed if `pkgdatadir` on
   `sys.path`). Add `scripts/flatpak.sh test` that runs `flatpak run --command=python3 com.cheerschopper.Streaks -c
   "import peewee, streaks"` with `PYTHONPATH=/app/share/streaks` to prove the bundle imports (deterministic check).
8. **README.md**: purpose, screenshots (`_build/screenshots` is gitignored — reference `docs/screenshots/*.png`
   copied from the approved goldens), build/run/test/flatpak commands, the phase/agent workflow, and known gaps
   (reminder delivery, narrow layout, dark variant — the design only covered the desktop light variant).
9. **CI**: `.github/workflows/ci.yml` runs `STREAKS_HEADLESS=1 scripts/check.sh` including snapshots.

`scripts/check.sh` (full, with snapshots) green on the live display and headless. No commits.
