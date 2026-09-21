"""Pytest configuration for Streaks tests."""

import os
import sys
import tempfile
from pathlib import Path

repo_root = Path(__file__).parent.parent
for _path in (
    repo_root / "src",
    repo_root / "tests",
    repo_root / "tests" / "gui",
    repo_root / "scripts",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

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

from fixtures.seed import FIXTURE_TODAY  # noqa: E402

os.environ.setdefault("STREAKS_FAKE_TODAY", FIXTURE_TODAY.isoformat())
