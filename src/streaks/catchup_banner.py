"""The "quiet days" banner shown above the Today check-in cards (design-spec §3)."""

from __future__ import annotations

import gettext

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GObject, Gtk

from streaks.engine import Banner
from streaks.widgets.grid_widgets import StripWidget  # noqa: F401  registers $StripWidget

_ = gettext.gettext


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/catchup_banner.ui")
class StreaksCatchupBanner(Gtk.Box):
    """One streak's "days without a check-in" banner, with a catch-up shortcut.

    No engine logic lives here — ``configure()`` only places already-computed strings and cells
    from an ``engine.Banner``. Clicking "Catch up" emits ``catch-up`` with the streak id; the
    Today view opens the catch-up dialog for it.
    """

    __gtype_name__ = "StreaksCatchupBanner"

    __gsignals__ = {
        "catch-up": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    title_label = Gtk.Template.Child()
    body_label = Gtk.Template.Child()
    strip = Gtk.Template.Child()
    catch_up_button = Gtk.Template.Child()

    streak_id = GObject.Property(type=int, default=0)

    def __init__(self, **kwargs):
        """Initialize the banner."""
        super().__init__(**kwargs)
        self.catch_up_button.connect("clicked", self._on_catch_up_clicked)

    def _on_catch_up_clicked(self, _button: Gtk.Button) -> None:
        self.emit("catch-up", self.streak_id)

    def configure(self, banner: Banner) -> None:
        """Populate the banner from an ``engine.Banner``."""
        self.streak_id = banner.streak_id
        self.title_label.set_label(banner.title)
        self.body_label.set_label(banner.body)
        self.strip.set_cells(banner.strip)
