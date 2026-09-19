"""Tests for the main window."""

from streaks.window import StreaksWindow


def test_window_initialization(app, process_events):
    """Test window initializes with correct content."""
    window = StreaksWindow(application=app)
    window.present()
    process_events()

    assert window.content_label.get_label() == "Streaks"
    assert window.get_default_size() == (1160, 760)

    window.destroy()
