#!/usr/bin/env python3
"""Check .blp/.py template consistency and basic i18n completeness for Streaks.

Verifies that every Blueprint template has a matching Python class and vice
versa, that every `.blp` is listed in the gresource bundle, `meson.build`,
and `po/POTFILES`, that every Python source is listed in `meson.build`, and
that translatable widget properties are not left as bare string literals.

The i18n checks are deliberately conservative: a bare literal is only
flagged when it contains a letter, so punctuation/placeholder-only strings
(``":"``, ``""``, ``"04:00"``) that aren't meaningfully translatable don't
need an explicit exemption list.
"""

import re
from pathlib import Path

_TRANSLATABLE_PROPS = ("label", "title", "subtitle", "tooltip-text", "placeholder-text")
_HAS_LETTER = re.compile(r"[A-Za-z]")

_BLP_PROP_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(p) for p in _TRANSLATABLE_PROPS) + r")\s*:\s*"
    r'(?P<value>_\(\s*"(?:[^"\\]|\\.)*"\s*\)|"(?:[^"\\]|\\.)*")'
)
_PY_KWARG_PATTERN = re.compile(
    r"\b(?:" + "|".join(p.replace("-", "_") for p in _TRANSLATABLE_PROPS) + r")\s*=\s*"
    r'(?P<value>f?\'(?:[^\'\\]|\\.)*\'|f?"(?:[^"\\]|\\.)*")'
)

repo_root = Path(__file__).parent.parent
src_dir = repo_root / "src" / "streaks"
gresource_file = repo_root / "src" / "streaks.gresource.xml"
meson_build = repo_root / "src" / "meson.build"
po_potfiles = repo_root / "po" / "POTFILES"


def collect_blp_templates(src_dir: Path) -> dict[str, Path]:
    """Map each `template $ClassName` name in a `.blp` file to that file's path."""
    templates: dict[str, Path] = {}
    for blp_file in src_dir.glob("**/*.blp"):
        content = blp_file.read_text()
        for match in re.finditer(r"template\s+\$(\w+)", content):
            templates[match.group(1)] = blp_file
    return templates


def collect_py_template_classes(src_dir: Path) -> dict[str, Path]:
    """Map each `__gtype_name__` of a `@Gtk.Template`-bound class to its file's path.

    Custom-drawn `Gtk.Widget` subclasses (`src/streaks/widgets/`) have a GType
    name but no template, so only classes immediately preceded by
    `@Gtk.Template(...)` count.
    """
    classes: dict[str, Path] = {}
    for py_file in src_dir.glob("**/*.py"):
        content = py_file.read_text()
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
                classes[gtype_match.group(1)] = py_file
    return classes


def read_meson_build(meson_build: Path) -> str:
    """Return the contents of `src/meson.build`, read once for both meson checks."""
    return meson_build.read_text()


def read_gresource_entries(gresource_file: Path) -> str:
    """Return the contents of `streaks.gresource.xml`."""
    return gresource_file.read_text()


def read_potfiles(po_potfiles: Path) -> str:
    """Return the contents of `po/POTFILES`."""
    return po_potfiles.read_text()


def check_templates_match_classes(
    blp_templates: dict[str, Path], py_classes: dict[str, Path]
) -> list[str]:
    """Every `.blp` template must have a matching `__gtype_name__`, and vice versa."""
    errors = []
    for template_name, blp_file in blp_templates.items():
        if template_name not in py_classes:
            errors.append(
                f"FAIL templates: {blp_file}: "
                f"template ${template_name} has no matching __gtype_name__"
            )
    for py_class_name, py_file in py_classes.items():
        if py_class_name not in blp_templates:
            errors.append(
                f"FAIL templates: {py_file}: "
                f"__gtype_name__ = '{py_class_name}' has no matching template"
            )
    return errors


def check_gresource_lists_every_ui(
    blp_templates: dict[str, Path], src_dir: Path, gresource_file: Path, gresource_content: str
) -> list[str]:
    """Every `.blp`'s compiled `.ui` file must be listed in `streaks.gresource.xml`."""
    errors = []
    for blp_file in blp_templates.values():
        ui_path = str(blp_file).replace(".blp", ".ui")
        ui_name = ui_path.replace(str(src_dir) + "/", "")
        if ui_name not in gresource_content:
            errors.append(f"FAIL templates: {gresource_file}: missing {ui_name} from gresource")
    return errors


def check_meson_lists_every_blp(
    blp_templates: dict[str, Path], src_dir: Path, meson_build: Path, meson_content: str
) -> list[str]:
    """Every `.blp` must be listed as a blueprint input in `meson.build`."""
    errors = []
    for blp_file in blp_templates.values():
        blp_name = str(blp_file).replace(str(src_dir) + "/", "")
        if blp_name not in meson_content:
            errors.append(f"FAIL templates: {meson_build}: missing {blp_name} from blueprint input")
    return errors


def check_meson_lists_every_source(
    src_dir: Path, meson_build: Path, meson_content: str
) -> list[str]:
    """Every top-level `streaks/*.py` file must be listed in `streaks_sources` in `meson.build`."""
    errors = []
    for py_file in src_dir.glob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        py_name = str(py_file).replace(str(src_dir) + "/", "")
        expected = f"'streaks/{py_name}'"
        if expected not in meson_content:
            errors.append(f"FAIL templates: {meson_build}: missing streaks/{py_name}")
    return errors


def check_potfiles_complete(
    blp_templates: dict[str, Path],
    src_dir: Path,
    repo_root: Path,
    po_potfiles: Path,
    potfiles_content: str,
) -> list[str]:
    """Every `.blp` and Python source (except `__init__.py`/`__main__.py`) must be
    in `po/POTFILES`.
    """
    errors = []
    for blp_file in blp_templates.values():
        blp_name = str(blp_file).replace(str(repo_root) + "/", "")
        if blp_name not in potfiles_content:
            errors.append(f"FAIL templates: {po_potfiles}: missing {blp_name}")
    for py_file in src_dir.glob("**/*.py"):
        if "__pycache__" in str(py_file):
            continue
        if py_file.name in ("__init__.py", "__main__.py"):
            continue
        py_name = str(py_file).replace(str(repo_root) + "/", "")
        if py_name not in potfiles_content:
            errors.append(f"FAIL templates: {po_potfiles}: missing {py_name}")
    return errors


def check_blp_literals_translated(src_dir: Path) -> list[str]:
    """Every translatable `.blp` property with a bare literal containing a letter must use `_()`."""
    errors = []
    for blp_file in src_dir.glob("**/*.blp"):
        content = blp_file.read_text()
        for match in _BLP_PROP_PATTERN.finditer(content):
            value = match.group("value")
            if value.startswith("_("):
                continue
            literal = value[1:-1]
            if _HAS_LETTER.search(literal):
                line_no = content.count("\n", 0, match.start()) + 1
                errors.append(
                    f"FAIL i18n: {blp_file}:{line_no}: "
                    f"untranslated literal {value} (wrap it in _(...))"
                )
    return errors


def check_py_literals_translated(src_dir: Path) -> list[str]:
    """Every translatable Python kwarg with a bare literal containing a letter
    must use `_()`/`ngettext()`.
    """
    errors = []
    for py_file in src_dir.glob("**/*.py"):
        if "__pycache__" in str(py_file):
            continue
        content = py_file.read_text()
        for match in _PY_KWARG_PATTERN.finditer(content):
            value = match.group("value")
            # A preceding `_(`/`ngettext(` means this value is gettext's own argument,
            # exempt from the check below.
            before = content[: match.start()]
            if re.search(r"(?:_|ngettext)\(\s*$", before):
                continue
            literal = value[1:-1] if not value.startswith("f") else value[2:-1]
            if "{" in literal:
                continue  # an f-string with `{...}` interpolation has an unknown rendered value
            if _HAS_LETTER.search(literal):
                line_no = content.count("\n", 0, match.start()) + 1
                errors.append(
                    f"FAIL i18n: {py_file}:{line_no}: untranslated literal {value} "
                    f"(wrap it in _(...)/ngettext(...))"
                )
    return errors


def main() -> int:
    blp_templates = collect_blp_templates(src_dir)
    py_classes = collect_py_template_classes(src_dir)
    meson_content = read_meson_build(meson_build)
    gresource_content = read_gresource_entries(gresource_file)
    potfiles_content = read_potfiles(po_potfiles)

    errors = [
        *check_templates_match_classes(blp_templates, py_classes),
        *check_gresource_lists_every_ui(blp_templates, src_dir, gresource_file, gresource_content),
        *check_meson_lists_every_blp(blp_templates, src_dir, meson_build, meson_content),
        *check_meson_lists_every_source(src_dir, meson_build, meson_content),
        *check_potfiles_complete(blp_templates, src_dir, repo_root, po_potfiles, potfiles_content),
        *check_blp_literals_translated(src_dir),
        *check_py_literals_translated(src_dir),
    ]

    if errors:
        for error in errors:
            print(error)
        return 1
    print("PASS templates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
