"""Offscreen rendering helpers, shared by the GUI tests and scripts/render_screens.py.

Turns an already realized/mapped/allocated GTK widget into a `Gdk.Texture`, a PNG file, or raw
pixel bytes, without ever needing a visible window manager.

Pixels are read via a PNG round-trip: `Gdk.Texture.download()` is not marshallable from
PyGObject (its buffer argument lacks an out annotation), so it silently returns nothing.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")

from gi.repository import (  # noqa: E402
    Adw,
    Gdk,
    Gio,
    Graphene,  # noqa: E402
    Gtk,
)

_configured = False


_accent_pin: Gtk.CssProvider | None = None


def set_colour_scheme(dark: bool) -> None:
    """Force the light or dark scheme.

    In light the accent is pinned to GNOME's default blue regardless of the host session's accent
    colour (libadwaita reads it from the portal or GSettings; the design assumes blue). In dark
    the pin is dropped so the app's own dark accent (amber, in `data/style.css`) applies.
    """
    global _accent_pin
    style_manager = Adw.StyleManager.get_default()
    display = Gdk.Display.get_default()
    if _accent_pin is not None:
        Gtk.StyleContext.remove_provider_for_display(display, _accent_pin)
        _accent_pin = None
    if dark:
        style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        return
    style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
    _accent_pin = Gtk.CssProvider()
    _accent_pin.load_from_string(
        ":root { --accent-bg-color: #3584e4; --accent-fg-color: #ffffff; --accent-color: #1c71d8; }"
    )
    Gtk.StyleContext.add_provider_for_display(
        display, _accent_pin, Gtk.STYLE_PROVIDER_PRIORITY_USER
    )


def configure_for_rendering() -> None:
    """Force deterministic, animation-free, light-themed rendering.

    Idempotent, so it is safe to call from multiple fixtures/entry points. Note that
    `GSK_RENDERER`, `GDK_SCALE`, `ADW_DISABLE_PORTAL` and `GTK_A11Y` are environment variables
    that must be set by the caller *before* `gi`/`Gtk` are imported at all — this function only
    sets in-process toolkit state that can be changed at any time.
    """
    global _configured
    if _configured:
        return

    set_colour_scheme(dark=False)

    # Background for detached dialog children (see screens.build_screen), matching the colours
    # `Adw.Dialog` gives its sheet.
    dialog_host = Gtk.CssProvider()
    dialog_host.load_from_string(
        ".render-dialog-host { background-color: var(--dialog-bg-color); "
        "color: var(--dialog-fg-color); }"
    )
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), dialog_host, Gtk.STYLE_PROVIDER_PRIORITY_USER
    )

    settings = Gtk.Settings.get_default()
    settings.set_property("gtk-font-name", "Cantarell 11")
    settings.set_property("gtk-enable-animations", False)
    settings.set_property("gtk-cursor-blink", False)
    settings.set_property("gtk-xft-antialias", 1)
    settings.set_property("gtk-xft-hinting", 1)
    settings.set_property("gtk-xft-hintstyle", "hintslight")
    settings.set_property("gtk-xft-rgba", "none")

    _configured = True


def make_test_application() -> Adw.Application:
    """Build and register a `StreaksApplication`.

    `NON_UNIQUE` so a test process never attaches to a real running Streaks instance on the
    session bus.
    """
    from streaks.main import StreaksApplication

    app = StreaksApplication(flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.register()
    return app


def render_widget(widget: Gtk.Widget, width: int, height: int) -> Gdk.Texture:
    """Render `widget` (already realized/mapped/allocated) to a `width`x`height` texture.

    For a whole window, pass the window itself as `widget`.
    """
    paintable = Gtk.WidgetPaintable.new(widget)
    snapshot = Gtk.Snapshot()
    paintable.snapshot(snapshot, width, height)
    node = snapshot.to_node()

    native = widget.get_native()
    renderer = native.get_renderer()

    bounds = Graphene.Rect()
    bounds.init(0, 0, width, height)
    return renderer.render_texture(node, bounds)


def texture_to_png(texture: Gdk.Texture, path: str) -> None:
    """Write `texture` to `path` as a PNG file."""
    texture.save_to_png(path)


def texture_pixels(texture: Gdk.Texture) -> tuple[bytes, int, int, int]:
    """Get raw pixels from `texture` via a PNG round-trip (see module docstring for why).

    Returns `(data, stride, width, height)`. `data` is RGBA8888, straight (non-premultiplied)
    alpha, row-major with no row padding (`stride == width * 4`) — see `pixel_at()`.
    """
    import io

    from PIL import Image

    png_bytes = bytes(texture.save_to_png_bytes().get_data())
    with Image.open(io.BytesIO(png_bytes)) as img:
        image = img.convert("RGBA")
        width, height = image.size
        data = image.tobytes()

    return data, width * 4, width, height


def pixel_at(pixels: bytes, stride: int, x: int, y: int) -> tuple[int, int, int]:
    """Return the `(r, g, b)` at `(x, y)` from a buffer produced by `texture_pixels()`."""
    offset = y * stride + x * 4
    r, g, b, _a = pixels[offset : offset + 4]
    return (r, g, b)
