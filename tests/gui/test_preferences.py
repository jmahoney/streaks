"""Tests for the Preferences dialog, the primary menu, sidebar search and window state."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import gi

gi.require_version("Gio", "2.0")

from gi.repository import Gio
from helpers import sidebar_rows

from streaks import clock, engine
from streaks.engine import Settings
from streaks.models import DayAnswer, Goal, GoalCheck, Streak
from streaks.preferences_dialog import StreaksPreferencesDialog
from streaks.window import StreaksWindow


def _open_preferences(state, window):
    dialog = StreaksPreferencesDialog(state)
    dialog.present(window)
    return dialog


# -- rows: titles, subtitles, group description, error class -------------------------------


def test_row_titles_and_subtitles(seeded_state, seeded_window, process_events):
    window = seeded_window

    dialog = _open_preferences(seeded_state, window)
    process_events()

    assert dialog.reminders_row.get_title() == "Reminders"
    assert dialog.reminders_row.get_subtitle() == "Set per streak"

    assert dialog.day_start_row.get_title() == "Day starts at"
    assert dialog.day_start_row.get_subtitle() == "Late-night check-ins count for the day before"

    assert dialog.backfill_row.get_title() == "Backfill window"
    assert dialog.backfill_row.get_subtitle() == "How far back a day can be answered for"

    assert dialog.count_through_row.get_title() == "Keep counting through unconfirmed days"
    assert dialog.count_through_row.get_subtitle() == "Runs end only on a missed goal"

    assert dialog.show_ended_row.get_title() == "Show ended runs in the sidebar"
    assert dialog.show_ended_row.get_subtitle() == "Old runs stay readable either way"

    assert dialog.export_row.get_title() == "Export everything"
    assert dialog.delete_row.get_title() == "Delete all data"
    assert "error" in dialog.delete_row.get_css_classes()


def test_data_group_description(seeded_state, seeded_window, process_events):
    window = seeded_window

    dialog = _open_preferences(seeded_state, window)
    process_events()

    parent = dialog.export_row.get_parent()
    while parent is not None and not hasattr(parent, "get_description"):
        parent = parent.get_parent()
    assert parent is not None
    assert parent.get_description() == "Data is stored locally."


# -- show ended ------------------------------------------------------------------------------


def test_show_ended_row_toggles_sidebar_section(seeded_state, seeded_window, process_events):
    window = seeded_window

    dialog = _open_preferences(seeded_state, window)
    process_events()

    assert dialog.show_ended_row.get_active()

    dialog.show_ended_row.set_active(False)
    process_events()

    assert seeded_state.settings.gio.get_boolean("show-ended") is False
    names = [r.name_label.get_label() for r in sidebar_rows(window)]
    assert "Couch to 5K" not in names

    dialog.show_ended_row.set_active(True)
    process_events()

    assert seeded_state.settings.gio.get_boolean("show-ended") is True
    names = [r.name_label.get_label() for r in sidebar_rows(window)]
    assert "Couch to 5K" in names


# -- backfill window --------------------------------------------------------------------------


def test_backfill_row_value_and_label(seeded_state, seeded_window, process_events):
    window = seeded_window

    dialog = _open_preferences(seeded_state, window)
    process_events()

    dialog.backfill_row.set_value(5)
    process_events()

    assert seeded_state.settings.gio.get_int("backfill-days") == 5
    assert dialog.backfill_label.get_label() == "5 days"

    dialog.backfill_row.set_value(1)
    process_events()

    assert seeded_state.settings.gio.get_int("backfill-days") == 1
    assert dialog.backfill_label.get_label() == "1 day"


# -- day starts at ----------------------------------------------------------------------------


def test_day_start_popover_sets_minutes_and_label(seeded_state, seeded_window, process_events):
    window = seeded_window

    dialog = _open_preferences(seeded_state, window)
    process_events()

    dialog.day_start_row.emit("activated")
    process_events()
    assert dialog.day_start_popover.heading_label.get_label() == "Day starts at"
    assert not dialog.day_start_popover.toggle_row.get_visible()

    dialog.day_start_popover.hour_spin.set_value(2)
    dialog.day_start_popover.minute_spin.set_value(30)
    process_events()

    assert seeded_state.settings.gio.get_int("day-start-minutes") == 150
    assert dialog.day_start_label.get_label() == "02:30"


def test_day_start_minutes_shifts_todays_checkin_day(monkeypatch):
    monkeypatch.setenv("STREAKS_FAKE_NOW", "2026-09-14T02:00:00")
    monkeypatch.delenv("STREAKS_FAKE_TODAY", raising=False)

    assert clock.today(150) == date(2026, 9, 13)


# -- count through unconfirmed -----------------------------------------------------------------


def test_count_through_row_changes_sidebar_run_count(seeded_state, seeded_window, process_events):
    window = seeded_window

    dialog = _open_preferences(seeded_state, window)
    process_events()

    assert dialog.count_through_row.get_active()

    dialog.count_through_row.set_active(False)
    process_events()

    assert seeded_state.settings.gio.get_boolean("count-through-unconfirmed") is False

    hard_data = next(s for s in seeded_state.streaks if s.name == "75 Hard")
    today = seeded_state.today()
    expected_settings = Settings(
        day_start_minutes=seeded_state.settings.to_engine().day_start_minutes,
        backfill_days=seeded_state.settings.to_engine().backfill_days,
        count_through_unconfirmed=False,
        show_ended=seeded_state.settings.to_engine().show_ended,
    )
    expected_run = engine.current_run(hard_data, today, expected_settings)
    expected_count = expected_run.length if expected_run else 0

    hard_row = next(r for r in sidebar_rows(window) if r.name_label.get_label() == "75 Hard")
    assert hard_row.count_label.get_label() == str(expected_count)


# -- export -------------------------------------------------------------------------------------


def test_export_row_writes_full_json_dump(seeded_state, seeded_window, process_events, tmp_path):
    window = seeded_window

    dialog = _open_preferences(seeded_state, window)
    process_events()

    out_path = tmp_path / "export.json"
    dialog._export_to(out_path)

    data = json.loads(out_path.read_text())
    assert data["version"] == 1
    assert len(data["streaks"]) == 5


def test_export_row_initial_name_uses_todays_date(
    seeded_state, seeded_window, process_events, monkeypatch
):
    window = seeded_window

    dialog = _open_preferences(seeded_state, window)
    process_events()

    captured = {}

    class _FakeFileDialog:
        def set_initial_name(self, name):
            captured["name"] = name

        def save(self, *_args, **_kwargs):
            captured["called"] = True

    monkeypatch.setattr("streaks.preferences_dialog.Gtk.FileDialog", lambda: _FakeFileDialog())

    dialog.export_row.emit("activated")
    process_events()

    assert captured["name"] == "streaks-export-2026-09-13.json"
    assert captured["called"]


# -- delete all data ------------------------------------------------------------------------------


def test_delete_all_wipes_database_and_shows_empty_state(
    seeded_state, seeded_window, process_events
):
    window = seeded_window

    dialog = _open_preferences(seeded_state, window)
    process_events()

    dialog.delete_row.emit("activated")
    process_events()
    assert dialog.delete_all_dialog is not None

    dialog.delete_all_dialog.emit("response", "delete")
    process_events()

    assert Streak.select().count() == 0
    assert Goal.select().count() == 0
    assert GoalCheck.select().count() == 0
    assert DayAnswer.select().count() == 0
    assert window.content_stack.get_visible_child_name() == "empty"


def test_delete_all_cancel_keeps_data(seeded_state, seeded_window, process_events):
    window = seeded_window

    dialog = _open_preferences(seeded_state, window)
    process_events()

    before = Streak.select().count()

    dialog.delete_row.emit("activated")
    process_events()
    dialog.delete_all_dialog.emit("response", "cancel")
    process_events()

    assert Streak.select().count() == before
    assert window.content_stack.get_visible_child_name() == "today"


# -- sidebar search --------------------------------------------------------------------------------


def test_search_filters_by_name(seeded_window, process_events):
    window = seeded_window

    window.search_button.set_active(True)
    process_events()
    assert window.search_bar.get_search_mode()

    window.search_entry.set_text("gym")
    process_events()

    visible_names = [
        r.name_label.get_label() for r in sidebar_rows(window) if r.get_child_visible()
    ]
    assert visible_names == ["Today", "Gym, three times a week"]

    hidden_names = [
        r.name_label.get_label() for r in sidebar_rows(window) if not r.get_child_visible()
    ]
    assert set(hidden_names) == {
        "75 Hard",
        "No snoozing the alarm",
        "Clip fingernails",
        "Couch to 5K",
    }

    window.search_entry.set_text("")
    process_events()

    visible_names = [
        r.name_label.get_label() for r in sidebar_rows(window) if r.get_child_visible()
    ]
    assert visible_names == [
        "Today",
        "75 Hard",
        "No snoozing the alarm",
        "Gym, three times a week",
        "Clip fingernails",
        "Couch to 5K",
    ]


def test_search_does_not_leave_orphan_section_headers(seeded_window, process_events):
    window = seeded_window

    window.search_button.set_active(True)
    process_events()
    window.search_entry.set_text("gym")
    process_events()

    visible = [r for r in sidebar_rows(window) if r.get_child_visible()]
    gym_row = next(r for r in visible if r.name_label.get_label() == "Gym, three times a week")
    # "Gym" is not the first RUNNING row in the unfiltered list, but with "75 Hard" and "No
    # snoozing the alarm" filtered out it must pick up the "RUNNING" header itself.
    header = gym_row.get_header()
    assert header is not None
    assert header.get_label() == "RUNNING"


def test_search_escape_closes_and_clears(seeded_window, process_events):
    window = seeded_window

    window.search_button.set_active(True)
    process_events()
    window.search_entry.set_text("gym")
    process_events()

    window.search_entry.emit("stop-search")
    process_events()

    assert not window.search_bar.get_search_mode()
    assert not window.search_button.get_active()
    assert window.search_entry.get_text() == ""
    assert all(r.get_child_visible() for r in sidebar_rows(window))


def test_ctrl_f_focuses_search(seeded_window, process_events):
    window = seeded_window

    window.activate_action("win.toggle-search", None)
    process_events()

    assert window.search_bar.get_search_mode()


# -- window state ----------------------------------------------------------------------------------


def test_window_state_saved_and_restored(seeded_state, app, process_events):
    # Not presented: a window manager may resize a mapped window, and the size binding is what's
    # under test.
    window = StreaksWindow(application=app, state=seeded_state)
    window.set_default_size(900, 650)
    process_events()

    assert seeded_state.settings.gio.get_int("window-width") == 900
    assert seeded_state.settings.gio.get_int("window-height") == 650

    window.close()
    process_events()
    window.destroy()

    window2 = StreaksWindow(application=app, state=seeded_state)
    assert window2.get_default_size() == (900, 650)
    window2.destroy()


# -- keyboard shortcuts window ---------------------------------------------------------------------

# Every shortcut `shortcuts.blp` lists, mapped to the action `main.py`/`window.py` registers it
# to with `set_accels_for_action`. Titles are the exact strings from
# `Gtk.ShortcutsShortcut.title` in `src/streaks/ui/shortcuts.blp`.
_SHORTCUT_TITLE_TO_ACTION = {
    "New streak": "win.new-streak",
    "Preferences": "app.preferences",
    "Search": "win.toggle-search",
    "Quit": "app.quit",
    "Keyboard shortcuts": "win.show-help-overlay",
}


def _shortcuts_blp_accelerators() -> dict[str, str]:
    """Parse (title -> accelerator) straight out of the ``.blp`` source, so this test breaks the
    moment the two drift apart, whichever side changes."""
    blp_path = Path(__file__).resolve().parents[2] / "src" / "streaks" / "ui" / "shortcuts.blp"
    content = blp_path.read_text()
    pairs = re.findall(
        r'Gtk\.ShortcutsShortcut\s*\{\s*title:\s*_\("([^"]+)"\);\s*accelerator:\s*"([^"]+)";',
        content,
    )
    assert pairs, "no Gtk.ShortcutsShortcut entries found in shortcuts.blp"
    return dict(pairs)


def test_shortcuts_blp_accelerators_match_registered_actions(app):
    """Every accelerator `shortcuts.blp` displays must be the one actually wired up via
    `app.set_accels_for_action`/`win.set_accels_for_action` — a shortcuts window that lies about
    what a key combo does is worse than no shortcuts window at all."""
    blp_accelerators = _shortcuts_blp_accelerators()
    assert set(blp_accelerators) == set(_SHORTCUT_TITLE_TO_ACTION)

    for title, accelerator in blp_accelerators.items():
        action_name = _SHORTCUT_TITLE_TO_ACTION[title]
        registered = app.get_accels_for_action(action_name)
        assert registered == [accelerator], (
            f"{title!r} ({action_name}): shortcuts.blp says {accelerator!r}, "
            f"but the app has {registered!r} registered"
        )


def test_show_help_overlay_action_is_wired_and_lists_new_streak(seeded_window, process_events):
    window = seeded_window

    # Checks wiring only: a real `Gtk.ShortcutsWindow` top-level never completes its first
    # frame under a WM-less display (see `screens._detach_dialog_content`).
    action = window.lookup_action("show-help-overlay")
    assert action is not None
    assert action.get_enabled()

    data = Gio.resources_lookup_data(
        "/com/cheerschopper/Streaks/gtk/help-overlay.ui", Gio.ResourceLookupFlags.NONE
    )
    text = bytes(data.get_data()).decode("utf-8")
    assert "New streak" in text


# -- app.preferences action ------------------------------------------------------------------------


def test_app_preferences_action_presents_dialog_over_active_window(
    app, seeded_state, process_events
):
    window = StreaksWindow(application=app, state=seeded_state)
    app.window = window
    window.present()
    process_events()

    app.activate_action("preferences", None)
    process_events()

    dialog = app.preferences_dialog
    assert isinstance(dialog, StreaksPreferencesDialog)
    assert dialog.get_visible()
    assert dialog.get_root() is window

    dialog.force_close()
    process_events()
    window.destroy()
    app.window = None


# -- rendered screen -------------------------------------------------------------------------------


def test_preferences_screen_renders_at_660_wide(seeded_window, process_events):
    window = seeded_window

    dialog = StreaksPreferencesDialog(window.state)
    dialog.present(window)
    process_events()

    assert dialog.get_content_width() == 660
    assert dialog.get_child() is not None

    dialog.force_close()
    process_events()
