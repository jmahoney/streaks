"""Main window: the sidebar/content shell (design-spec §1, §2)."""

from __future__ import annotations

import gettext
import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from streaks import clock, engine, models
from streaks.empty_view import StreaksEmptyView  # noqa: F401  registers $StreaksEmptyView
from streaks.models import Streak
from streaks.sidebar_row import StreaksSidebarRow
from streaks.state import AppState
from streaks.streak_dialog import StreaksStreakDialog
from streaks.streak_view import StreaksStreakView  # noqa: F401  registers $StreaksStreakView
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
        self.state.settings.connect("changed", self._on_settings_changed)

        self._today_view: engine.TodayView | None = None
        self._current_streak_id = 0
        self.end_streak_dialog: Adw.AlertDialog | None = None
        self.delete_streak_dialog: Adw.AlertDialog | None = None

        self._install_actions()
        self.sidebar_list.set_header_func(self._header_func)
        self.sidebar_list.connect("row-selected", self._on_row_selected)
        self.checkin_button.connect("clicked", self._on_checkin_clicked)
        self.streak_view.connect("catch-up", self._on_streak_catch_up)

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

        # Present-but-no-op for now; a later phase wires up the shortcuts window.
        show_help_overlay = Gio.SimpleAction.new("show-help-overlay", None)
        show_help_overlay.connect("activate", lambda *_args: None)
        self.add_action(show_help_overlay)

    def _on_new_streak(self, *_args) -> None:
        dialog = StreaksStreakDialog.for_new()
        dialog.set_state(self.state)
        dialog.present(self)

    def _on_edit_streak(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:
        streak_id = param.get_int32()
        streak = next((s for s in self.state.streaks if s.id == streak_id), None)
        if streak is None:
            return
        dialog = StreaksStreakDialog.for_edit(streak)
        dialog.set_state(self.state)
        dialog.present(self)

    def _on_end_streak(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:
        streak_id = param.get_int32()
        streak = next((s for s in self.state.streaks if s.id == streak_id), None)
        if streak is None:
            return
        dialog = Adw.AlertDialog(
            heading=_("End this streak?"),
            body=_("It moves to Ended in the sidebar. Its history stays readable."),
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("end", _("End streak"))
        dialog.set_response_appearance("end", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_end_streak_response, streak_id)
        self.end_streak_dialog = dialog
        dialog.present(self)

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
        streak = next((s for s in self.state.streaks if s.id == streak_id), None)
        if streak is None:
            return
        dialog = Adw.AlertDialog(
            heading=_("Delete %(name)s?") % {"name": streak.name},
            body=_("Every check-in for this streak will be removed. This cannot be undone."),
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("delete", _("Delete"))
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_delete_streak_response, streak_id)
        self.delete_streak_dialog = dialog
        dialog.present(self)

    def _on_delete_streak_response(
        self, _dialog: Adw.AlertDialog, response: str, streak_id: int
    ) -> None:
        if response != "delete":
            return
        streak = Streak.get_by_id(streak_id)
        models.delete_streak(streak)
        self.state.set_selection(0)
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
        _logger.info("catch-up requested for streak %s (not yet implemented)", streak_id)

    # -- header ---------------------------------------------------------------------

    def _set_header_for_page(self, page: str) -> None:
        """Show only the end-of-header controls that belong to ``page`` (design-spec §1)."""
        is_streak = page == "streak"
        self.search_button.set_visible(page == "today")
        self.menu_button.set_visible(not is_streak)
        self.checkin_button.set_visible(is_streak)
        self.more_button.set_visible(is_streak)

    def _build_more_menu(self, streak_id: int) -> Gio.Menu:
        menu = Gio.Menu()
        for label, action_name in (
            (_("Edit…"), "win.edit-streak"),
            (_("End streak"), "win.end-streak"),
            (_("Delete…"), "win.delete-streak"),
        ):
            item = Gio.MenuItem.new(label, None)
            item.set_action_and_target_value(action_name, GLib.Variant("i", streak_id))
            menu.append_item(item)
        return menu

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
            self._set_header_for_page("empty")
            self.content_title.set_title(_("Streaks"))
            self.content_title.set_subtitle("")
            self.content_stack.set_visible_child_name("empty")
            return

        self.sidebar_list.set_visible(True)
        self.footer_label.set_visible(True)
        self.sidebar_empty_label.set_visible(False)

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
            self._current_streak_id = 0
            self._set_header_for_page("today")
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
        self._current_streak_id = streak_id
        self._set_header_for_page("streak")
        self.more_button.set_menu_model(self._build_more_menu(streak_id))
        self.content_title.set_title(streak.name)
        self.content_title.set_subtitle(hist.header_subtitle)
        self.streak_view.configure(streak)
        self.content_stack.set_visible_child_name("streak")

    def _on_state_changed(self, _state: AppState) -> None:
        self._rebuild_sidebar()

    def _on_settings_changed(self, _settings, key: str) -> None:
        if key == "show-ended":
            self._rebuild_sidebar()
