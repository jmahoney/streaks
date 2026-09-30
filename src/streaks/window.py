"""Main window: the sidebar/content shell."""

from __future__ import annotations

import gettext
import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from streaks import engine, models, words
from streaks.catchup_dialog import StreaksCatchupDialog
from streaks.empty_view import StreaksEmptyView  # noqa: F401  registers $StreaksEmptyView
from streaks.models import Streak
from streaks.sidebar_row import StreaksSidebarRow
from streaks.state import AppState
from streaks.streak_dialog import StreaksStreakDialog
from streaks.streak_view import StreaksStreakView  # noqa: F401  registers $StreaksStreakView
from streaks.today_view import StreaksTodayView  # noqa: F401  registers $StreaksTodayView
from streaks.widgets import confirm_dialog

_ = gettext.gettext
_logger = logging.getLogger(__name__)


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/window.ui")
class StreaksWindow(Adw.ApplicationWindow):
    """Main application window: a navigation split view with a sidebar and content stack."""

    __gtype_name__ = "StreaksWindow"

    split_view = Gtk.Template.Child()
    search_bar = Gtk.Template.Child()
    search_entry = Gtk.Template.Child()
    sidebar_list = Gtk.Template.Child()
    sidebar_empty_label = Gtk.Template.Child()
    footer_label = Gtk.Template.Child()
    content_stack = Gtk.Template.Child()
    content_title = Gtk.Template.Child()
    today_view = Gtk.Template.Child()
    streak_view = Gtk.Template.Child()
    search_button = Gtk.Template.Child()
    menu_button = Gtk.Template.Child()
    more_button = Gtk.Template.Child()
    checkin_button = Gtk.Template.Child()
    new_button = Gtk.Template.Child()

    def __init__(self, state: AppState | None = None, **kwargs):
        """Initialize the window: build the sidebar from `state` (a fresh one if not given)."""
        super().__init__(**kwargs)
        self.state = state or AppState()
        self.state.settings.bind_window_state(self)
        self.state.connect("changed", self._on_state_changed)
        # Break `AppState`'s GSettings subscription once this window is done with it — see
        # `AppState.close()`.
        self.connect("destroy", self._on_destroy)

        self._current_streak_id = 0
        self._current_streak_ended = False
        self.end_streak_dialog: Adw.AlertDialog | None = None
        self.delete_streak_dialog: Adw.AlertDialog | None = None
        self.catchup_dialog: StreaksCatchupDialog | None = None

        self._install_actions()
        self.sidebar_list.set_header_func(self._header_func)
        self.sidebar_list.set_filter_func(self._filter_sidebar_row)
        self.sidebar_list.connect("row-selected", self._on_row_selected)
        self.checkin_button.connect("clicked", self._on_checkin_clicked)
        self.streak_view.connect("catch-up", self._on_streak_catch_up)

        self.search_bar.connect_entry(self.search_entry)
        self.search_bar.set_key_capture_widget(self)
        self.search_bar.set_visible(False)
        self.search_bar.connect("notify::search-mode-enabled", self._on_search_mode_changed)
        # "changed" fires synchronously on every keystroke, so filtering is deterministic in
        # tests.
        self.search_entry.connect("changed", self._on_search_changed)

        self.today_view.set_state(self.state)
        self.streak_view.set_state(self.state)
        self._rebuild_sidebar()

    # -- window actions -----------------------------------------------------------

    def _install_actions(self) -> None:
        new_streak = Gio.SimpleAction.new("new-streak", None)
        new_streak.connect("activate", self._on_new_streak)
        self.add_action(new_streak)

        edit_streak = Gio.SimpleAction.new("edit-streak", GLib.VariantType.new("i"))
        edit_streak.connect("activate", self._on_edit_streak)
        self.add_action(edit_streak)

        end_streak = Gio.SimpleAction.new("end-streak", GLib.VariantType.new("i"))
        end_streak.connect("activate", self._on_end_streak)
        self.add_action(end_streak)

        delete_streak = Gio.SimpleAction.new("delete-streak", GLib.VariantType.new("i"))
        delete_streak.connect("activate", self._on_delete_streak)
        self.add_action(delete_streak)

        select_today = Gio.SimpleAction.new("select-today", None)
        select_today.connect("activate", self._on_select_today)
        self.add_action(select_today)

        toggle_search = Gio.SimpleAction.new("toggle-search", None)
        toggle_search.connect("activate", self._on_toggle_search)
        self.add_action(toggle_search)

        # win.show-help-overlay is provided by GtkApplicationWindow from the
        # gtk/help-overlay.ui resource (src/streaks/ui/shortcuts.blp).

    def _on_new_streak(self, *_args) -> None:
        dialog = StreaksStreakDialog.for_new()
        dialog.set_state(self.state)
        dialog.present(self)

    def _on_edit_streak(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:
        streak_id = param.get_int32()
        streak = self.state.streak(streak_id)
        if streak is None:
            return
        dialog = StreaksStreakDialog.for_edit(streak)
        dialog.set_state(self.state)
        dialog.present(self)

    def _on_end_streak(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:
        streak_id = param.get_int32()
        streak = self.state.streak(streak_id)
        if streak is None:
            return
        self.end_streak_dialog = confirm_dialog(
            self,
            heading=_("End this streak?"),
            body=_("It moves to Ended in the sidebar. Its history stays readable."),
            confirm_id="end",
            confirm_label=_("End streak"),
            destructive=True,
            on_response=lambda dialog, response: self._on_end_streak_response(
                dialog, response, streak_id
            ),
        )

    def _on_end_streak_response(
        self, _dialog: Adw.AlertDialog, response: str, streak_id: int
    ) -> None:
        if response != "end":
            return
        streak = Streak.get_by_id(streak_id)
        models.end_streak(streak, self.state.today())
        self.state.reload()

    def _on_delete_streak(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:
        streak_id = param.get_int32()
        streak = self.state.streak(streak_id)
        if streak is None:
            return
        self.delete_streak_dialog = confirm_dialog(
            self,
            heading=_("Delete %(name)s?") % {"name": streak.name},
            body=_("Every check-in for this streak will be removed. This cannot be undone."),
            confirm_id="delete",
            confirm_label=_("Delete"),
            destructive=True,
            on_response=lambda dialog, response: self._on_delete_streak_response(
                dialog, response, streak_id
            ),
        )

    def _on_delete_streak_response(
        self, _dialog: Adw.AlertDialog, response: str, streak_id: int
    ) -> None:
        if response != "delete":
            return
        streak = Streak.get_by_id(streak_id)
        models.delete_streak(streak)
        self.state.selection = 0
        self.state.reload()

    def _on_select_today(self, *_args) -> None:
        today_row = self.sidebar_list.get_row_at_index(0)
        if today_row is not None:
            self.sidebar_list.select_row(today_row)

    def _on_checkin_clicked(self, _button: Gtk.Button) -> None:
        streak_id = self._current_streak_id
        self._on_select_today()
        if streak_id:
            self.today_view.scroll_to_streak(streak_id)

    def _on_streak_catch_up(self, _view: StreaksStreakView, streak_id: int) -> None:
        dialog = StreaksCatchupDialog(self.state, streak_id)
        self.catchup_dialog = dialog
        dialog.present(self)

    def _on_toggle_search(self, *_args) -> None:
        if not self.search_button.get_visible():
            return
        self.search_bar.set_search_mode(True)
        self.search_entry.grab_focus()

    # -- search -----------------------------------------------------------------------

    def _on_search_changed(self, _entry: Gtk.SearchEntry) -> None:
        self.sidebar_list.invalidate_filter()
        self.sidebar_list.invalidate_headers()

    def _on_search_mode_changed(self, *_args) -> None:
        active = self.search_bar.get_search_mode()
        # Hide the bar entirely when search is off: a visible-but-collapsed bar still takes its
        # share of the box spacing.
        self.search_bar.set_visible(active)
        if not active:
            self.search_entry.set_text("")
        self.sidebar_list.invalidate_filter()
        self.sidebar_list.invalidate_headers()

    def _filter_sidebar_row(self, row: Gtk.ListBoxRow) -> bool:
        if not isinstance(row, StreaksSidebarRow) or row.streak_id == 0:
            return True
        query = self.search_entry.get_text().strip().lower()
        if not query:
            return True
        return query in row.name_label.get_label().lower()

    # -- header ---------------------------------------------------------------------

    def _set_header_for_page(self, page: str) -> None:
        """Show only the end-of-header controls that belong to ``page``.

        An ended streak's page is read-only: no "Check in" button, and the ⋯ menu offers only
        Delete… (see ``_build_more_menu``).
        """
        is_streak = page == "streak"
        is_ended = is_streak and self._current_streak_ended
        self.search_button.set_visible(page == "today")
        self.menu_button.set_visible(not is_streak)
        self.checkin_button.set_visible(is_streak and not is_ended)
        self.more_button.set_visible(is_streak)

    def _build_more_menu(self, streak_id: int, ended: bool) -> Gio.Menu:
        menu = Gio.Menu()
        items = (
            [(_("Delete…"), "win.delete-streak")]
            if ended
            else [
                (_("Edit…"), "win.edit-streak"),
                (_("End streak"), "win.end-streak"),
                (_("Delete…"), "win.delete-streak"),
            ]
        )
        for label, action_name in items:
            item = Gio.MenuItem.new(label, None)
            item.set_action_and_target_value(action_name, GLib.Variant("i", streak_id))
            menu.append_item(item)
        return menu

    # -- sidebar building -----------------------------------------------------------

    def _header_func(self, row: Gtk.ListBoxRow, _before: Gtk.ListBoxRow | None) -> None:
        section = getattr(row, "section", None)
        if section is None or not row.get_child_visible():
            row.set_header(None)
            return

        # Find the previous *visible* row: _before ignores the search filter.
        prev_section = None
        sibling = row.get_prev_sibling()
        while sibling is not None:
            if isinstance(sibling, StreaksSidebarRow) and sibling.get_child_visible():
                prev_section = getattr(sibling, "section", None)
                break
            sibling = sibling.get_prev_sibling()

        if section == prev_section:
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
        # remove_all() also disposes the header widgets GtkListBox attached via _header_func.
        self.sidebar_list.remove_all()

    def _rebuild_sidebar(self) -> None:
        previous_selection = self.state.selection
        self._clear_sidebar()

        streaks = self.state.streaks
        if not streaks:
            self.sidebar_list.set_visible(False)
            self.footer_label.set_visible(False)
            self.sidebar_empty_label.set_visible(True)
            self._set_header_for_page("empty")
            self.content_title.set_title(_("Streaks"))
            self.content_title.set_subtitle("")
            self.content_stack.set_visible_child_name("empty")
            return

        self.sidebar_list.set_visible(True)
        self.footer_label.set_visible(True)
        self.sidebar_empty_label.set_visible(False)

        today = self.state.today()
        settings = self.state.settings.to_engine()

        today_row = StreaksSidebarRow()
        today_row.section = None
        today_row.configure_today(engine.open_count(streaks, today))
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
        self.state.selection = streak_id

        if streak_id == 0:
            self._current_streak_id = 0
            self._set_header_for_page("today")
            self.content_title.set_title(_("Today"))
            self.content_title.set_subtitle(words.fmt_weekday_day(self.state.today()))
            self.content_stack.set_visible_child_name("today")
            self.today_view.show_day(None)
            return

        streak = self.state.streak(streak_id)
        if streak is None:
            return
        self._current_streak_id = streak_id
        self._current_streak_ended = streak.ended_on is not None
        self._set_header_for_page("streak")
        self.more_button.set_menu_model(
            self._build_more_menu(streak_id, self._current_streak_ended)
        )
        self.content_title.set_title(streak.name)
        self.streak_view.configure(streak)
        self.content_title.set_subtitle(self.streak_view.header_subtitle)
        self.content_stack.set_visible_child_name("streak")

    def _on_state_changed(self, _state: AppState) -> None:
        self._rebuild_sidebar()

    def _on_destroy(self, *_args) -> None:
        self.state.close()
