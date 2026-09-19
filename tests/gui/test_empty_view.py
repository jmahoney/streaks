"""Tests for the empty-state view (design-spec §8)."""

from streaks.empty_view import StreaksEmptyView


def test_empty_view_labels(app, process_events):
    view = StreaksEmptyView()
    process_events()

    assert view.title_label.get_label() == "No streaks yet"
    assert view.body_label.get_label() == (
        "Pick something you want to do regularly, choose how often, and add as "
        "many goals as that thing needs."
    )
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
    assert all(c.fill == "#e9e9e7" for c in cells[:-1])
    assert cells[-1].fill == "#cfe2f8"
