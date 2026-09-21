"""Pytest configuration for Streaks tests."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

repo_src = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(repo_src))

repo_root = Path(__file__).parent.parent
os.environ.setdefault("STREAKS_GRESOURCE", str(repo_root / "_build" / "src" / "streaks.gresource"))
os.environ.setdefault("GSETTINGS_SCHEMA_DIR", str(repo_root / "_build" / "data"))
os.environ.setdefault("GSETTINGS_BACKEND", "memory")

if "STREAKS_DATA_DIR" not in os.environ:
    tmp_dir = tempfile.mkdtemp(prefix="streaks-test-")
    os.environ["STREAKS_DATA_DIR"] = tmp_dir

os.environ.setdefault("GSK_RENDERER", "cairo")
os.environ.setdefault("GDK_SCALE", "1")
os.environ.setdefault("ADW_DISABLE_PORTAL", "1")
os.environ.setdefault("GTK_A11Y", "none")
os.environ.setdefault("STREAKS_FAKE_TODAY", "2026-09-13")


def process_events():
    """Iterate GLib main context while pending."""
    import gi

    gi.require_version("GLib", "2.0")
    from gi.repository import GLib

    context = GLib.MainContext.default()
    while context.pending():
        context.iteration(False)


@pytest.fixture
def process_events_fixture():
    """Fixture for event processing."""
    return process_events
