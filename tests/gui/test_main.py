"""Tests for `streaks.main` — application startup and the corrupt/unwritable-database path.

These build a throwaway `StreaksApplication`: `do_activate()` mutates `self.window`, and
asserting on the session-scoped `app` would leave it in whatever state the last test put it in.
"""

from __future__ import annotations

import gi

gi.require_version("Gio", "2.0")

from gi.repository import Gio

from streaks import models
from streaks.main import StreaksApplication


def test_do_activate_shows_database_error_with_path_and_reason(monkeypatch, process_events):
    def fake_init_db():
        raise models.DatabaseInitError("/fake/data/streaks.db", "disk is full")

    monkeypatch.setattr(models, "init_db", fake_init_db)
    monkeypatch.setattr(models.db, "database", None)

    app = StreaksApplication(flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.do_activate()
    process_events()

    assert "/fake/data/streaks.db" in app.database_error_dialog.get_body()
    assert "disk is full" in app.database_error_dialog.get_body()

    quit_calls = []
    app.quit = lambda: quit_calls.append(True)  # noqa: E731 - overriding a bound method for the test
    app.database_error_dialog.emit("response", "quit")
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
    assert app.database_error_dialog is not None
    assert "/fake/data/streaks.db" in app.database_error_dialog.get_body()


def test_development_profile_marks_the_window_devel(app, process_events):
    """A development build (GNOME Builder, `-Dprofile=development`) gets GNOME's striped
    `devel` header bar so it can't be mistaken for the installed app. (The session `app`
    fixture is only requested so libadwaita is initialised.)"""
    streaks_app = StreaksApplication(flags=Gio.ApplicationFlags.NON_UNIQUE, profile="development")
    streaks_app.do_activate()
    process_events()

    assert streaks_app.window.has_css_class("devel")
    streaks_app.window.destroy()


def test_default_profile_leaves_the_window_unmarked(app, process_events):
    streaks_app = StreaksApplication(flags=Gio.ApplicationFlags.NON_UNIQUE)
    streaks_app.do_activate()
    process_events()

    assert not streaks_app.window.has_css_class("devel")
    streaks_app.window.destroy()
