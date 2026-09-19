"""A single row in the sidebar list: the Today row, a running streak, or an ended one.

No engine logic lives here — the caller (``window.py``) passes already-formatted strings and
numbers (from ``engine.sidebar_meta``/``sidebar_ended_meta``/``sidebar_count`` etc.); this module
only lays them out and applies the per-row colour dot.
"""

from __future__ import annotations

import gettext

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import GObject, Gtk

_ = gettext.gettext

TODAY_DOT_COLOUR = "rgba(0, 0, 0, .55)"
ENDED_DOT_COLOUR = "#c0bfbc"


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

    def __init__(self, **kwargs):
        """Initialize the row."""
        super().__init__(**kwargs)
        self.colour: str | None = None
        self._dot_provider = Gtk.CssProvider()
        self.dot.get_style_context().add_provider(
            self._dot_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _set_dot_colour(self, colour: str) -> None:
        self.colour = colour
        self._dot_provider.load_from_string(f"* {{ background-color: {colour}; }}")

    def configure_today(self, open_count: int) -> None:
        """Set up the fixed "Today" row, badged with the number of open check-ins."""
        self.streak_id = 0
        self.dot.add_css_class("today-dot")
        self._set_dot_colour(TODAY_DOT_COLOUR)
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
        self.dot.remove_css_class("today-dot")
        self._set_dot_colour(colour)
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
        self.dot.remove_css_class("today-dot")
        self._set_dot_colour(ENDED_DOT_COLOUR)
        self.name_label.set_label(name)
        self.meta_label.set_label(meta)
        self.meta_label.set_visible(True)
        self.count_label.set_visible(False)
        self.badge_label.set_visible(False)
        self.set_opacity(0.55)
