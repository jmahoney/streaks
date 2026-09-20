"""Tests for the streak history content pane (design-spec §4)."""

from streaks.sidebar_row import StreaksSidebarRow
from streaks.window import StreaksWindow


def _rows(window):
    """The sidebar's actual rows, skipping the section-header labels GtkListBox interleaves
    as row siblings (see `Gtk.ListBoxRow.set_header`)."""
    rows = []
    child = window.sidebar_list.get_first_child()
    while child is not None:
        if isinstance(child, StreaksSidebarRow):
            rows.append(child)
        child = child.get_next_sibling()
    return rows


def _select_by_name(window, name, process_events):
    for row in _rows(window):
        if row.name_label.get_label() == name:
            window.sidebar_list.select_row(row)
            process_events()
            return row
    raise AssertionError(f"no sidebar row named {name!r}")


def _list_rows(listbox):
    rows = []
    row = listbox.get_row_at_index(0)
    while row is not None:
        rows.append(row)
        row = row.get_next_sibling()
    return rows


def _legend_entries(streak_view):
    """(fill/border css text, caption) pairs from the dynamically-built legend."""
    entries = []
    child = streak_view.legend_entries_box.get_first_child()
    while child is not None:
        swatch = child.get_first_child()
        caption = swatch.get_next_sibling()
        entries.append(caption.get_label())
        child = child.get_next_sibling()
    return entries


def test_75_hard_tiles(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    _select_by_name(window, "75 Hard", process_events)
    view = window.streak_view

    assert view.tile_running.value_label.get_label() == "51"
    assert view.tile_running.caption_label.get_label() == "days running"
    assert view.tile_running.value_label.has_css_class("stat-accent")

    assert view.tile_unconfirmed.value_label.get_label() == "4"
    assert view.tile_unconfirmed.caption_label.get_label() == "unconfirmed"

    assert view.tile_confirmed.value_label.get_label() == "47"
    assert view.tile_confirmed.caption_label.get_label() == "confirmed kept"

    assert view.tile_hit.value_label.get_label() == "94%"
    assert view.tile_hit.caption_label.get_label() == "goals hit"

    window.destroy()


def test_75_hard_chart(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    _select_by_name(window, "75 Hard", process_events)
    view = window.streak_view

    assert view.chart_title_label.get_label() == "Run 3 · since 25 Jul"
    assert view.best_label.get_visible()
    assert view.chart_caption_label.get_label() == (
        "Darker means more of that day's goals were done. Outlined days are ones you never "
        "answered for."
    )
    assert view.range_toggle.get_active_name() == "run"

    cells = view.heatmap._cells
    assert len(cells) % 7 == 0
    assert len(cells) == view.heatmap.columns * 7

    # The heatmap is laid out column-major (one column per week, Monday first); the run starts
    # Saturday 25 July, so the grid begins the Monday of that week.
    from datetime import date, timedelta

    run_start = date(2026, 7, 25)
    week_start = run_start - timedelta(days=run_start.weekday())

    def cell_for(day):
        return cells[(day - week_start).days]

    assert cell_for(date(2026, 9, 10)).border == "#a9c9ef"
    assert cell_for(date(2026, 9, 8)).fill == "#4b8fdb"
    assert cell_for(date(2026, 9, 7)).fill == "#1a68c7"
    assert cell_for(date(2026, 9, 13)).fill == "#4b8fdb"  # today, 3 of 5 = 0.6

    assert _legend_entries(view) == ["all five", "some", "unconfirmed", "missed"]
    assert view.catch_up_link.get_visible()
    assert view.catch_up_link.get_label() == "4 days unconfirmed — catch up"

    window.destroy()


def test_lifetime_toggle(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    _select_by_name(window, "75 Hard", process_events)
    view = window.streak_view

    view.range_toggle.set_active_name("lifetime")
    process_events()

    cells = view.heatmap._cells
    assert len(cells) == 30 * 7

    from datetime import date, timedelta

    today = date(2026, 9, 13)
    this_week_start = today - timedelta(days=today.weekday())
    grid_start = this_week_start - timedelta(days=7 * 29)
    index = (date(2026, 3, 15) - grid_start).days
    assert cells[index].fill == "#f3c0c4"

    window.destroy()


def test_goal_bars(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    _select_by_name(window, "75 Hard", process_events)
    view = window.streak_view

    rows = _list_rows(view.goal_bars_list)
    names = [r.name_label.get_label() for r in rows]
    assert names == [
        "Progress photo",
        "45 min outdoors",
        "45 min second workout",
        "Read 10 pages",
        "Stick to the diet",
    ]
    ratios = [r.ratio_label.get_text() for r in rows]
    assert ratios == ["9/9", "9/9", "6/9", "8/9", "9/9"]
    assert [r.bar.get_fraction() for r in rows] == [
        1.0,
        1.0,
        6 / 9,
        8 / 9,
        1.0,
    ]
    assert rows[2].bar.has_css_class("low")
    assert not rows[0].bar.has_css_class("low")

    window.destroy()


def test_earlier_runs_and_switching_charts(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    _select_by_name(window, "75 Hard", process_events)
    view = window.streak_view

    assert view.runs_card.get_visible()
    rows = _list_rows(view.runs_list)
    assert len(rows) == 2

    assert rows[0].title_label.get_label() == "Run 2"
    assert rows[0].meta_label.get_label() == "14 May – 16 Jun · 34 days"
    assert len(rows[0].strip._cells) == 34

    assert rows[1].title_label.get_label() == "Run 1"
    assert rows[1].meta_label.get_label() == "2 Feb – 1 Mar · 28 days"
    assert len(rows[1].strip._cells) == 28

    # Activating Run 2 switches the chart to that run.
    view.runs_list.emit("row-activated", rows[0])
    process_events()

    assert view.chart_title_label.get_label() == "Run 2 · 14 May – 16 Jun"
    assert not view.best_label.get_visible()
    assert view.range_toggle.get_active_name() == "run"
    run_toggle = view.range_toggle.get_toggle_by_name("run")
    assert run_toggle.get_label() == "Run 2"
    assert len(view.heatmap._cells) == 6 * 7

    # Toggling away and back restores "This run".
    view.range_toggle.set_active_name("lifetime")
    process_events()
    view.range_toggle.set_active_name("run")
    process_events()

    assert run_toggle.get_label() == "This run"
    assert view.chart_title_label.get_label() == "Run 3 · since 25 Jul"
    assert view.best_label.get_visible()

    window.destroy()


def test_window_header_on_streak_page(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    assert not window.checkin_button.get_visible()

    _select_by_name(window, "75 Hard", process_events)

    assert window.content_title.get_title() == "75 Hard"
    assert window.content_title.get_subtitle() == "Daily · 5 goals · run 3"
    assert window.checkin_button.get_visible()
    assert window.checkin_button.has_css_class("suggested-action")
    assert window.more_button.get_visible()
    assert not window.search_button.get_visible()

    window.checkin_button.emit("clicked")
    process_events()

    assert window.content_stack.get_visible_child_name() == "today"
    assert not window.checkin_button.get_visible()

    window.destroy()


def test_ended_streak_history(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    _select_by_name(window, "Couch to 5K", process_events)
    view = window.streak_view

    assert view.tile_running.value_label.get_label() == "31"
    assert view.tile_running.caption_label.get_label() == "days, best run"
    assert view.tile_unconfirmed.value_label.get_label() == "0"
    assert view.tile_confirmed.value_label.get_label() == "31"
    assert view.tile_hit.value_label.get_label() == "100%"

    assert view.chart_title_label.get_label() == "Run 1 · 2 Feb – 4 Mar"
    assert not view.catch_up_link.get_visible()

    assert window.content_title.get_subtitle() == "Daily · 1 goal · ended 4 Mar"

    # Phase 8 deliverable 5: an ended streak's page is read-only — no "Check in" button, and the
    # ⋯ menu offers only Delete….
    assert not window.checkin_button.get_visible()
    menu = window.more_button.get_menu_model()
    assert menu.get_n_items() == 1
    label_value = menu.get_item_attribute_value(0, "label", None)
    assert label_value.get_string() == "Delete…"

    window.destroy()


def test_end_streak_action(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    row = _select_by_name(window, "75 Hard", process_events)
    streak_id = row.streak_id

    window.activate_action("win.end-streak", _variant(streak_id))
    process_events()

    assert window.end_streak_dialog is not None
    window.end_streak_dialog.emit("response", "end")
    process_events()

    from streaks.models import Streak

    streak = Streak.get_by_id(streak_id)
    assert streak.ended_on == seeded_state.today()

    rows = _rows(window)
    ended_row = next(r for r in rows if r.streak_id == streak_id)
    assert ended_row.section == "ended"

    window.destroy()


def test_delete_streak_action(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    row = _select_by_name(window, "75 Hard", process_events)
    streak_id = row.streak_id

    window.activate_action("win.delete-streak", _variant(streak_id))
    process_events()

    assert window.delete_streak_dialog is not None
    window.delete_streak_dialog.emit("response", "delete")
    process_events()

    from streaks.models import Streak

    assert Streak.get_or_none(Streak.id == streak_id) is None
    assert window.content_stack.get_visible_child_name() == "today"
    assert all(r.streak_id != streak_id for r in _rows(window))

    window.destroy()


def _variant(streak_id):
    from gi.repository import GLib

    return GLib.Variant("i", streak_id)
