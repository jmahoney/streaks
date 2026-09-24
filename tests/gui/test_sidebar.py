"""Tests for the sidebar list (design-spec §2)."""

import pytest
from helpers import sidebar_rows

from streaks.empty_view import StreaksEmptyView
from streaks.models import Streak
from streaks.window import StreaksWindow


def test_sidebar_rows_from_seed(seeded_window, process_events):
    window = seeded_window

    rows = sidebar_rows(window)
    names = [r.name_label.get_label() for r in rows]
    assert names == [
        "Today",
        "75 Hard",
        "No snoozing the alarm",
        "Gym, three times a week",
        "Clip fingernails",
        "Couch to 5K",
    ]

    today_row = rows[0]
    assert today_row.badge_label.get_label() == "2"
    assert today_row.badge_label.get_visible()
    assert not today_row.meta_label.get_visible()
    assert not today_row.count_label.get_visible()

    hard_row = rows[1]
    assert hard_row.meta_label.get_label() == "Daily · 5 goals"
    assert hard_row.count_label.get_label() == "51"
    assert hard_row.colour == "#3584e4"

    no_snoozing_row = rows[2]
    assert no_snoozing_row.meta_label.get_label() == "Mon–Fri · 1 goal"
    assert no_snoozing_row.count_label.get_label() == "12"

    gym_row = rows[3]
    assert gym_row.meta_label.get_label() == "3× a week · 2 goals"
    assert gym_row.count_label.get_label() == "9"

    clip_row = rows[4]
    assert clip_row.meta_label.get_label() == "Monthly · 1 goal"
    assert clip_row.count_label.get_label() == "4"

    ended_row = rows[5]
    assert ended_row.meta_label.get_label() == "Ended 4 Mar · best 31"
    assert not ended_row.count_label.get_visible()
    # GTK quantizes the widget opacity to 8 bits internally, so it doesn't round-trip exactly.
    assert ended_row.get_opacity() == pytest.approx(0.55, abs=0.01)

    assert window.footer_label.get_label() == "Data is stored locally."
    assert window.footer_label.get_visible()


def test_section_headers(seeded_window, process_events):
    window = seeded_window

    rows = sidebar_rows(window)

    assert rows[0].get_header() is None  # Today

    header = rows[1].get_header()  # 75 Hard, first RUNNING row
    assert header is not None
    assert header.get_label() == "RUNNING"

    for row in rows[2:5]:
        assert row.get_header() is None

    header = rows[5].get_header()  # Couch to 5K, first ENDED row
    assert header is not None
    assert header.get_label() == "ENDED"


def test_selecting_a_streak_switches_content(seeded_window, process_events):
    window = seeded_window

    rows = sidebar_rows(window)
    hard_row = rows[1]
    window.sidebar_list.select_row(hard_row)
    process_events()

    assert window.content_stack.get_visible_child_name() == "streak"
    assert window.content_title.get_title() == "75 Hard"
    assert window.content_title.get_subtitle() == "Daily · 5 goals · run 3"

    today_row = rows[0]
    window.sidebar_list.select_row(today_row)
    process_events()

    assert window.content_stack.get_visible_child_name() == "today"


def test_selection_survives_state_changed(seeded_state, seeded_window, process_events):
    window = seeded_window

    rows = sidebar_rows(window)
    hard_row = rows[1]
    hard_id = hard_row.streak_id
    window.sidebar_list.select_row(hard_row)
    process_events()

    seeded_state.reload()
    process_events()

    selected = window.sidebar_list.get_selected_row()
    assert selected is not None
    assert selected.streak_id == hard_id
    assert window.content_stack.get_visible_child_name() == "streak"


def test_selection_restored_from_gsettings(seeded_state, app, process_events):
    # `sidebar-selection` is read once, when the window is built, so it must be set first.
    hard_id = Streak.get(Streak.name == "75 Hard").id
    seeded_state.settings.sidebar_selection = hard_id

    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    assert window.content_stack.get_visible_child_name() == "streak"
    assert window.content_title.get_title() == "75 Hard"

    window.destroy()


def test_show_ended_false_hides_ended_section(seeded_state, seeded_window, process_events):
    seeded_state.settings.show_ended = False

    window = seeded_window

    rows = sidebar_rows(window)
    names = [r.name_label.get_label() for r in rows]
    assert "Couch to 5K" not in names
    assert not any(getattr(r, "section", None) == "ended" for r in rows)


def test_empty_state(fresh_window, process_events):
    window = fresh_window

    assert window.content_stack.get_visible_child_name() == "empty"
    assert window.sidebar_empty_label.get_visible()
    assert window.sidebar_empty_label.get_label() == "No streaks yet"
    assert not window.sidebar_list.get_visible()
    assert not window.footer_label.get_visible()

    empty_view = window.content_stack.get_child_by_name("empty")
    assert isinstance(empty_view, StreaksEmptyView)
    assert empty_view.create_button.has_css_class("suggested-action")
    assert empty_view.create_button.has_css_class("pill")
    assert empty_view.create_button.get_action_name() == "win.new-streak"
