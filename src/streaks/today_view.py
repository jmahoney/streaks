"""The Today content pane: header, quiet-day banners, and per-streak check-in cards
(design-spec §3).

No engine/database logic lives here beyond the two writes a check-in view has to make (toggling
a ``GoalCheck``, recording a ``DayAnswer``) — every string and number displayed comes straight
from ``engine.today_view``/``engine.mark_missed_preview``.
"""

from __future__ import annotations

import gettext
import logging
from datetime import date, datetime, timedelta

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

from streaks import clock, engine, words
from streaks.catchup_banner import (
    StreaksCatchupBanner,  # noqa: F401  registers $StreaksCatchupBanner
)
from streaks.checkin_card import StreaksCheckinCard  # noqa: F401  registers $StreaksCheckinCard
from streaks.engine import Answer, Banner, Card
from streaks.models import Goal, Streak, answer_day, toggle_goal_check
from streaks.state import AppState

_ = gettext.gettext
ngettext = gettext.ngettext
_logger = logging.getLogger(__name__)


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/today_view.ui")
class StreaksTodayView(Adw.Bin):
    """The Today content pane (design-spec §3). Call ``set_state()`` before it renders anything."""

    __gtype_name__ = "StreaksTodayView"

    scrolled = Gtk.Template.Child()
    title_label = Gtk.Template.Child()
    subtitle_label = Gtk.Template.Child()
    another_day_button = Gtk.Template.Child()
    back_to_today_button = Gtk.Template.Child()
    calendar_popover = Gtk.Template.Child()
    day_calendar = Gtk.Template.Child()
    calendar_hint_label = Gtk.Template.Child()
    banners_box = Gtk.Template.Child()
    columns_box = Gtk.Template.Child()
    column_left = Gtk.Template.Child()
    column_right = Gtk.Template.Child()

    def __init__(self, **kwargs):
        """Initialize the view. It renders nothing until ``set_state()`` is called."""
        super().__init__(**kwargs)
        self.state: AppState | None = None
        self._shown_day: date | None = None
        self.missed_dialog: Adw.AlertDialog | None = None

        self.back_to_today_button.connect("clicked", lambda _b: self.show_day(None))

    # -- wiring -----------------------------------------------------------------

    def set_state(self, state: AppState) -> None:
        """Bind to ``state``, pin the calendar to "today", and rebuild on every change."""
        self.state = state
        today = state.today()
        gdate = GLib.DateTime.new_local(today.year, today.month, today.day, 0, 0, 0)
        self.day_calendar.select_day(gdate)
        self.day_calendar.connect("day-selected", self._on_day_selected)
        state.connect("changed", self._on_state_changed)
        self._rebuild()

    def _on_state_changed(self, _state: AppState) -> None:
        self._rebuild()

    def show_day(self, day: date | None) -> None:
        """Show ``day`` (``None`` = today) in the content pane."""
        self._shown_day = day
        self._rebuild()

    def scroll_to_streak(self, streak_id: int) -> None:
        """Focus the check-in card for ``streak_id``, if it is currently shown.

        GTK scrolls a `Gtk.ScrolledWindow` to keep a newly-focused descendant in view, so
        grabbing focus on the card is enough to bring it on screen — no manual adjustment math
        needed.
        """
        for column in (self.column_left, self.column_right):
            child = column.get_first_child()
            while child is not None:
                if getattr(child, "streak_id", None) == streak_id:
                    child.grab_focus()
                    return
                child = child.get_next_sibling()

    # -- rebuilding ---------------------------------------------------------------

    @staticmethod
    def _clear_box(box: Gtk.Box) -> None:
        child = box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            box.remove(child)
            child = nxt

    def _rebuild(self) -> None:
        if self.state is None:
            return

        today = self.state.today()
        settings = self.state.settings.to_engine()
        self.calendar_hint_label.set_label(
            ngettext(
                "Only the last %(n)d day can be answered",
                "Only the last %(n)d days can be answered",
                settings.backfill_days,
            )
            % {"n": settings.backfill_days}
        )

        display_day = self._shown_day or today
        view = engine.today_view(self.state.streaks, display_day, clock.now(), settings)

        viewing_past = self._shown_day is not None
        self.back_to_today_button.set_visible(viewing_past)
        if viewing_past:
            self.title_label.set_label(words.fmt_weekday_day(display_day))
            self.subtitle_label.set_label(_("Checking in for an earlier day."))
            self._clear_box(self.banners_box)
        else:
            self.title_label.set_label(view.title)
            self.subtitle_label.set_label(view.subtitle)
            self._rebuild_banners(view.banners)

        self._rebuild_cards(view.cards)

    def _rebuild_banners(self, banners: list[Banner]) -> None:
        self._clear_box(self.banners_box)
        for banner in banners:
            widget = StreaksCatchupBanner()
            widget.configure(banner)
            widget.connect("catch-up", self._on_catch_up)
            self.banners_box.append(widget)

    def _rebuild_cards(self, cards: list[Card]) -> None:
        self._clear_box(self.column_left)
        self._clear_box(self.column_right)
        left_rows = 0
        right_rows = 0
        for card in cards:
            widget = StreaksCheckinCard()
            widget.configure(card)
            widget.connect("goal-toggled", self._on_goal_toggled)
            widget.connect("mark-missed", self._on_mark_missed)
            if left_rows <= right_rows:
                self.column_left.append(widget)
                left_rows += len(card.goals)
            else:
                self.column_right.append(widget)
                right_rows += len(card.goals)

    # -- interactions ---------------------------------------------------------------

    def _on_catch_up(self, _banner: StreaksCatchupBanner, streak_id: int) -> None:
        _logger.info("catch-up requested for streak %s (not yet implemented)", streak_id)

    def _on_goal_toggled(self, _card: StreaksCheckinCard, goal_id: int) -> None:
        if self.state is None:
            return
        goal = Goal.get_by_id(goal_id)
        display_day = self._shown_day or self.state.today()
        done_at = datetime.combine(display_day, clock.now().time())
        toggle_goal_check(goal, display_day, done_at)
        self.state.reload()

    def _on_mark_missed(self, _card: StreaksCheckinCard, streak_id: int) -> None:
        if self.state is None:
            return
        streak_data = next((s for s in self.state.streaks if s.id == streak_id), None)
        if streak_data is None:
            return
        today = self.state.today()
        settings = self.state.settings.to_engine()
        body = engine.mark_missed_preview(streak_data, today, settings)

        dialog = Adw.AlertDialog(heading=_("Mark today as missed?"), body=body)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("missed", _("Mark missed"))
        dialog.set_response_appearance("missed", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_mark_missed_response, streak_id)
        self.missed_dialog = dialog
        dialog.present(self)

    def _on_mark_missed_response(
        self, _dialog: Adw.AlertDialog, response: str, streak_id: int
    ) -> None:
        if response != "missed" or self.state is None:
            return
        streak = Streak.get_by_id(streak_id)
        answer_day(streak, self.state.today(), Answer.MISSED)
        self.state.reload()

    def _on_day_selected(self, calendar: Gtk.Calendar) -> None:
        if self.state is None:
            return
        gdate = calendar.get_date()
        day = date(gdate.get_year(), gdate.get_month(), gdate.get_day_of_month())
        today = self.state.today()
        settings = self.state.settings.to_engine()
        earliest = today - timedelta(days=settings.backfill_days)
        if day < earliest or day > today:
            return
        self.calendar_popover.popdown()
        self.show_day(day)
