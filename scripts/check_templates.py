#!/usr/bin/env python3
"""Check template consistency between .blp and .py files, and a basic i18n-completeness pass.

The i18n checks are deliberately conservative: a bare literal is only
flagged when it contains a letter, so punctuation/placeholder-only strings (``":"``, ``""``,
``"04:00"``) that aren't meaningfully translatable don't need an explicit exemption list.
"""

import re
import sys
from pathlib import Path

_TRANSLATABLE_PROPS = ("label", "title", "subtitle", "tooltip-text", "placeholder-text")
_HAS_LETTER = re.compile(r"[A-Za-z]")

repo_root = Path(__file__).parent.parent
src_dir = repo_root / "src" / "streaks"
gresource_file = repo_root / "src" / "streaks.gresource.xml"
meson_build = repo_root / "src" / "meson.build"
po_potfiles = repo_root / "po" / "POTFILES"

errors = []

# Parse .blp files for templates and object IDs
blp_templates = {}
blp_ids = {}

for blp_file in src_dir.glob("**/*.blp"):
    with open(blp_file) as f:
        content = f.read()

    # Find template definitions: template $ClassName
    template_matches = re.findall(r"template\s+\$(\w+)", content)
    for match in template_matches:
        blp_templates[match] = str(blp_file)

    # Find object IDs
    id_pattern = r"(\w+)\s+(?:\{|:)"
    for match in re.finditer(id_pattern, content):
        obj_id = match.group(1)
        if blp_file not in blp_ids:
            blp_ids[blp_file] = []
        blp_ids[blp_file].append(obj_id)

# Parse .py files for class definitions
py_classes = {}
py_children = {}

for py_file in src_dir.glob("**/*.py"):
    with open(py_file) as f:
        content = f.read()

    # Find __gtype_name__, but only for classes bound to a Blueprint template (immediately
    # preceded by @Gtk.Template(...)): custom-drawn Gtk.Widget subclasses (src/streaks/widgets/)
    # have a GType name and no template.
    class_starts = list(re.finditer(r"(?m)^class\s+\w+\(", content))
    for i, class_match in enumerate(class_starts):
        start = class_match.start()
        end = class_starts[i + 1].start() if i + 1 < len(class_starts) else len(content)
        gtype_match = re.search(r"__gtype_name__\s*=\s*['\"](\w+)['\"]", content[start:end])
        if not gtype_match:
            continue
        preceding_lines = content[:start].rstrip("\n").splitlines()
        is_templated = bool(preceding_lines) and preceding_lines[-1].strip().startswith(
            "@Gtk.Template("
        )
        if is_templated:
            py_classes[gtype_match.group(1)] = str(py_file)

    # Find Gtk.Template.Child definitions
    child_pattern = r"(\w+)\s*=\s*Gtk\.Template\.Child\(\)"
    for match in re.finditer(child_pattern, content):
        child_name = match.group(1)
        if py_file not in py_children:
            py_children[py_file] = []
        py_children[py_file].append(child_name)

# Check template consistency
for template_name in blp_templates:
    if template_name not in py_classes:
        errors.append(
            f"FAIL templates: {blp_templates[template_name]}: "
            f"template ${template_name} has no matching __gtype_name__"
        )

for py_class_name in py_classes:
    if py_class_name not in blp_templates:
        errors.append(
            f"FAIL templates: {py_classes[py_class_name]}: "
            f"__gtype_name__ = '{py_class_name}' has no matching template"
        )

# Check gresource.xml
with open(gresource_file) as f:
    gresource_content = f.read()

for _template_name, blp_file in blp_templates.items():
    ui_path = str(blp_file).replace(".blp", ".ui")
    ui_name = ui_path.replace(str(src_dir) + "/", "")
    if ui_name not in gresource_content:
        errors.append(f"FAIL templates: {gresource_file}: missing {ui_name} from gresource")

# Check meson.build
with open(meson_build) as f:
    meson_content = f.read()

for _template_name, blp_file in blp_templates.items():
    blp_name = str(blp_file).replace(str(src_dir) + "/", "")
    if blp_name not in meson_content:
        errors.append(f"FAIL templates: {meson_build}: missing {blp_name} from blueprint input")

# Check po/POTFILES
with open(po_potfiles) as f:
    potfiles_content = f.read()

for _template_name, blp_file in blp_templates.items():
    blp_name = str(blp_file).replace(str(repo_root) + "/", "")
    if blp_name not in potfiles_content:
        errors.append(f"FAIL templates: {po_potfiles}: missing {blp_name}")

# Check Python sources in po/POTFILES (skip __init__.py and __main__.py)
for py_file in src_dir.glob("**/*.py"):
    if "__pycache__" in str(py_file):
        continue
    if py_file.name in ("__init__.py", "__main__.py"):
        continue
    py_name = str(py_file).replace(str(repo_root) + "/", "")
    if py_name not in potfiles_content:
        errors.append(f"FAIL templates: {po_potfiles}: missing {py_name}")

# Check streaks_sources in meson.build
with open(meson_build) as f:
    meson_content = f.read()

for py_file in src_dir.glob("*.py"):
    if "__pycache__" in str(py_file):
        continue
    py_name = str(py_file).replace(str(src_dir) + "/", "")
    expected = f"'streaks/{py_name}'"
    if expected not in meson_content:
        errors.append(f"FAIL templates: {meson_build}: missing streaks/{py_name}")

# Check .blp files: every `label:`/`title:`/`subtitle:`/`tooltip-text:`/`placeholder-text:` with
# a bare (non-`_(...)`) string literal must not contain a letter — i.e. real translatable text
# must go through `_()`.
_blp_prop_pattern = re.compile(
    r"\b(?:" + "|".join(re.escape(p) for p in _TRANSLATABLE_PROPS) + r")\s*:\s*"
    r'(?P<value>_\(\s*"(?:[^"\\]|\\.)*"\s*\)|"(?:[^"\\]|\\.)*")'
)

for blp_file in src_dir.glob("**/*.blp"):
    with open(blp_file) as f:
        content = f.read()
    for match in _blp_prop_pattern.finditer(content):
        value = match.group("value")
        if value.startswith("_("):
            continue  # already translatable
        literal = value[1:-1]  # strip the surrounding quotes
        if _HAS_LETTER.search(literal):
            line_no = content.count("\n", 0, match.start()) + 1
            errors.append(
                f"FAIL i18n: {blp_file}:{line_no}: untranslated literal {value} (wrap it in _(...))"
            )

# Check .py files: a widget built with a translatable-looking keyword (`label=`/`title=`/etc.)
# must not be given a bare string literal containing a letter — it must be `_(...)`/`ngettext(...)`.
# Dynamic values (`label=goal.name`, `label=some_var`) have no
# quote right after `=` and are never matched.
_py_kwarg_pattern = re.compile(
    r"\b(?:" + "|".join(p.replace("-", "_") for p in _TRANSLATABLE_PROPS) + r")\s*=\s*"
    r'(?P<value>f?\'(?:[^\'\\]|\\.)*\'|f?"(?:[^"\\]|\\.)*")'
)

for py_file in src_dir.glob("**/*.py"):
    if "__pycache__" in str(py_file):
        continue
    with open(py_file) as f:
        content = f.read()
    for match in _py_kwarg_pattern.finditer(content):
        value = match.group("value")
        # A preceding `_(`/`ngettext(` (any whitespace in between) means this literal is one of
        # gettext's own arguments, not a bare, untranslated widget keyword value.
        before = content[: match.start()]
        if re.search(r"(?:_|ngettext)\(\s*$", before):
            continue
        literal = value[1:-1] if not value.startswith("f") else value[2:-1]
        if "{" in literal:
            continue  # f-string with interpolation: not a plain literal
        if _HAS_LETTER.search(literal):
            line_no = content.count("\n", 0, match.start()) + 1
            errors.append(
                f"FAIL i18n: {py_file}:{line_no}: untranslated literal {value} "
                f"(wrap it in _(...)/ngettext(...))"
            )

# Print errors
if errors:
    for error in errors:
        print(error)
    sys.exit(1)
else:
    print("PASS templates")
    sys.exit(0)
