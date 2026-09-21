#!/usr/bin/env python3
"""Render registered GUI screens to PNG files, headless-safe.

    python3 scripts/render_screens.py --out DIR [names...]

Renders every screen registered in tests/gui/screens.py:SCREENS by default, or only the ones
named on the command line, writing `DIR/<name>.png` for each. Must work both under `xvfb-run`
(`STREAKS_HEADLESS=1`) and on a live Wayland/X11 display.
"""

from __future__ import annotations

# These must be set before Gtk/Adw/Gdk are imported anywhere at all — including transitively, via
# the `screens`/`render` imports below or the `streaks` package — so this block stays first.
import os

os.environ.setdefault("GSK_RENDERER", "cairo")
os.environ.setdefault("GDK_SCALE", "1")
os.environ.setdefault("ADW_DISABLE_PORTAL", "1")
os.environ.setdefault("GTK_A11Y", "none")

import argparse  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

os.environ.setdefault("STREAKS_GRESOURCE", str(REPO_ROOT / "_build" / "src" / "streaks.gresource"))
os.environ.setdefault("GSETTINGS_SCHEMA_DIR", str(REPO_ROOT / "_build" / "data"))
os.environ.setdefault("GSETTINGS_BACKEND", "memory")

sys.path[0:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "tests"), str(REPO_ROOT / "tests" / "gui")]

from fixtures.seed import FIXTURE_TODAY  # noqa: E402

os.environ.setdefault("STREAKS_FAKE_TODAY", FIXTURE_TODAY.isoformat())

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from streaks.resources import load_resources  # noqa: E402

# Widget templates validate their resource path at class-definition time, so the gresource bundle
# must be registered before anything imports a view class — including `screens`, which imports
# StreaksWindow at module scope.
load_resources()

from render import (  # noqa: E402
    configure_for_rendering,
    make_test_application,
    render_widget,
    set_colour_scheme,
    texture_to_png,
)
from screens import SCREENS, build_screen  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="output directory for PNGs")
    parser.add_argument("names", nargs="*", help="screen names to render (default: all)")
    parser.add_argument("--dark", action="store_true", help="render in the dark colour scheme")
    args = parser.parse_args(argv)

    names = args.names or sorted(SCREENS)
    unknown = [n for n in names if n not in SCREENS]
    if unknown:
        available = ", ".join(sorted(SCREENS))
        print(
            f"error: unknown screen(s): {', '.join(unknown)} (available: {available})",
            file=sys.stderr,
        )
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    app = make_test_application()

    from gi.repository import Gtk

    configure_for_rendering()
    set_colour_scheme(dark=args.dark)

    for name in names:
        widget = None
        try:
            widget, screen = build_screen(name, app)
            texture = render_widget(widget, screen.width, screen.height)
            out_path = out_dir / f"{name}.png"
            texture_to_png(texture, str(out_path))
            print(f"wrote {out_path} ({screen.width}x{screen.height})")
        except Exception as exc:  # noqa: BLE001 - want a clear message for any screen failure
            print(f"error: failed to render screen {name!r}: {exc}", file=sys.stderr)
            return 1
        finally:
            if isinstance(widget, Gtk.Window):
                widget.destroy()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
