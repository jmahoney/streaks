"""Main window module."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/window.ui")
class StreaksWindow(Adw.ApplicationWindow):
    """Main application window."""

    __gtype_name__ = "StreaksWindow"

    content_label = Gtk.Template.Child()

    def __init__(self, **kwargs):
        """Initialize the window."""
        super().__init__(**kwargs)
