"""Registry of GUI "screens" that can be rendered offscreen for screenshots and golden snapshots.

Later phases register more entries (dialogs, the shell, catch-up, ...).

This module is imported both by pytest (as a bare top-level module, since `tests/gui` has no
`__init__.py` and pytest inserts that directory onto `sys.path`) and by `scripts/render_screens.py`
(which inserts `tests/gui` onto `sys.path` itself). Either way `render.py` next to this file must
be importable as a bare `render` module, which is why this file makes sure its own directory is on
`sys.path` before importing it.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from render import configure_for_rendering  # noqa: E402

from streaks.window import StreaksWindow  # noqa: E402

# The design fixture (tests/fixtures/seed.py) is pinned to this date; screens are always rendered
# as of this date so goldens are deterministic regardless of the caller's ambient environment.
FAKE_TODAY = "2026-09-13"

_MAX_EVENT_ITERATIONS = 10_000
_SETTLE_DELAY_MS = 50


@dataclass(frozen=True)
class Screen:
    """One renderable screen: a size and a function that builds its widget."""

    name: str
    width: int
    height: int
    build: Callable[[BuildContext], Gtk.Widget]
    seed: bool = True  # whether to seed the design fixture first (False -> empty DB)


@dataclass
class BuildContext:
    """Everything a `Screen.build` callable needs to construct its widget."""

    app: Adw.Application
    window: Adw.ApplicationWindow | None
    today: date
    settings: object | None = None


def _build_window(ctx: BuildContext) -> Gtk.Widget:
    window = StreaksWindow(application=ctx.app)
    ctx.window = window
    return window


def _build_empty(ctx: BuildContext) -> Gtk.Widget:
    window = StreaksWindow(application=ctx.app)
    ctx.window = window
    return window


def _build_sidebar(ctx: BuildContext) -> Gtk.Widget:
    window = StreaksWindow(application=ctx.app)
    ctx.window = window
    return window


def _select_today(window) -> None:
    today_row = window.sidebar_list.get_row_at_index(0)
    if today_row is not None:
        window.sidebar_list.select_row(today_row)


def _build_today(ctx: BuildContext) -> Gtk.Widget:
    window = StreaksWindow(application=ctx.app)
    ctx.window = window
    _select_today(window)
    return window


def _build_new_streak(ctx: BuildContext) -> Gtk.Widget:
    from streaks.streak_dialog import StreaksStreakDialog

    window = StreaksWindow(application=ctx.app)
    ctx.window = window
    window.present()
    _process_events()

    dialog = StreaksStreakDialog.for_new()
    dialog.set_state(window.state)

    # The design fixture's five goals (design-spec §6), replacing the default empty row.
    goal_texts = [
        "Take a progress photo",
        "45 min workout — outside",
        "45 min second workout",
        "Read 10 pages",
        "Stick to the diet",
    ]
    dialog.name_row.set_text("75 Hard")
    dialog._goal_rows[0].entry.set_text(goal_texts[0])
    for text in goal_texts[1:]:
        row = dialog._add_goal_row_widget()
        row.entry.set_text(text)

    dialog.present(window)
    _process_events()

    # Detach the content from the dialog: under a headless/no-WM display, `AdwDialog`'s floating
    # sheet never reaches GTK's "mapped" state (no window manager ever focuses the surface), so
    # anything still parented inside it snapshots as blank. Rendering the (already laid-out,
    # correctly-sized-to-560) content on its own, ordinary, `present()`-ed window sidesteps that
    # — this is exactly the "non-window widget" path `build_screen` already handles below.
    child = dialog.get_child()
    dialog.set_child(None)
    return child


def _select_streak(window, name: str) -> None:
    from streaks.sidebar_row import StreaksSidebarRow

    child = window.sidebar_list.get_first_child()
    while child is not None:
        if isinstance(child, StreaksSidebarRow) and child.name_label.get_label() == name:
            window.sidebar_list.select_row(child)
            return
        child = child.get_next_sibling()


def _build_streak(ctx: BuildContext) -> Gtk.Widget:
    window = StreaksWindow(application=ctx.app)
    ctx.window = window
    _select_streak(window, "75 Hard")
    return window


def _build_streak_lifetime(ctx: BuildContext) -> Gtk.Widget:
    # `Adw.ToggleGroup` only keeps a programmatic `set_active_name()` once it has been realized
    # (an unrealized group's active toggle reverts to the first one on its first map/layout
    # pass), so this screen must present the window before switching to "lifetime".
    window = StreaksWindow(application=ctx.app)
    ctx.window = window
    _select_streak(window, "75 Hard")
    window.present()
    _process_events()
    window.streak_view.range_toggle.set_active_name("lifetime")
    return window


def _build_today_quiet(ctx: BuildContext) -> Gtk.Widget:
    from streaks.engine import Answer
    from streaks.models import Streak, answer_day

    streak = Streak.get(Streak.name == "75 Hard")
    for day in (date(2026, 9, 9), date(2026, 9, 10), date(2026, 9, 11), date(2026, 9, 12)):
        answer_day(streak, day, Answer.KEPT)

    window = StreaksWindow(application=ctx.app)
    ctx.window = window
    _select_today(window)
    return window


SCREENS: dict[str, Screen] = {
    "window": Screen(name="window", width=1160, height=760, build=_build_window),
    "empty": Screen(name="empty", width=1160, height=760, build=_build_empty, seed=False),
    "sidebar": Screen(name="sidebar", width=1160, height=760, build=_build_sidebar),
    "today": Screen(name="today", width=1160, height=760, build=_build_today),
    "today-quiet": Screen(name="today-quiet", width=1160, height=760, build=_build_today_quiet),
    "new-streak": Screen(name="new-streak", width=560, height=900, build=_build_new_streak),
    "streak": Screen(name="streak", width=1160, height=760, build=_build_streak),
    "streak-lifetime": Screen(
        name="streak-lifetime", width=1160, height=760, build=_build_streak_lifetime
    ),
}


def _process_events(max_iterations: int = _MAX_EVENT_ITERATIONS) -> None:
    """Iterate the default GLib main context while events are pending, bounded so a stuck
    idle/timeout source can never hang a render."""
    context = GLib.MainContext.default()
    iterations = 0
    while context.pending() and iterations < max_iterations:
        context.iteration(False)
        iterations += 1


def _settle() -> None:
    """Pump the loop, then let a short timeout elapse (processed through the loop) so CSS
    transitions/layout have a chance to settle. Animations are disabled via
    `gtk-enable-animations`, so this is a small safety margin, not a wait for an animation."""
    _process_events()

    done = False

    def _mark_done() -> bool:
        nonlocal done
        done = True
        return GLib.SOURCE_REMOVE

    GLib.timeout_add(_SETTLE_DELAY_MS, _mark_done)
    context = GLib.MainContext.default()
    while not done:
        context.iteration(True)

    _process_events()


def _bind_and_seed(should_seed: bool, today: date) -> None:
    """Initialise `streaks.models.db` as a fresh in-memory database and optionally seed it with
    the design fixture. Mirrors `tests/unit/conftest.py` so every screen renders the same data."""
    from streaks.models import MODELS, db

    if not db.is_closed():
        db.close()
    db.init(":memory:", pragmas={"foreign_keys": 1})
    db.connect()
    db.create_tables(MODELS)

    if not should_seed:
        return

    tests_dir = _THIS_DIR.parent
    if str(tests_dir) not in sys.path:
        sys.path.insert(0, str(tests_dir))
    from fixtures.seed import seed

    seed(today)


def build_screen(name: str, app: Adw.Application) -> tuple[Gtk.Widget, Screen]:
    """Build, present and settle screen `name`, returning `(widget, screen)`.

    `widget` is what `render.render_widget()` should render — a window for whole-window screens,
    or a dialog's child widget for smaller screens. This is the single place that binds/seeds the
    in-memory DB, pins `STREAKS_FAKE_TODAY`, builds the widget, presents its toplevel at the
    screen's size, and pumps the main loop until it is realized, mapped and allocated.
    """
    if name not in SCREENS:
        available = ", ".join(sorted(SCREENS))
        raise ValueError(f"unknown screen {name!r} (available: {available})")
    screen = SCREENS[name]

    configure_for_rendering()

    os.environ["STREAKS_FAKE_TODAY"] = FAKE_TODAY
    today = date.fromisoformat(FAKE_TODAY)

    _bind_and_seed(screen.seed, today)

    ctx = BuildContext(app=app, window=None, today=today)
    widget = screen.build(ctx)

    if isinstance(widget, Gtk.Window):
        toplevel: Gtk.Window = widget
    else:
        toplevel = Gtk.Window(application=app)
        toplevel.set_child(widget)
        if ctx.window is None:
            ctx.window = toplevel  # type: ignore[assignment]

    toplevel.set_default_size(screen.width, screen.height)
    toplevel.present()

    _settle()

    return widget, screen
