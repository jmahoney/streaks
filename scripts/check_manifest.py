#!/usr/bin/env python3
"""Cross-checks `com.cheerschopper.Streaks.json` against `src/streaks/`'s third-party imports:
flags a runtime-version mismatch and any import with no matching Flatpak module. Also checks that
the development manifest (`com.cheerschopper.Streaks.Devel.json`, used by GNOME Builder) matches
it apart from the app ID, command and `-Dprofile=development`."""

import ast
import json
import sys
from pathlib import Path

EXPECTED_RUNTIME_VERSION = "50"

# Import names that ship inside another PyPI distribution's sdist rather than having their own
# Flatpak module: `playhouse` (Peewee's migration/extension helpers) is part of the `peewee`
# package itself, installed by the "python3-peewee" module.
BUNDLED_IMPORTS = {"playhouse": "peewee"}

repo_root = Path(__file__).parent.parent
src_dir = repo_root / "src" / "streaks"
manifest_file = repo_root / "com.cheerschopper.Streaks.json"
devel_manifest_file = repo_root / "com.cheerschopper.Streaks.Devel.json"

errors = []

# Load manifest
with open(manifest_file) as f:
    manifest = json.load(f)

# The development manifest is the release one plus a `.Devel` ID and the development profile.
with open(devel_manifest_file) as f:
    devel_manifest = json.load(f)
expected_devel = json.loads(json.dumps(manifest))
expected_devel["id"] = f"{manifest['id']}.Devel"
expected_devel["command"] = f"{manifest['command']}.Devel"
for module in expected_devel.get("modules", []):
    if module.get("name") == "streaks":
        module.setdefault("config-opts", []).append("-Dprofile=development")
if devel_manifest != expected_devel:
    errors.append(
        f"FAIL manifest: {devel_manifest_file.name} has drifted from {manifest_file.name}; it "
        "should differ only by a '.Devel' id/command and '-Dprofile=development' on 'streaks'"
    )

# Check runtime version
if manifest.get("runtime-version") != EXPECTED_RUNTIME_VERSION:
    errors.append(
        f"FAIL manifest: runtime-version should be '{EXPECTED_RUNTIME_VERSION}', "
        f"got '{manifest.get('runtime-version')}'"
    )

# Collect module names from manifest
manifest_modules = set()
for module in manifest.get("modules", []):
    name = module.get("name", "")
    manifest_modules.add(name)
    # Also register the name with/without its "python3-" prefix, since Python imports are
    # unprefixed (e.g. `import peewee`) but flatpak module names conventionally carry it
    # (e.g. "python3-peewee") — either spelling in the manifest should satisfy either import.
    if name.startswith("python3-"):
        manifest_modules.add(name[len("python3-") :])
    else:
        manifest_modules.add(f"python3-{name}")

# Collect imports from Python files
imports = set()
for py_file in src_dir.glob("**/*.py"):
    if "__pycache__" in str(py_file):
        continue

    try:
        with open(py_file) as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split(".")[0]
                    imports.add(module_name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split(".")[0]
                    imports.add(module_name)
    except Exception as exc:
        errors.append(f"FAIL manifest: {py_file}: could not parse ({exc})")

# Filter out stdlib and gi
stdlib_modules = sys.stdlib_module_names
imports = {m for m in imports if m not in stdlib_modules and m != "gi"}

# Check each import
for module in sorted(imports):
    bundled_with = BUNDLED_IMPORTS.get(module)
    if module in manifest_modules or bundled_with in manifest_modules:
        continue
    errors.append(f"FAIL manifest: import '{module}' not found in com.cheerschopper.Streaks.json")

# Print results
if errors:
    for error in errors:
        print(error)
    sys.exit(1)
else:
    print("PASS manifest")
    sys.exit(0)
