"""The sidebar's "RUNNING"/"ENDED" section header, set as a `GtkListBoxRow`'s header widget."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/section_header.ui")
class StreaksSectionHeader(Gtk.Label):
    """A sidebar section heading label, styled and margined to match the design."""

    __gtype_name__ = "StreaksSectionHeader"
