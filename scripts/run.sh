#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"

# Compile if needed
[[ ! -f _build/build.ninja ]] && meson setup _build
meson compile -C _build

# Parse arguments
seed=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --seed) seed=1; shift ;;
    *) shift ;;
  esac
done

# Set up environment
export STREAKS_GRESOURCE="_build/src/streaks.gresource"
export GSETTINGS_SCHEMA_DIR="_build/data"
export STREAKS_DATA_DIR="_build/devdata"
export PYTHONPATH="src"

# Seed data if requested
if [[ $seed -eq 1 ]]; then
  rm -rf _build/devdata
  if [[ -f tests/fixtures/seed.py ]]; then
    export STREAKS_FAKE_TODAY="2026-09-13"
    python3 tests/fixtures/seed.py
  else
    echo "warning: tests/fixtures/seed.py not found, skipping seed"
  fi
fi

# Run the app
if [[ $seed -eq 1 ]]; then
  export STREAKS_FAKE_TODAY="2026-09-13"
fi
python3 -m streaks
