"""Custom drawing widgets (design-spec §10): ``HeatmapWidget``, ``StripWidget``,
``EmptyGridWidget``. See ``grid_widgets.py``. Also holds small view helpers shared across
widgets: ``clear_children()`` and ``confirm_dialog()``.
"""

from __future__ import annotations

import gettext
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

_ = gettext.gettext


def clear_children(box: Gtk.Box) -> None:
    """Remove every child widget from ``box``."""
    child = box.get_first_child()
    while child is not None:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


def confirm_dialog(
    parent: Gtk.Widget,
    *,
    heading: str,
    body: str,
    confirm_id: str,
    confirm_label: str,
    destructive: bool,
    on_response: Callable[[Adw.AlertDialog, str], None],
) -> Adw.AlertDialog:
    """Build, wire and present a Cancel/confirm ``Adw.AlertDialog``, returning it.

    ``on_response`` is connected to the dialog's ``response`` signal, so it receives the dialog
    and the response id (``"cancel"`` or ``confirm_id``); wrap it in a ``lambda`` to pass through
    any extra context the caller needs. "Cancel" is both the default and the close response.
    """
    dialog = Adw.AlertDialog(heading=heading, body=body)
    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response(confirm_id, confirm_label)
    if destructive:
        dialog.set_response_appearance(confirm_id, Adw.ResponseAppearance.DESTRUCTIVE)
    dialog.set_default_response("cancel")
    dialog.set_close_response("cancel")
    dialog.connect("response", on_response)
    dialog.present(parent)
    return dialog
