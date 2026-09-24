"""Tests for the empty-state view (design-spec §8)."""

from streaks import engine, theme
from streaks.empty_view import StreaksEmptyView


def test_empty_view_labels(app, process_events):
    view = StreaksEmptyView()
    process_events()

    assert view.title_label.get_label() == "No streaks yet"
    assert view.body_label.get_label() == "A streak is a set of goals repeated on a schedule."
    assert view.create_button.get_label() == "Create a streak"
    assert view.create_button.has_css_class("suggested-action")
    assert view.create_button.has_css_class("pill")
    assert view.create_button.get_action_name() == "win.new-streak"


def test_empty_view_grid_cells(app, process_events):
    view = StreaksEmptyView()
    process_events()

    grid = view.grid
    assert grid.cell_width == 14
    assert grid.cell_height == 14
    assert grid.gap == 5
    assert grid.radius == 4

    cells = grid._cells
    assert len(cells) == 28
    assert all(c.fill == engine.CHART_ZERO for c in cells[:-1])
    assert cells[-1].fill == theme.CHART_EMPTY_HINT
    # Light reuses the low chart step; dark gets its own warmer hint (design-spec §8).
    assert theme.LIGHT_PALETTE[theme.CHART_EMPTY_HINT] == "#cfe2f8"
    assert theme.DARK_PALETTE[theme.CHART_EMPTY_HINT] == "#7a4d18"
