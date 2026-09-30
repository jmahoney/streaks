"""An hour/minute picker popover with an optional heading and on/off switch."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GObject, Gtk


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/time_popover.ui")
class StreaksTimePopover(Gtk.Popover):
    """Picks a time of day as minutes since midnight.

    ``heading`` shows a title above the spin buttons when set. ``toggle-label`` adds a labelled
    switch; while it is off the spin buttons are insensitive. Emits ``changed`` on any edit.
    """

    __gtype_name__ = "StreaksTimePopover"

    __gsignals__ = {
        "changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    heading_label = Gtk.Template.Child()
    toggle_row = Gtk.Template.Child()
    toggle_label_widget = Gtk.Template.Child()
    switch = Gtk.Template.Child()
    hour_spin = Gtk.Template.Child()
    minute_spin = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.hour_spin.connect("value-changed", self._on_changed)
        self.minute_spin.connect("value-changed", self._on_changed)
        self.switch.connect("notify::active", self._on_changed)
        self._update_sensitivity()

    def _on_changed(self, *_args) -> None:
        self._update_sensitivity()
        self.emit("changed")

    def _update_sensitivity(self) -> None:
        enabled = self.active
        self.hour_spin.set_sensitive(enabled)
        self.minute_spin.set_sensitive(enabled)

    @GObject.Property(type=str, default="")
    def heading(self) -> str:
        return self.heading_label.get_label()

    @heading.setter
    def heading(self, value: str) -> None:
        self.heading_label.set_label(value)
        self.heading_label.set_visible(bool(value))

    @GObject.Property(type=str, default="")
    def toggle_label(self) -> str:
        return self.toggle_label_widget.get_label()

    @toggle_label.setter
    def toggle_label(self, value: str) -> None:
        self.toggle_label_widget.set_label(value)
        self.toggle_row.set_visible(bool(value))
        self._update_sensitivity()

    @GObject.Property(type=bool, default=True)
    def active(self) -> bool:
        """Whether the time is in use: the switch's state, or always true without a switch."""
        return not self.toggle_row.get_visible() or self.switch.get_active()

    @active.setter
    def active(self, value: bool) -> None:
        self.switch.set_active(value)

    @GObject.Property(type=int, default=0)
    def minutes(self) -> int:
        """Minutes since midnight."""
        return int(self.hour_spin.get_value()) * 60 + int(self.minute_spin.get_value())

    @minutes.setter
    def minutes(self, value: int) -> None:
        self.hour_spin.set_value(value // 60)
        self.minute_spin.set_value(value % 60)
