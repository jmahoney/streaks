"""Tests for `streaks.main` — application startup and the corrupt/unwritable-database path.

These build a throwaway `StreaksApplication` rather than using the shared, session-scoped `app`
fixture: `do_activate()` mutates `self.window`, and the error path deliberately never builds one,
which would be confusing to assert on an instance the rest of the suite also shares.
"""

from __future__ import annotations

import gi

gi.require_version("Gio", "2.0")

from gi.repository import Gio

from streaks import models
from streaks.main import StreaksApplication


def test_show_database_error_presents_dialog_with_path_and_reason(process_events):
    app = StreaksApplication(flags=Gio.ApplicationFlags.NON_UNIQUE)
    exc = models.DatabaseInitError("/fake/data/streaks.db", "disk is full")

    app._show_database_error(exc)
    process_events()

    assert "/fake/data/streaks.db" in app._db_error_dialog.get_body()
    assert "disk is full" in app._db_error_dialog.get_body()

    quit_calls = []
    app.quit = lambda: quit_calls.append(True)  # noqa: E731 - overriding a bound method for the test
    app._db_error_dialog.emit("response", "quit")
    process_events()

    assert quit_calls == [True]


def test_do_activate_shows_database_error_and_never_builds_a_window(monkeypatch, process_events):
    def fake_init_db():
        raise models.DatabaseInitError("/fake/data/streaks.db", "permission denied")

    monkeypatch.setattr(models, "init_db", fake_init_db)
    monkeypatch.setattr(models.db, "database", None)

    app = StreaksApplication(flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.do_activate()
    process_events()

    assert app.window is None
    assert app._db_error_dialog is not None
    assert "/fake/data/streaks.db" in app._db_error_dialog.get_body()
