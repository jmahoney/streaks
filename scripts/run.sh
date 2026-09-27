#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"

# Compile if needed
[[ ! -f builddir/build.ninja ]] && meson setup builddir
meson compile -C builddir

# Parse arguments
seed=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --seed) seed=1; shift ;;
    *) shift ;;
  esac
done

# Set up environment
export STREAKS_GRESOURCE="builddir/src/streaks.gresource"
export GSETTINGS_SCHEMA_DIR="builddir/data"
export STREAKS_DATA_DIR="builddir/devdata"
export PYTHONPATH="src"

# Seed data if requested
if [[ $seed -eq 1 ]]; then
  rm -rf builddir/devdata
  # Matches tests/fixtures/seed.py::FIXTURE_TODAY.
  export STREAKS_FAKE_TODAY="2026-09-13"
  if [[ -f tests/fixtures/seed.py ]]; then
    python3 tests/fixtures/seed.py
  else
    echo "warning: tests/fixtures/seed.py not found, skipping seed"
  fi
fi

# Run the app
python3 -m streaks
