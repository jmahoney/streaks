# Hacking on Streaks

This is the developer guide. For building and running the app see the
[README](../README.md), and for getting a change merged see
[CONTRIBUTING.md](../CONTRIBUTING.md).

## Code layout

The code has three layers:

- **`engine`** (`src/streaks/engine.py`) is pure Python with no GTK and no database. It takes plain
  data and computes every status, count, string and colour token the UI shows. The rules it
  applies are written down in [engine-rules.md](engine-rules.md).
- **`models`** (`src/streaks/models.py`) is the Peewee/SQLite data layer. It loads the data the
  engine needs and performs all writes.
- **Views** are everything else in `src/streaks/`. Each view is a GTK widget bound to a Blueprint
  template in `src/streaks/ui/*.blp`. A view places what the engine produced, and reports user
  actions either as signals or as a `models` write followed by `AppState.reload()`.

Other places worth knowing:

| Path | What's there |
|---|---|
| `src/streaks/widgets/` | Custom-drawn widgets (heatmap, day strips) |
| `data/` | Desktop file, AppStream metainfo, GSettings schema, icons, `style.css` |
| `po/` | Translation template and catalogues |
| `tests/unit/` | Engine and model tests against an in-memory database (no GTK) |
| `tests/gui/` | PyGObject integration tests and the snapshot suite |
| `tests/fixtures/` | The shared sample data (`seed.py`) and database helpers |
| `docs/design-spec.md` | The UI/behaviour spec. Code comments cite it as `design-spec §N` |
| `docs/engine-rules.md` | How check-ins become period statuses, runs and counts |

## Conventions

- **UI goes in Blueprint.** Layouts live in `.blp` files, which Meson compiles into a GResource.
  Don't build widget trees in Python, and don't add raw `.ui` XML. The template name
  (`template $StreaksFoo`) must match the Python class's `__gtype_name__`.
  `scripts/add_ui.py <name>` scaffolds a new `.blp`/`.py` pair and wires it into `meson.build`,
  `streaks.gresource.xml` and `po/POTFILES`.
- **Prefer Adwaita over custom CSS.** Reach for libadwaita style classes (`title-1`, `heading`,
  `card`, `boxed-list`, `dim-label`, …) first. `data/style.css` is only for things Adwaita
  doesn't provide.
- **Every user-facing string is translatable.** Wrap strings in `_()` (or `ngettext()`) in both
  `.blp` and Python. `scripts/check_templates.py` fails the build if it finds an untranslated
  label, title, subtitle, tooltip or placeholder.
- **Database access goes through Peewee.** Use `.select()`, `.where()`, `.create()` and so on,
  never SQL built from strings. Keep database code in `models.py`, out of the views. The real
  database lives under `GLib.get_user_data_dir()`.
- **Runtime dependencies go in the Flatpak manifests.** If you add a Python dependency, add it to
  `com.cheerschopper.Streaks.json` and `com.cheerschopper.Streaks.Devel.json` as well.
  `scripts/check_manifest.py` checks this.
- **Style.** Code is type-hinted Python 3.11+, formatted with `ruff format` (line length 100)
  and linted with `ruff check`.

## Tests

- **Unit tests** (`tests/unit/`) never touch your real database. The autouse `in_memory_db`
  fixture gives each test a fresh `:memory:` SQLite database. The `today` fixture pins the date.
- **GUI tests** (`tests/gui/`) build real widgets and pump the GLib main loop instead of clicking.
  Use the fixtures in `tests/gui/conftest.py`: `app`, `fresh_state`/`seeded_state`,
  `fresh_window`/`seeded_window` and `process_events`.
- **Sample data.** `tests/fixtures/seed.py` defines five sample streaks anchored on Sunday
  13 September 2026. The unit tests, the GUI tests, the snapshots and `scripts/run.sh --seed` all
  use it.

### Headless tests

GUI and snapshot tests run under Xvfb by default (`STREAKS_HEADLESS=1`), so no test window can
appear on, or hang, your real desktop. Set `STREAKS_HEADLESS=0` only if you want to watch them
run on your own display.

Under Xvfb the scripts also force GTK onto the X11 backend (`GDK_BACKEND=x11`, with
`WAYLAND_DISPLAY` unset). This is necessary because GTK 4 prefers a Wayland socket whenever it can
see one, and would open the "headless" windows on your real desktop. `scripts/lib/headless.sh`
does this setup. Use the repo scripts rather than calling `pytest` directly on the GUI suite.

### Screenshots and snapshots

- `scripts/screenshot.sh [screen] [--dark]` renders one screen, or all of them, to
  `builddir/screenshots/` so you can take a quick look.
- `scripts/snapshots.sh check` compares the current UI against the golden images in
  `tests/snapshots/` (light) and `tests/snapshots/dark/`.
- `scripts/snapshots.sh update` re-renders the goldens in both styles. Run it only after a
  deliberate visual change that you have reviewed.

`docs/screenshots/` holds separate, curated copies used by the README and the AppStream
metainfo, which means the store listing is what people see before installing. They don't change
when the goldens do. Copy new images over deliberately when a change deserves new store
screenshots.

## Translations

Regenerate the template after adding or changing translatable strings:

```bash
meson compile -C builddir streaks-pot
```

## Distribution

```bash
scripts/flatpak.sh build   # flatpak-builder --user --install --force-clean
scripts/flatpak.sh run     # flatpak run com.cheerschopper.Streaks
scripts/flatpak.sh test    # headless: the bundle imports and the window actually opens
```

`scripts/flatpak.sh test` never touches a live display either. It runs under Xvfb with the
sandbox's Wayland access overridden off (`--nosocket=wayland`), and the app quits itself
(`STREAKS_QUIT_AFTER_STARTUP=1`) as soon as the window is realised.

### GNOME Builder

Open the project in Builder and choose the **com.cheerschopper.Streaks.Devel.json**
configuration. That manifest is the release one plus `-Dprofile=development`, which gives the
app the ID `com.cheerschopper.Streaks.Devel`. It runs alongside the installed app, with its own
database, settings and D-Bus name, and a striped header bar so the two are easy to tell apart.
`scripts/check_manifest.py` fails if the two manifests differ in anything else, so change
modules in both.

As a backstop, a build of the *release* manifest run from Builder (or `flatpak-builder --run`)
still keeps its data in a separate `streaks-devel/` directory. The app spots this from
`build=true` in `/.flatpak-info`, so even that never opens your real database.

Builder keeps its build directory at `_build/` in the source tree, and the host scripts use
`builddir/`. Don't point host `meson` at `_build/`. Builder only runs `meson setup` when
`_build/build.ninja` is missing, so it would reuse a host configuration with `/usr/local` as the
prefix and a different Meson version, and then fail to install into the read-only sandbox.
