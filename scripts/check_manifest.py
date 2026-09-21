#!/usr/bin/env python3
"""Cross-checks `com.cheerschopper.Streaks.json` against `src/streaks/`'s third-party imports:
flags a runtime-version mismatch and any import with no matching Flatpak module."""

import ast
import json
import sys
from pathlib import Path

EXPECTED_RUNTIME_VERSION = "50"

repo_root = Path(__file__).parent.parent
src_dir = repo_root / "src" / "streaks"
manifest_file = repo_root / "com.cheerschopper.Streaks.json"

errors = []

# Load manifest
with open(manifest_file) as f:
    manifest = json.load(f)

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
    if module not in manifest_modules:
        errors.append(
            f"FAIL manifest: import '{module}' not found in com.cheerschopper.Streaks.json"
        )

# Print results
if errors:
    for error in errors:
        print(error)
    sys.exit(1)
else:
    print("PASS manifest")
    sys.exit(0)
