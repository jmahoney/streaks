"""A single row in the sidebar list: the Today row, a running streak, or an ended one."""

from __future__ import annotations

import gettext

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import GObject, Gtk

from streaks import theme

_ = gettext.gettext

# Dot classes for the two non-streak rows; their colours live in data/style.css.
_TODAY_DOT_CLASS = "today-dot"
_ENDED_DOT_CLASS = "ended-dot"


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/sidebar_row.ui")
class StreaksSidebarRow(Gtk.ListBoxRow):
    """One sidebar row: Today, a running streak, or an ended streak."""

    __gtype_name__ = "StreaksSidebarRow"

    dot = Gtk.Template.Child()
    name_label = Gtk.Template.Child()
    meta_label = Gtk.Template.Child()
    count_label = Gtk.Template.Child()
    badge_label = Gtk.Template.Child()

    streak_id = GObject.Property(type=int, default=0)

    def _set_dot_class(self, css_class: str) -> None:
        """Paint the dot via one CSS class (the stylesheet supplies light and dark hues)."""
        for old in (_TODAY_DOT_CLASS, _ENDED_DOT_CLASS, *theme.colour_classes()):
            self.dot.remove_css_class(old)
        self.dot.add_css_class(css_class)

    def configure_today(self, open_count: int) -> None:
        """Set up the fixed "Today" row, badged with the number of open check-ins."""
        self.streak_id = 0
        self._set_dot_class(_TODAY_DOT_CLASS)
        self.name_label.set_label(_("Today"))
        self.meta_label.set_visible(False)
        self.count_label.set_visible(False)
        self.badge_label.set_label(str(open_count))
        self.badge_label.set_visible(open_count > 0)
        self.set_opacity(1.0)

    def configure_running(
        self, streak_id: int, name: str, colour: str, meta: str, count: int
    ) -> None:
        """Set up a row for a currently-running streak."""
        self.streak_id = streak_id
        self._set_dot_class(theme.colour_class(colour))
        self.name_label.set_label(name)
        self.meta_label.set_label(meta)
        self.meta_label.set_visible(True)
        self.count_label.set_label(str(count))
        self.count_label.set_visible(True)
        self.badge_label.set_visible(False)
        self.set_opacity(1.0)

    def configure_ended(self, streak_id: int, name: str, meta: str) -> None:
        """Set up a row for an ended streak (dimmed, no count)."""
        self.streak_id = streak_id
        self._set_dot_class(_ENDED_DOT_CLASS)
        self.name_label.set_label(name)
        self.meta_label.set_label(meta)
        self.meta_label.set_visible(True)
        self.count_label.set_visible(False)
        self.badge_label.set_visible(False)
        self.set_opacity(0.55)
