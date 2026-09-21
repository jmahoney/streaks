"""Tests for the Today content pane (design-spec §3)."""

from datetime import date, datetime

from gi.repository import GLib

from streaks import engine
from streaks.models import DayAnswer, GoalCheck, Streak
from streaks.window import StreaksWindow


def _engine_view(state, day=None):
    """The canonical ``engine.TodayView`` for ``state``, computed the same way the widget does."""
    today = state.today()
    settings = state.settings.to_engine()
    return engine.today_view(state.streaks, day or today, settings)


def _today_view(window):
    return window.today_view


def _card_by_name(today_view, name):
    for column in (today_view.column_left, today_view.column_right):
        child = column.get_first_child()
        while child is not None:
            if child.name_label.get_label() == name:
                return child
            child = child.get_next_sibling()
    raise AssertionError(f"no card named {name!r}")


def _goal_rows(card):
    rows = []
    row = card.goals_list.get_row_at_index(0)
    while row is not None:
        rows.append(row)
        row = row.get_next_sibling()
    return rows


def _goal_row_by_name(card, name):
    for row in _goal_rows(card):
        if row.name_label.get_label() == name:
            return row
    raise AssertionError(f"no goal row named {name!r}")


def test_header_and_another_day_button(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    today_view = _today_view(window)
    assert today_view.title_label.get_label() == "Sunday 13 September"
    assert (
        today_view.subtitle_label.get_label()
        == "Two check-ins open. Four earlier days are unconfirmed."
    )
    assert today_view.another_day_button.get_label() == "Check in for another day"

    window.destroy()


def test_quiet_days_banner(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    expected = _engine_view(seeded_state).banners
    assert len(expected) == 1

    today_view = _today_view(window)
    banner = today_view.banners_box.get_first_child()
    assert banner is not None
    assert banner.get_next_sibling() is None  # exactly one banner

    assert banner.title_label.get_label() == expected[0].title
    assert banner.body_label.get_label() == expected[0].body
    assert len(banner.strip._cells) == 24
    outlined = [c.border == engine.CHART_UNCONFIRMED_BORDER for c in banner.strip._cells]
    # 9-12 Sep are the unconfirmed (outlined) days; today (13 Sep, the last cell) is still open,
    # not unconfirmed, so it renders solid.
    assert outlined[-5:-1] == [True, True, True, True]
    assert outlined[-1] is False
    assert not any(outlined[:-5])
    assert banner.catch_up_button.get_label() == "Catch up"

    window.destroy()


def test_cards_order_and_columns(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    today_view = _today_view(window)

    def names_in(box):
        names = []
        child = box.get_first_child()
        while child is not None:
            names.append(child.name_label.get_label())
            child = child.get_next_sibling()
        return names

    assert names_in(today_view.column_left) == ["75 Hard"]
    assert names_in(today_view.column_right) == [
        "Gym, three times a week",
        "No snoozing the alarm",
        "Clip fingernails",
    ]

    window.destroy()


def test_75_hard_card(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    expected = next(c for c in _engine_view(seeded_state).cards if c.name == "75 Hard")

    today_view = _today_view(window)
    card = _card_by_name(today_view, "75 Hard")
    assert card.meta_label.get_label() == expected.meta

    rows = _goal_rows(card)
    names = [r.name_label.get_label() for r in rows]
    assert names == [
        "Progress photo",
        "45 min outdoors",
        "45 min second workout",
        "Read 10 pages",
        "Stick to the diet",
    ]
    assert [r.check.get_active() for r in rows] == [True, True, False, False, True]
    assert [r.time_label.get_label() for r in rows] == ["07:12", "07:55", "", "", "21:30"]

    assert card.footer.get_visible()
    assert card.progress.get_fraction() == 0.6
    assert card.progress_label.get_label() == "3 of 5"

    window.destroy()


def test_gym_card(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    today_view = _today_view(window)
    card = _card_by_name(today_view, "Gym, three times a week")
    rows = _goal_rows(card)
    assert len(rows) == 2
    assert not card.footer.get_visible()

    window.destroy()


def test_no_snoozing_card(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    today_view = _today_view(window)
    card = _card_by_name(today_view, "No snoozing the alarm")
    assert len(_goal_rows(card)) == 0
    assert card.body_label.get_visible()
    assert card.body_label.get_label() == "Weekdays only. Next check-in Monday 14 September."

    window.destroy()


def test_clip_fingernails_card(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    today_view = _today_view(window)
    card = _card_by_name(today_view, "Clip fingernails")
    row = _goal_row_by_name(card, "Clip them")
    assert row.time_label.get_label() == "17 days left"

    window.destroy()


def _sidebar_today_badge(window):
    row = window.sidebar_list.get_row_at_index(0)
    return row.badge_label.get_label()


def test_goal_row_keyboard_activation_toggles_check(seeded_state, app, process_events):
    """Phase 8 deliverable 2: Space/Enter on a focused goal row toggles it. `goals_list` (a plain
    `Gtk.ListBox`) is focusable by default, and `GtkListBoxRow`'s own Space/Enter keybindings
    call ``activate()``, which is exactly what this test drives directly rather than injecting
    synthetic key events (consistent with how the rest of this suite simulates interactions —
    e.g. ``.emit("clicked")``/``.emit("response", ...)``)."""
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    today_view = _today_view(window)
    card = _card_by_name(today_view, "75 Hard")
    assert card.goals_list.get_focusable()

    row = _goal_row_by_name(card, "Read 10 pages")
    assert row.get_focusable()
    assert not row.check.get_active()

    row.activate()
    process_events()

    check = GoalCheck.get_or_none(GoalCheck.goal == row.goal_id, GoalCheck.day == date(2026, 9, 13))
    assert check is not None
    card = _card_by_name(today_view, "75 Hard")
    row = _goal_row_by_name(card, "Read 10 pages")
    assert row.check.get_active()

    row.activate()
    process_events()

    assert (
        GoalCheck.get_or_none(GoalCheck.goal == row.goal_id, GoalCheck.day == date(2026, 9, 13))
        is None
    )

    window.destroy()


def test_toggle_goal_writes_check_and_updates_view(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    today_view = _today_view(window)
    card = _card_by_name(today_view, "75 Hard")
    row = _goal_row_by_name(card, "Read 10 pages")
    goal_id = row.goal_id

    row.check.set_active(True)
    process_events()

    check = GoalCheck.get_or_none(GoalCheck.goal == goal_id, GoalCheck.day == date(2026, 9, 13))
    assert check is not None
    assert check.done_at == datetime(2026, 9, 13, 21, 45)

    card = _card_by_name(today_view, "75 Hard")
    assert card.progress_label.get_label() == "4 of 5"
    assert card.meta_label.get_label() == "4 of 5 · day 51"
    row = _goal_row_by_name(card, "Read 10 pages")
    assert row.time_label.get_label() == "21:45"

    assert _sidebar_today_badge(window) == "2"

    row.check.set_active(False)
    process_events()

    assert (
        GoalCheck.get_or_none(GoalCheck.goal == goal_id, GoalCheck.day == date(2026, 9, 13)) is None
    )

    window.destroy()


def test_toggle_last_open_75_hard_goal_updates_badge(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    assert _sidebar_today_badge(window) == "2"

    today_view = _today_view(window)
    card = _card_by_name(today_view, "75 Hard")
    for name in ("45 min second workout", "Read 10 pages"):
        row = _goal_row_by_name(card, name)
        row.check.set_active(True)
        process_events()
        card = _card_by_name(today_view, "75 Hard")

    # 75 Hard is now fully checked in for today; Gym is still open.
    assert _sidebar_today_badge(window) == "1"

    window.destroy()


def test_show_day_switches_to_an_earlier_day(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    today_view = _today_view(window)
    today_view.show_day(date(2026, 9, 12))
    process_events()

    assert today_view.title_label.get_label() == "Saturday 12 September"
    assert today_view.subtitle_label.get_label() == "Checking in for an earlier day."
    assert today_view.banners_box.get_first_child() is None
    assert today_view.back_to_today_button.get_visible()

    card = _card_by_name(today_view, "75 Hard")
    row = _goal_row_by_name(card, "Read 10 pages")
    row.check.set_active(True)
    process_events()

    check = GoalCheck.get_or_none(GoalCheck.goal == row.goal_id, GoalCheck.day == date(2026, 9, 12))
    assert check is not None

    today_view.show_day(None)
    process_events()

    assert today_view.title_label.get_label() == "Sunday 13 September"
    assert not today_view.back_to_today_button.get_visible()

    window.destroy()


def test_calendar_limits_backfill_window(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    today_view = _today_view(window)

    out_of_range = GLib.DateTime.new_local(2026, 9, 10, 0, 0, 0)
    today_view.day_calendar.select_day(out_of_range)
    process_events()
    assert today_view.title_label.get_label() == "Sunday 13 September"

    in_range = GLib.DateTime.new_local(2026, 9, 11, 0, 0, 0)
    today_view.day_calendar.select_day(in_range)
    process_events()
    assert today_view.title_label.get_label() == "Friday 11 September"

    window.destroy()


def test_mark_day_missed(seeded_state, app, process_events):
    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    today_view = _today_view(window)
    card = _card_by_name(today_view, "75 Hard")
    hard_id = card.streak_id

    card.missed_button.emit("clicked")
    process_events()

    assert today_view.missed_dialog is not None
    today_view.missed_dialog.emit("response", "missed")
    process_events()

    answer = DayAnswer.get_or_none(DayAnswer.streak == hard_id, DayAnswer.day == date(2026, 9, 13))
    assert answer is not None
    assert answer.status == "missed"

    hard_row = next(
        r
        for r in _all_sidebar_rows(window)
        if getattr(r, "name_label", None) and r.name_label.get_label() == "75 Hard"
    )
    # Run 3 ended on today's missed answer, and no new due period has started yet, so there's
    # no open run to count.
    assert hard_row.count_label.get_label() == "0"

    window.destroy()


def _all_sidebar_rows(window):
    rows = []
    child = window.sidebar_list.get_first_child()
    while child is not None:
        if hasattr(child, "name_label"):
            rows.append(child)
        child = child.get_next_sibling()
    return rows


def test_no_quiet_days_variant(seeded_state, app, process_events):
    from streaks.engine import Answer
    from streaks.models import answer_day

    streak = Streak.get(Streak.name == "75 Hard")
    for day in (date(2026, 9, 9), date(2026, 9, 10), date(2026, 9, 11), date(2026, 9, 12)):
        answer_day(streak, day, Answer.KEPT)
    seeded_state.reload()

    window = StreaksWindow(application=app, state=seeded_state)
    window.present()
    process_events()

    today_view = _today_view(window)
    assert today_view.banners_box.get_first_child() is None
    assert today_view.subtitle_label.get_label() == "Two check-ins open."

    window.destroy()
