#!/usr/bin/env python3
"""Scaffold a new GTK widget: creates its `.blp` template and `.py` module, and registers both
in `src/meson.build`. Usage: `add_ui.py <name>`."""

import re
import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: add_ui.py <name>")
    sys.exit(1)

name = sys.argv[1]
camel_name = "".join(word.capitalize() for word in name.split("_"))
template_name = f"Streaks{camel_name}"

repo_root = Path(__file__).parent.parent
ui_dir = repo_root / "src" / "streaks" / "ui"
src_dir = repo_root / "src" / "streaks"

# Create .blp file
blp_file = ui_dir / f"{name}.blp"
blp_content = f"""using Gtk 4.0;
using Adw 1;

template ${template_name} : Adw.Bin {{
}}
"""

if not blp_file.exists():
    ui_dir.mkdir(parents=True, exist_ok=True)
    blp_file.write_text(blp_content)
    print(f"Created {blp_file}")
else:
    print(f"Already exists: {blp_file}")

# Create .py file
py_file = src_dir / f"{name}.py"
py_content = f"""\"\"\"Module for {camel_name}.\"\"\"
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw


@Gtk.Template(resource_path="/com/cheerschopper/Streaks/streaks/ui/{name}.ui")
class {template_name}(Adw.Bin):
    \"\"\"UI component for {camel_name}.\"\"\"

    __gtype_name__ = "{template_name}"

    def __init__(self, **kwargs):
        \"\"\"Initialize the component.\"\"\"
        super().__init__(**kwargs)
"""

if not py_file.exists():
    py_file.write_text(py_content)
    print(f"Created {py_file}")
else:
    print(f"Already exists: {py_file}")

# Update meson.build
meson_file = repo_root / "src" / "meson.build"


def add_to_files_list(content: str, anchor: str, entry: str) -> str:
    """Insert `entry` as a new line before the closing `)` of the `files(` list that contains
    `anchor`, keeping the two-space indent and one trailing comma per line. Idempotent."""
    if entry in content:
        return content
    anchor_pos = content.index(anchor)
    close = re.compile(r"\n([ \t]*)\)").search(content, anchor_pos)
    assert close is not None, f"no closing paren after {anchor!r}"
    indent = close.group(1)
    before = content[: close.start()].rstrip()
    if not before.endswith(","):
        before += ","
    return f"{before}\n{indent}  {entry},\n{indent})" + content[close.end() :]


meson_content = meson_file.read_text()
updated = add_to_files_list(meson_content, "'streaks/ui/window.blp'", f"'streaks/ui/{name}.blp'")
updated = add_to_files_list(updated, "'streaks/window.py'", f"'streaks/{name}.py'")
if updated != meson_content:
    meson_file.write_text(updated)
    print(f"Updated {meson_file}")

# Update gresource.xml
gresource_file = repo_root / "src" / "streaks.gresource.xml"
gresource_content = gresource_file.read_text()

ui_line = f"    <file>streaks/ui/{name}.ui</file>"
if ui_line not in gresource_content:
    gresource_content = gresource_content.replace(
        "    <file>streaks/ui/window.ui</file>",
        f"    <file>streaks/ui/window.ui</file>\n{ui_line}",
    )
    gresource_file.write_text(gresource_content)
    print(f"Updated {gresource_file}")

# Update po/POTFILES
potfiles = repo_root / "po" / "POTFILES"
potfiles_content = potfiles.read_text()

potfiles_blp_line = f"src/streaks/ui/{name}.blp"
potfiles_py_line = f"src/streaks/{name}.py"

if potfiles_blp_line not in potfiles_content:
    potfiles_content += f"{potfiles_blp_line}\n"
    potfiles.write_text(potfiles_content)
    print(f"Updated {potfiles}")

if potfiles_py_line not in potfiles_content:
    potfiles_content += f"{potfiles_py_line}\n"
    potfiles.write_text(potfiles_content)
    print(f"Updated {potfiles} with python file")

print(f"Successfully added UI component: {name}")
