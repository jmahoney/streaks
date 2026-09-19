"""Golden-image regression tests: render every registered screen and diff it against
tests/snapshots/<name>.png.

Not generating a golden here for `window` is intentional (see docs/phases/01b-snapshot-infra.md) —
`scripts/check.sh` skips this whole stage while `tests/snapshots/` has no PNGs in it yet. Once a
golden exists (`scripts/snapshots.sh update`, after reviewing the PNG), this test enforces it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import gi
import pytest

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402
from render import render_widget, texture_to_png  # noqa: E402
from screens import SCREENS, build_screen  # noqa: E402

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import compare_png  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_DIR = REPO_ROOT / "tests" / "snapshots"
ACTUAL_DIR = REPO_ROOT / "_build" / "snapshot-actual"
DIFF_DIR = REPO_ROOT / "_build" / "snapshot-diffs"


@pytest.mark.parametrize("name", sorted(SCREENS))
def test_snapshot(name, app, process_events):
    widget, screen = build_screen(name, app)
    process_events()

    try:
        ACTUAL_DIR.mkdir(parents=True, exist_ok=True)

        texture = render_widget(widget, screen.width, screen.height)
        actual_path = ACTUAL_DIR / f"{name}.png"
        texture_to_png(texture, str(actual_path))

        golden_path = GOLDEN_DIR / f"{name}.png"
        if not golden_path.exists():
            pytest.fail(
                f"no golden for {name} — run scripts/snapshots.sh update and review "
                f"tests/snapshots/{name}.png"
            )

        diff_path = DIFF_DIR / f"{name}.png"
        passed, _fraction, message = compare_png.compare(
            str(golden_path), str(actual_path), diff_path=str(diff_path)
        )

        assert passed, message
    finally:
        if isinstance(widget, Gtk.Window):
            widget.destroy()
