"""Tests for the main window shell (design-spec §1, §2)."""


def test_window_defaults(fresh_window, process_events):
    """Split view geometry, page titles/tags, and the content stack's pages."""
    window = fresh_window

    assert window.get_default_size() == (1160, 760)
    assert window.split_view.get_min_sidebar_width() == 280
    assert window.split_view.get_max_sidebar_width() == 280
    assert window.split_view.get_sidebar().get_title() == "Streaks"

    for name in ("empty", "today", "streak"):
        assert window.content_stack.get_child_by_name(name) is not None


def test_content_title_shows_today_at_start(seeded_window, process_events):
    """Today is selected by default; the header title/subtitle come from the engine."""
    window = seeded_window

    assert window.content_title.get_title() == "Today"
    assert window.content_title.get_subtitle() == "Sunday 13 September"
    assert window.content_stack.get_visible_child_name() == "today"


def test_empty_database_shows_empty_content_page(fresh_window, process_events):
    """With no streaks, the content stack shows the empty page."""
    window = fresh_window

    assert window.content_stack.get_visible_child_name() == "empty"
    # Design §1: the empty page has the primary menu only, titled "Streaks".
    assert not window.search_button.get_visible()
    assert window.menu_button.get_visible()
    assert window.content_title.get_title() == "Streaks"
