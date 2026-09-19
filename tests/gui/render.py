"""Offscreen rendering helpers, shared by the GUI tests and scripts/render_screens.py.

Turns an already realized/mapped/allocated GTK widget into a `Gdk.Texture`, a PNG file, or raw
pixel bytes, without ever needing a visible window manager.

Pixel format note: `texture_pixels()` round-trips the texture through PNG (`save_to_png_bytes()`
+ Pillow) rather than `Gdk.Texture.download()`. `download()`'s `data` parameter is under-annotated
in GDK's own introspection data (no `direction="out"`/array-length annotation), so GObject
Introspection cannot marshal it as an output buffer — calling it silently leaves the buffer
untouched (verified: it does this for *any* `Gdk.Texture`, not just ones produced by
`render_widget()`). The PNG round-trip gives each pixel as 4 bytes in plain **R, G, B, A** order,
straight (non-premultiplied) alpha — see `pixel_at()`.
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
    Graphene,  # noqa: E402
    Gtk,
)

_configured = False


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

    Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)

    # Pin the accent to GNOME's default blue regardless of the host session's accent colour
    # (libadwaita reads it from the portal or GSettings; the design assumes blue).
    accent = Gtk.CssProvider()
    accent.load_from_string(
        ":root { --accent-bg-color: #3584e4; --accent-fg-color: #ffffff; --accent-color: #1c71d8; }"
    )
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), accent, Gtk.STYLE_PROVIDER_PRIORITY_USER
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
