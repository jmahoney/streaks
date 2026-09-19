"""Main window: the sidebar/content shell (design-spec §1, §2)."""

from __future__ import annotations

import gettext
import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, Gtk

from streaks import clock, engine
from streaks.empty_view import StreaksEmptyView  # noqa: F401  registers $StreaksEmptyView
from streaks.sidebar_row import StreaksSidebarRow
from streaks.state import AppState
from streaks.today_view import StreaksTodayView  # noqa: F401  registers $StreaksTodayView

_ = gettext.gettext
_logger = logging.getLogger(__name__)


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/window.ui")
class StreaksWindow(Adw.ApplicationWindow):
    """Main application window: a navigation split view with a sidebar and content stack."""

    __gtype_name__ = "StreaksWindow"

    split_view = Gtk.Template.Child()
    sidebar_list = Gtk.Template.Child()
    sidebar_empty_label = Gtk.Template.Child()
    footer_label = Gtk.Template.Child()
    content_stack = Gtk.Template.Child()
    content_title = Gtk.Template.Child()
    today_view = Gtk.Template.Child()
    streak_status_page = Gtk.Template.Child()
    search_button = Gtk.Template.Child()
    menu_button = Gtk.Template.Child()
    new_button = Gtk.Template.Child()

    def __init__(self, state: AppState | None = None, **kwargs):
        """Initialize the window: build the sidebar from `state` (a fresh one if not given)."""
        super().__init__(**kwargs)
        self.state = state or AppState()
        self.state.settings.bind_window_state(self)
        self.state.connect("changed", self._on_state_changed)
        self.state.settings.connect("changed", self._on_settings_changed)

        self._today_view: engine.TodayView | None = None

        self._install_actions()
        self.sidebar_list.set_header_func(self._header_func)
        self.sidebar_list.connect("row-selected", self._on_row_selected)

        self.today_view.set_state(self.state)
        self._rebuild_sidebar()

    # -- window actions -----------------------------------------------------------

    def _install_actions(self) -> None:
        new_streak = Gio.SimpleAction.new("new-streak", None)
        new_streak.connect("activate", self._on_new_streak)
        self.add_action(new_streak)

        select_today = Gio.SimpleAction.new("select-today", None)
        select_today.connect("activate", self._on_select_today)
        self.add_action(select_today)

        # Present-but-no-op for now; a later phase wires up the shortcuts window.
        show_help_overlay = Gio.SimpleAction.new("show-help-overlay", None)
        show_help_overlay.connect("activate", lambda *_args: None)
        self.add_action(show_help_overlay)

    def _on_new_streak(self, *_args) -> None:
        # Phase 4 wires this up to the new-streak dialog; for now it's a logged no-op.
        _logger.info("win.new-streak activated (not yet implemented)")

    def _on_select_today(self, *_args) -> None:
        today_row = self.sidebar_list.get_row_at_index(0)
        if today_row is not None:
            self.sidebar_list.select_row(today_row)

    # -- sidebar building -----------------------------------------------------------

    def _header_func(self, row: Gtk.ListBoxRow, before: Gtk.ListBoxRow | None) -> None:
        section = getattr(row, "section", None)
        prev_section = getattr(before, "section", None) if before is not None else None
        if section is None or section == prev_section:
            row.set_header(None)
            return
        label = Gtk.Label(label=_("RUNNING") if section == "running" else _("ENDED"))
        label.add_css_class("caption-heading")
        label.add_css_class("dim-label")
        label.set_halign(Gtk.Align.START)
        label.set_margin_top(14)
        label.set_margin_bottom(6)
        label.set_margin_start(10)
        row.set_header(label)

    def _clear_sidebar(self) -> None:
        # `remove_all()` also cleans up the per-row header widgets GtkListBox manages as row
        # siblings (see `_header_func`) — a manual child-by-child removal loop fights that and
        # warns about removing widgets already gone.
        self.sidebar_list.remove_all()

    def _rebuild_sidebar(self) -> None:
        previous_selection = self.state.selection
        self._clear_sidebar()

        streaks = self.state.streaks
        if not streaks:
            self.sidebar_list.set_visible(False)
            self.footer_label.set_visible(False)
            self.sidebar_empty_label.set_visible(True)
            self.search_button.set_visible(False)
            self.content_title.set_title(_("Streaks"))
            self.content_title.set_subtitle("")
            self.content_stack.set_visible_child_name("empty")
            return

        self.sidebar_list.set_visible(True)
        self.footer_label.set_visible(True)
        self.sidebar_empty_label.set_visible(False)
        self.search_button.set_visible(True)

        today = self.state.today()
        now = clock.now()
        settings = self.state.settings.to_engine()
        self._today_view = engine.today_view(streaks, today, now, settings)

        today_row = StreaksSidebarRow()
        today_row.section = None
        today_row.configure_today(self._today_view.open_count)
        self.sidebar_list.append(today_row)

        running = [s for s in streaks if s.ended_on is None]
        ended = [s for s in streaks if s.ended_on is not None]

        for streak in running:
            row = StreaksSidebarRow()
            row.section = "running"
            meta = engine.sidebar_meta(streak)
            count = engine.sidebar_count(streak, today, settings)
            row.configure_running(streak.id, streak.name, streak.colour, meta, count)
            self.sidebar_list.append(row)

        if ended and self.state.settings.show_ended:
            for streak in ended:
                row = StreaksSidebarRow()
                row.section = "ended"
                best = engine.best_run(streak, today, settings)
                meta = engine.sidebar_ended_meta(streak, best.length if best else 0)
                row.configure_ended(streak.id, streak.name, meta)
                self.sidebar_list.append(row)

        target_row = today_row
        row = self.sidebar_list.get_first_child()
        while row is not None:
            if isinstance(row, StreaksSidebarRow) and row.streak_id == previous_selection:
                target_row = row
                break
            row = row.get_next_sibling()
        self.sidebar_list.select_row(target_row)

    # -- selection / content ---------------------------------------------------------

    def _on_row_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None:
            return
        streak_id = row.streak_id
        self.state.set_selection(streak_id)

        if streak_id == 0:
            self.content_title.set_title(_("Today"))
            self.content_title.set_subtitle(self._today_view.title if self._today_view else "")
            self.content_stack.set_visible_child_name("today")
            self.today_view.show_day(None)
            return

        streak = next((s for s in self.state.streaks if s.id == streak_id), None)
        if streak is None:
            return
        settings = self.state.settings.to_engine()
        hist = engine.history(streak, self.state.today(), settings)
        self.content_title.set_title(streak.name)
        self.content_title.set_subtitle(hist.header_subtitle)
        self.streak_status_page.set_title(streak.name)
        self.content_stack.set_visible_child_name("streak")

    def _on_state_changed(self, _state: AppState) -> None:
        self._rebuild_sidebar()

    def _on_settings_changed(self, _settings, key: str) -> None:
        if key == "show-ended":
            self._rebuild_sidebar()
