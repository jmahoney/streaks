"""Tests for the offscreen-rendering helpers themselves (render.py, compare_png.py, and the
render_screens.py CLI) — not for any particular screen's pixels (see test_snapshots.py)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402
from PIL import Image  # noqa: E402
from render import pixel_at, render_widget, texture_pixels  # noqa: E402
from screens import build_screen  # noqa: E402

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import compare_png  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_window_screen_renders_at_expected_size_and_colour(app, process_events):
    widget, screen = build_screen("window", app)
    process_events()

    try:
        texture = render_widget(widget, screen.width, screen.height)

        assert texture.get_width() == 1160
        assert texture.get_height() == 760

        pixels, stride, _width, _height = texture_pixels(texture)
        # (580, 400) is the window's exact centre, which is where the centred "Streaks" title-1
        # label glyphs are — sampling there hits dark text pixels, not the background. (100, 100)
        # is comfortably inside the plain content background (confirmed uniformly (250, 250, 250)
        # away from the label) while still exercising the same thing: a light window background.
        r, g, b = pixel_at(pixels, stride, 100, 100)
        assert r > 200 and g > 200 and b > 200
    finally:
        if isinstance(widget, Gtk.Window):
            widget.destroy()


def test_render_screens_cli_writes_png(tmp_path):
    script = REPO_ROOT / "scripts" / "render_screens.py"

    cmd = [sys.executable, str(script), "--out", str(tmp_path), "window"]
    if os.environ.get("STREAKS_HEADLESS") == "1":
        cmd = ["xvfb-run", "-a", "-s", "-screen 0 1600x1000x24 -dpi 96", *cmd]

    env = os.environ.copy()
    # The `app` fixture used elsewhere in this session registers com.cheerschopper.Streaks as the
    # primary instance on the real session bus and never pumps its main loop afterwards, so a
    # child process registering the same (unique, by default) application ID on that same bus can
    # stall waiting for a D-Bus reply that never comes. Point the child at a bus address that
    # can't be connected to: GApplication.register() degrades gracefully to a local-only
    # (non-D-Bus) registration in that case, which is exactly what an isolated render process
    # wants anyway (it must never accidentally activate/attach to another running instance).
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={tmp_path / 'no-such-bus'}"

    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    out_png = tmp_path / "window.png"
    assert out_png.exists()
    with Image.open(out_png) as img:
        assert img.size == (1160, 760)


def test_compare_png_passes_against_itself(tmp_path):
    path = tmp_path / "a.png"
    Image.new("RGB", (100, 80), (240, 240, 240)).save(path)

    passed, fraction, message = compare_png.compare(str(path), str(path))

    assert passed, message
    assert fraction == 0.0


def test_compare_png_fails_with_painted_rectangle(tmp_path):
    golden_path = tmp_path / "golden.png"
    actual_path = tmp_path / "actual.png"
    diff_path = tmp_path / "diff.png"

    base = Image.new("RGB", (100, 80), (40, 40, 40))
    base.save(golden_path)

    # Paint a white rectangle covering 10% of the image (100 x 8 of 100 x 80).
    modified = base.copy()
    white_rect = Image.new("RGB", (100, 8), (255, 255, 255))
    modified.paste(white_rect, (0, 0))
    modified.save(actual_path)

    passed, fraction, message = compare_png.compare(
        str(golden_path), str(actual_path), diff_path=str(diff_path)
    )

    assert not passed, message
    assert fraction >= 0.09
    assert diff_path.exists()
