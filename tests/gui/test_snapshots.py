"""Golden-image regression tests: render every registered screen and diff it against
tests/snapshots/<name>.png (light) and tests/snapshots/dark/<name>.png (dark).
"""

from __future__ import annotations

from pathlib import Path

import gi
import pytest

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402
from render import render_widget, set_colour_scheme, texture_to_png  # noqa: E402
from screens import SCREENS, build_screen  # noqa: E402

import compare_png  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_DIR = REPO_ROOT / "tests" / "snapshots"
ACTUAL_DIR = REPO_ROOT / "_build" / "snapshot-actual"
DIFF_DIR = REPO_ROOT / "_build" / "snapshot-diffs"


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("name", sorted(SCREENS))
def test_snapshot(name, scheme, app, process_events):
    dark = scheme == "dark"
    set_colour_scheme(dark=dark)
    widget, screen = build_screen(name, app)
    process_events()

    relative = Path("dark") / f"{name}.png" if dark else Path(f"{name}.png")
    try:
        actual_path = ACTUAL_DIR / relative
        actual_path.parent.mkdir(parents=True, exist_ok=True)

        texture = render_widget(widget, screen.width, screen.height)
        texture_to_png(texture, str(actual_path))

        golden_path = GOLDEN_DIR / relative
        if not golden_path.exists():
            pytest.fail(
                f"no {scheme} golden for {name} — run scripts/snapshots.sh update and review "
                f"tests/snapshots/{relative}"
            )

        diff_path = DIFF_DIR / relative
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        passed, _fraction, message = compare_png.compare(
            str(golden_path), str(actual_path), diff_path=str(diff_path)
        )

        assert passed, message
    finally:
        if isinstance(widget, Gtk.Window):
            widget.destroy()
        set_colour_scheme(dark=False)
