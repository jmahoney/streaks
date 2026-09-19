# Phase 1b — offscreen rendering, screenshots and golden snapshots

Deliverables: `tests/gui/screens.py`, `scripts/render_screens.py`, `scripts/compare_png.py`,
`tests/gui/test_snapshots.py`, `tests/gui/test_render.py`, and any fixes to `scripts/screenshot.sh` /
`scripts/snapshots.sh` so they work end-to-end. Only the Phase 0 bare window exists as a screen for now; later
phases add entries to the registry.

## `tests/gui/screens.py` — screen registry
```python
@dataclass(frozen=True)
class Screen:
    name: str                      # "window", later "today", "streak", "catch-up", ...
    width: int; height: int        # design card size, e.g. 1160×760 for the window, 560×N for dialogs
    build: Callable[[BuildContext], Gtk.Widget]   # returns the widget to render (a window or a dialog's child)
    seed: bool = True              # whether to seed the design fixture first (False → empty DB)
SCREENS: dict[str, Screen]
class BuildContext: app: Adw.Application; window: Adw.ApplicationWindow | None; today: date; settings: ...
def build_screen(name, app) -> tuple[Gtk.Widget, Screen]
```
`build_screen` is the single place that (re)binds an in-memory Peewee DB (`models` may not exist yet in this phase —
import it lazily inside a `try` so the registry works before Phase 1 lands; once `streaks.models` exists, bind and
seed via `tests/fixtures/seed.py` when `screen.seed`), sets `STREAKS_FAKE_TODAY`, builds the widget, `present()`s
the toplevel window at the screen's size, and pumps the main loop until the widget is realized, mapped and has
allocated its size (`process_events()` loop with a bounded iteration count, then a `GLib.timeout` of ~50 ms
processed through the loop to let CSS/animations settle — animations are disabled via `gtk-enable-animations`).
Register `window` now: `StreaksWindow(application=app)` at 1160×760.

## `tests/gui/render.py` (helper used by both tests and the script)
`render_widget(widget: Gtk.Widget, width, height) -> Gdk.Texture`:
`paintable = Gtk.WidgetPaintable.new(widget)`; `snapshot = Gtk.Snapshot()`; `paintable.snapshot(snapshot, w, h)`;
`node = snapshot.to_node()`; `renderer = widget.get_native().get_renderer()`; `texture =
renderer.render_texture(node, Graphene.Rect().init(0, 0, w, h))`. For a whole window use the window itself as the
widget. `texture_to_png(texture, path)` via `texture.save_to_png`. `texture_pixels(texture) -> (bytes, stride,
w, h)` via `Gdk.Texture.download` (memory format B8G8R8A8 premultiplied on little-endian — document it and provide
`pixel_at(x, y) -> (r, g, b)`).
Determinism setup function `configure_for_rendering()`: `Adw.StyleManager` FORCE_LIGHT, `gtk-font-name
"Cantarell 11"`, `gtk-enable-animations False`, `gtk-cursor-blink False`, `gtk-xft-antialias 1`, `gtk-xft-hinting 1`,
`gtk-xft-hintstyle "hintslight"`, `gtk-xft-rgba "none"`; env `GSK_RENDERER=cairo`, `GDK_SCALE=1`,
`ADW_DISABLE_PORTAL=1`, `GTK_A11Y=none` must be set **before** GTK is imported (do this at the top of
`scripts/render_screens.py` and in `tests/conftest.py` — the latter already sets most; add the missing ones).
Move the existing Gtk.Settings/StyleManager setup from `tests/gui/conftest.py`'s `app` fixture into
`configure_for_rendering()` and call it from there.

## `scripts/render_screens.py`
`python3 scripts/render_screens.py --out DIR [names...]` — sets env, imports `tests/gui/screens.py` (add
`tests` to `sys.path`), creates a registered `StreaksApplication` (no `run()`), and for each screen (all by
default) builds, renders and writes `DIR/<name>.png`, printing `wrote DIR/<name>.png (WxH)`. Exit 1 with a clear
message if a name is unknown or rendering fails. Must work under `xvfb-run` and on the live Wayland display.

## `scripts/compare_png.py`
`python3 scripts/compare_png.py GOLDEN ACTUAL [--diff OUT.png] [--tolerance 8] [--max-differing 0.005]` — uses
Pillow; sizes must match (else FAIL with both sizes); a pixel differs if any channel differs by more than
`tolerance`; FAIL when the fraction of differing pixels exceeds `max-differing`; writes a diff image (differing
pixels red on a faded copy of ACTUAL) when `--diff` is given. Prints `PASS name (0.12% differing)` / `FAIL name:
3.4% of pixels differ (limit 0.5%) — diff written to …`. Exit code accordingly. Also importable:
`compare(golden_path, actual_path, tolerance, max_differing, diff_path) -> tuple[bool, float, str]`.

## `tests/gui/test_snapshots.py`
Parametrised over `SCREENS`: builds the screen, renders to `_build/snapshot-actual/<name>.png`, and compares to
`tests/snapshots/<name>.png` via `compare_png.compare`, writing diffs to `_build/snapshot-diffs/<name>.png`. If the
golden is missing the test **fails** with the message `no golden for <name> — run scripts/snapshots.sh update and
review tests/snapshots/<name>.png`. Do NOT generate a golden for `window` in this phase; `scripts/check.sh` already
skips the snapshot stage while `tests/snapshots` has no PNGs.

## `tests/gui/test_render.py`
Renders the `window` screen via the registry and asserts: texture size 1160×760; the pixel at (580, 400) is
close to the window background (light, all channels > 200); `render_screens.py` CLI writes `window.png` into a tmp
dir (run it via `subprocess` with the current env, under `xvfb-run -a` only if `STREAKS_HEADLESS=1`); and
`compare_png.compare` returns PASS for a file against itself and FAIL against a copy with a 10 % white rectangle
painted over it.

## Scripts
Make sure `scripts/screenshot.sh` and `scripts/snapshots.sh update|check` work as documented in
`docs/phases/00-scaffold.md` and print PASS/FAIL lines. Run `scripts/screenshot.sh` and view the resulting
`_build/screenshots/window.png` with the Read tool to confirm it is a real rendering (header bar + "Streaks" label).

Run `ruff format` + `ruff check --fix`; `scripts/check.sh --fast` must be fully green. Do not git commit. Do not
edit files under `src/streaks/` other than nothing — this phase is test/tooling only (if a src change is truly
required, describe it in your report instead of making it).
