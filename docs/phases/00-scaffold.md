# Phase 0 — scaffold & build tooling

Read `/home/joe/src/streaks/CLAUDE.md` and `/home/joe/src/streaks/docs/design-spec.md` §1 first. Create exactly the files
below. Do not add features; the only UI is a bare window. Everything must pass `scripts/check.sh` at the end.

App ID `com.cheerschopper.Streaks`, project name `streaks`, version `0.1.0`, Python package `streaks` under `src/`.

## Files

### `meson.build` (root)
```
project('streaks', version: '0.1.0', meson_version: '>= 1.0.0', default_options: ['warning_level=2'])
i18n = import('i18n')
gnome = import('gnome')
subdir('data')
subdir('src')
subdir('po')
subdir('tests')
gnome.post_install(glib_compile_schemas: true, gtk_update_icon_cache: true, update_desktop_database: true)
```

### `data/meson.build`
- `desktop_file` via `i18n.merge_file` from `com.cheerschopper.Streaks.desktop.in` → `com.cheerschopper.Streaks.desktop`,
  type `desktop`, po_dir `../po`, install to `datadir/applications`; `test('Validate desktop file', desktop-file-validate)`.
- `appstream_file` via `i18n.merge_file` from `com.cheerschopper.Streaks.metainfo.xml.in`, type `xml`, install to
  `datadir/metainfo`; `test('Validate appstream file', appstreamcli, args: ['validate', '--no-net', '--explain', appstream_file])`.
- `install_data('com.cheerschopper.Streaks.gschema.xml', install_dir: datadir/'glib-2.0'/'schemas')` and
  `gnome.compile_schemas(build_by_default: true, depend_files: 'com.cheerschopper.Streaks.gschema.xml')` (produces
  `_build/data/gschemas.compiled`, which tests use via `GSETTINGS_SCHEMA_DIR`).
- `test('Validate schema file', glib-compile-schemas, args: ['--strict', '--dry-run', meson.current_source_dir()])`.
- `subdir('icons')`: install `icons/hicolor/scalable/apps/com.cheerschopper.Streaks.svg` and
  `icons/hicolor/symbolic/apps/com.cheerschopper.Streaks-symbolic.svg` (simple placeholder SVGs: a 7×4 grid of rounded
  squares, one highlighted, 128×128 viewBox; symbolic version 16×16 in currentColor).

### `data/com.cheerschopper.Streaks.desktop.in`
Name=Streaks, Comment=Keep track of things you do regularly, Exec=com.cheerschopper.Streaks, Icon=com.cheerschopper.Streaks,
Terminal=false, Type=Application, Categories=GNOME;GTK;Utility;, StartupNotify=true,
DBusActivatable=true, Keywords=habit;streak;tracker;

### `data/com.cheerschopper.Streaks.metainfo.xml.in`
component type desktop-application, id, metadata_license CC0-1.0, project_license GPL-3.0-or-later, name Streaks,
summary "Keep track of things you do regularly", description one paragraph, launchable desktop-id, releases 0.1.0
dated 2026-09-19, content_rating oars-1.1, developer id com.cheerschopper name "Cheers Chopper", requires display
length ge 768, supports internet offline-only.

### `data/com.cheerschopper.Streaks.gschema.xml`
schema id `com.cheerschopper.Streaks` path `/com/cheerschopper/Streaks/` keys:
`window-width` i 1160, `window-height` i 760, `window-maximized` b false, `sidebar-selection` i 0,
`reminders` b true, `day-start-minutes` i 240 (range 0–1439), `backfill-days` i 2 (range 0–14),
`count-through-unconfirmed` b true, `show-ended` b true. Each with summary + description.

### `data/style.css`
Empty apart from a comment header listing the allowed classes from design-spec §9 (real rules come in later phases).

### `src/meson.build`
```
pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'streaks'
gnome = import('gnome')
python = import('python')

blueprints = custom_target('blueprints',
  input: files('streaks/ui/window.blp'),
  output: '.',
  command: [find_program('blueprint-compiler'), 'batch-compile', '@OUTPUT@', '@CURRENT_SOURCE_DIR@', '@INPUT@'],
)
gnome.compile_resources('streaks', 'streaks.gresource.xml',
  gresource_bundle: true, install: true, install_dir: pkgdatadir, dependencies: blueprints)

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)
configure_file(input: 'com.cheerschopper.Streaks.in', output: 'com.cheerschopper.Streaks',
  configuration: conf, install: true, install_dir: get_option('bindir'), install_mode: 'r-xr-xr-x')

streaks_sources = files('streaks/__init__.py', 'streaks/__main__.py', 'streaks/main.py', 'streaks/window.py')
install_data(streaks_sources, install_dir: moduledir)
install_data(files('../data/style.css'), install_dir: pkgdatadir)
```
Keep the blueprint `input:` list and `streaks_sources` list each on their own lines, one file per line, so
`scripts/add_ui.py` can append to them later.

### `src/streaks.gresource.xml`
prefix `/com/cheerschopper/Streaks`: `streaks/ui/window.ui` (compiled from blp) and `../data/style.css` with alias
`style.css`.

### `src/com.cheerschopper.Streaks.in`
Standard GNOME python launcher: shebang `@PYTHON@`, sets `VERSION='@VERSION@'`, `pkgdatadir='@pkgdatadir@'`,
`localedir='@localedir@'`, `sys.path.insert(1, pkgdatadir)`, `signal.signal(SIGINT, SIG_DFL)`, `locale.bindtextdomain`,
`gettext.install('streaks', localedir)`, sets `os.environ.setdefault('STREAKS_GRESOURCE', pkgdatadir/'streaks.gresource')`,
then `from streaks import main; sys.exit(main.main(VERSION))`.

### `src/streaks/__init__.py` — empty docstring.
### `src/streaks/__main__.py` — dev entry: `from streaks.main import main; raise SystemExit(main("dev"))`.
### `src/streaks/main.py`
`class StreaksApplication(Adw.Application)` with `application_id='com.cheerschopper.Streaks'`,
`flags=Gio.ApplicationFlags.DEFAULT_FLAGS`, `resource_base_path='/com/cheerschopper/Streaks'`. `do_activate` presents the
existing window or creates `StreaksWindow(application=self)`. Actions: `quit` (Ctrl+Q), `about` (Adw.AboutDialog: app
name Streaks, version, developer "Cheers Chopper", license GPL-3.0-or-later). `main(version)` calls
`load_resources()` then `app.run(sys.argv)`. `load_resources()`: path from env `STREAKS_GRESOURCE`; if it does not
exist raise `RuntimeError("gresource not found at {path} — run: meson compile -C _build")`;
`Gio.Resource.load(path)._register()`; then load `style.css` from the resource into a `Gtk.CssProvider` added for the
default display at `Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION`. Also `gettext.install('streaks')` fallback so `_` exists
when run via `python -m streaks`.
### `src/streaks/window.py`
`class StreaksWindow(Adw.ApplicationWindow)` with `__gtype_name__ = 'StreaksWindow'`, decorated
`@Gtk.Template(resource_path='/com/cheerschopper/Streaks/streaks/ui/window.ui')`. One `Gtk.Template.Child` named
`content_label`. In `__init__` after `super().__init__(**kwargs)` nothing else yet.
### `src/streaks/ui/window.blp`
```
using Gtk 4.0;
using Adw 1;

template $StreaksWindow : Adw.ApplicationWindow {
  title: _("Streaks");
  default-width: 1160;
  default-height: 760;

  content: Adw.ToolbarView {
    [top]
    Adw.HeaderBar {}

    content: Gtk.Label content_label {
      label: _("Streaks");
      styles ["title-1"]
    };
  };
}
```

### `po/meson.build` — `i18n.gettext('streaks', preset: 'glib')`. `po/LINGUAS` empty. `po/POTFILES` lists
`data/com.cheerschopper.Streaks.desktop.in`, `data/com.cheerschopper.Streaks.metainfo.xml.in`,
`data/com.cheerschopper.Streaks.gschema.xml`, `src/streaks/main.py`, `src/streaks/window.py`,
`src/streaks/ui/window.blp` (one per line).

### `tests/meson.build`
```
pytest = find_program('pytest', 'pytest-3', required: false)
if pytest.found()
  test_env = environment()
  test_env.set('STREAKS_GRESOURCE', meson.project_build_root() / 'src' / 'streaks.gresource')
  test_env.set('GSETTINGS_SCHEMA_DIR', meson.project_build_root() / 'data')
  test_env.set('GSETTINGS_BACKEND', 'memory')
  test_env.set('PYTHONPATH', meson.project_source_root() / 'src')
  test('unit', pytest, args: ['-q', meson.project_source_root() / 'tests' / 'unit'], env: test_env, timeout: 300)
  test('gui', pytest, args: ['-q', meson.project_source_root() / 'tests' / 'gui'], env: test_env, timeout: 600)
endif
```

### `tests/conftest.py`
- Inserts `<repo>/src` at the front of `sys.path`.
- Sets env defaults (only if unset): `STREAKS_GRESOURCE=<repo>/_build/src/streaks.gresource`,
  `GSETTINGS_SCHEMA_DIR=<repo>/_build/data`, `GSETTINGS_BACKEND=memory`, `STREAKS_DATA_DIR=<tmp per session>`,
  `GSK_RENDERER=cairo`, `GDK_SCALE=1`, `ADW_DISABLE_PORTAL=1`, `STREAKS_FAKE_TODAY=2026-09-13`.
- Session fixture `app` (used by `tests/gui`): calls `streaks.main.load_resources()` (fails with the RuntimeError hint if
  the gresource is missing), sets `Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)`,
  `Gtk.Settings.get_default()` props `gtk-font-name="Cantarell 11"`, `gtk-enable-animations=False`, creates
  `StreaksApplication()` and calls `app.register()` (do not `run`). Yields the app.
- Helper `process_events()` exported via a fixture of the same name: iterate `GLib.MainContext.default()` while pending.
- `tests/unit/` must be importable without GTK: put the `app` fixture in `tests/gui/conftest.py` instead, and only the
  path/env setup in the root conftest.

### `tests/unit/test_smoke.py` — `def test_python_version(): assert sys.version_info >= (3, 11)`.
### `tests/gui/test_window.py` — creates `StreaksWindow(application=app)`, `present()`, `process_events()`, asserts
`window.content_label.get_label() == "Streaks"` and `window.get_default_size() == (1160, 760)`; then `window.destroy()`.

### `pyproject.toml`
```
[tool.ruff]
line-length = 100
target-version = "py311"
src = ["src", "tests", "scripts"]
[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "W"]
[tool.ruff.lint.per-file-ignores]
"src/streaks/**" = ["E402"]   # gi.require_version before imports
[tool.pytest.ini_options]
testpaths = ["tests"]
```

### `com.cheerschopper.Streaks.json` (Flatpak manifest)
```
{
  "id": "com.cheerschopper.Streaks",
  "runtime": "org.gnome.Platform", "runtime-version": "50", "sdk": "org.gnome.Sdk",
  "command": "com.cheerschopper.Streaks",
  "finish-args": ["--share=ipc", "--socket=fallback-x11", "--socket=wayland", "--device=dri"],
  "cleanup": ["/include", "/lib/pkgconfig", "/man", "/share/doc", "/share/gtk-doc", "/share/man", "/share/pkgconfig", "*.la", "*.a"],
  "modules": [
    { "name": "blueprint-compiler", "buildsystem": "meson",
      "sources": [{"type": "git", "url": "https://gitlab.gnome.org/GNOME/blueprint-compiler.git", "tag": "v0.19.0"}] },
    { "name": "python3-peewee", "buildsystem": "simple",
      "build-commands": ["pip3 install --verbose --exact-version --no-index --find-links=\"file://${PWD}\" --prefix=${FLATPAK_DEST} \"peewee\" --no-build-isolation"],
      "sources": [{"type": "file",
        "url": "https://files.pythonhosted.org/packages/6f/60/58e7a307a24044e0e982b99042fcd5a58d0cd928d9c01829574d7553ee8d/peewee-3.18.3.tar.gz",
        "sha256": "62c3d93315b1a909360c4b43c3a573b47557a1ec7a4583a71286df2a28d4b72e"}] },
    { "name": "streaks", "buildsystem": "meson", "sources": [{"type": "dir", "path": "."}] }
  ]
}
```

### `scripts/` (bash: `set -euo pipefail`, `cd "$(dirname "$0")/.."`, `export PATH="$HOME/.local/bin:$PATH"`)

Common conventions: every stage prints `PASS <stage>` or `FAIL <stage>: <hint>`; a failing stage prints the command
output (captured to a temp file) before the FAIL line; the script exits 1 at the end if any stage failed, and prints a
summary table `stage | result`. Never require sudo.

- `scripts/check.sh [--unit|--gui|--no-snapshots|--fast]` — stages, in order:
  1. `ruff format --check src tests scripts`
  2. `ruff check src tests scripts`
  3. `blueprint` — `blueprint-compiler batch-compile <tmpdir> src $(find src -name '*.blp')`
  4. `meson` — `meson setup _build` if `_build/build.ninja` is missing, then `meson compile -C _build`
  5. `templates` — `python3 scripts/check_templates.py`
  6. `manifest` — `python3 scripts/check_manifest.py`
  7. `desktop` — `desktop-file-validate _build/data/com.cheerschopper.Streaks.desktop`
  8. `appstream` — `appstreamcli validate --no-net --explain _build/data/com.cheerschopper.Streaks.metainfo.xml`
  9. `schema` — `glib-compile-schemas --strict --dry-run data`
  10. `unit` — `pytest -q tests/unit`
  11. `gui` — `pytest -q tests/gui --ignore=tests/gui/test_snapshots.py`; wrapped in
      `xvfb-run -a -s "-screen 0 1600x1000x24 -dpi 96"` when `STREAKS_HEADLESS=1` or `$DISPLAY`/`$WAYLAND_DISPLAY` both empty.
  12. `snapshots` — `pytest -q tests/gui/test_snapshots.py` (same xvfb rule); skipped with `--no-snapshots`/`--fast`;
      also skipped (printing `SKIP snapshots: no tests/snapshots yet`) if `tests/snapshots` has no PNGs.
  `--unit` runs stages 1,2,10 only; `--gui` runs 1–9,11,12; `--fast` = everything except 12.
  Exports the same env as `tests/conftest.py` defaults (STREAKS_GRESOURCE, GSETTINGS_SCHEMA_DIR, GSETTINGS_BACKEND=memory).
- `scripts/run.sh [--seed]` — `meson compile -C _build` (setup first if needed), then
  `STREAKS_GRESOURCE=_build/src/streaks.gresource GSETTINGS_SCHEMA_DIR=_build/data STREAKS_DATA_DIR=_build/devdata
  PYTHONPATH=src python3 -m streaks`. With `--seed`: `rm -rf _build/devdata`, run `python3 tests/fixtures/seed.py`
  (skip with a warning if the file doesn't exist yet) with the same env plus `STREAKS_FAKE_TODAY=2026-09-13`, then launch
  with `STREAKS_FAKE_TODAY=2026-09-13`.
- `scripts/flatpak.sh [build|run]` — build: `flatpak-builder --user --install --force-clean _flatpak
  com.cheerschopper.Streaks.json`; run: `flatpak run com.cheerschopper.Streaks`. Default `build`.
- `scripts/screenshot.sh` — `mkdir -p _build/screenshots` then runs `python3 scripts/render_screens.py --out
  _build/screenshots "$@"` with the test env (xvfb rule as above). Prints the list of PNGs written.
- `scripts/snapshots.sh update|check` — update: `python3 scripts/render_screens.py --out tests/snapshots`; check:
  `pytest -q tests/gui/test_snapshots.py`. (`render_screens.py` itself is written in a later step, so the script may
  report `FAIL: scripts/render_screens.py missing` for now.)
- `scripts/check_templates.py` — parses every `src/streaks/**/*.blp` for `template $Name` and object ids
  (`Type name {` and `Type name :` forms), and every `src/streaks/**/*.py` for `__gtype_name__ = '...'`,
  `Gtk.Template(resource_path=...)` and `Gtk.Template.Child()` attribute names. Reports: template names without a
  matching `__gtype_name__` and vice-versa; Child names not present as ids in the class's blp; resource paths whose
  `.ui` isn't listed in `src/streaks.gresource.xml`; `.blp` files missing from `src/meson.build` blueprint input,
  `streaks.gresource.xml`, or `po/POTFILES`; `.py` files under `src/streaks` missing from `streaks_sources` or
  `po/POTFILES`. Prints each problem as `FAIL templates: <file>: <problem>` and exits 1; otherwise `PASS templates`.
- `scripts/check_manifest.py` — collects top-level imports from `src/streaks/**/*.py` (ast), ignores stdlib
  (`sys.stdlib_module_names`) and `gi`; every remaining root module must appear as `python3-<name>` (or `<name>`) in a
  module name inside `com.cheerschopper.Streaks.json`. Also asserts `runtime-version` is `"50"`. Same PASS/FAIL format.
- `scripts/add_ui.py <name>` — creates `src/streaks/ui/<name>.blp` (template `$Streaks<CamelName>` : `Adw.Bin`) and
  `src/streaks/<name>.py` (matching class with `__gtype_name__` and `@Gtk.Template`) if absent, and appends the blp to
  the blueprint `input:` list in `src/meson.build`, the `.ui` to `streaks.gresource.xml`, the `.py` to
  `streaks_sources`, and both to `po/POTFILES`, each only if not already present. Idempotent; prints what it did.

### `.github/workflows/ci.yml` — Ubuntu 26.04 runner, `sudo apt install` the same packages as
`scripts/bootstrap.sh` lists, `uv tool install ruff`, then `STREAKS_HEADLESS=1 scripts/check.sh --fast`.

### `README.md` — short: what the app is, `scripts/bootstrap.sh --install`, `scripts/check.sh`, `scripts/run.sh --seed`,
`scripts/flatpak.sh`.

## Done criteria
- `scripts/check.sh --fast` prints PASS for every stage (unit + gui included) and exits 0.
- `scripts/run.sh` opens a window titled "Streaks" (you may verify with `timeout 5 scripts/run.sh`; exit 124 = it ran).
- `ruff format` has been applied to all Python.
- Do not `git commit`.
