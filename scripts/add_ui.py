#!/usr/bin/env python3
"""Add a new UI component to the application."""

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
meson_content = meson_file.read_text()

blp_line = f"  input: files('streaks/ui/{name}.blp'),"
if blp_line not in meson_content:
    # Find the blueprints input line and add the new file
    if "input: files('streaks/ui/window.blp')," in meson_content:
        meson_content = meson_content.replace(
            "  input: files('streaks/ui/window.blp'),",
            f"  input: files('streaks/ui/window.blp',\n{blp_line}",
        )
        meson_file.write_text(meson_content)
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

# Update streaks_sources in meson.build
py_file_line = f"  'streaks/{name}.py',"
if py_file_line not in meson_content:
    if "  'streaks/window.py'" in meson_content:
        meson_content = meson_content.replace(
            "  'streaks/window.py'",
            f"  'streaks/window.py',\n{py_file_line}",
        )
        meson_file.write_text(meson_content)
        print(f"Updated {meson_file} with streaks_sources")

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
