#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
source scripts/lib/headless.sh

# Parse arguments
action="${1:-update}"

# Set test environment
export STREAKS_GRESOURCE="_build/src/streaks.gresource"
export GSETTINGS_SCHEMA_DIR="_build/data"
export GSETTINGS_BACKEND="memory"
export PYTHONPATH="src"

headless_setup

case "$action" in
  update)
    if [[ ! -f scripts/render_screens.py ]]; then
      echo "FAIL: scripts/render_screens.py missing"
      exit 1
    fi
    "${HEADLESS_RUNNER[@]}" timeout "${PYTEST_TIMEOUT:-600}" python3 scripts/render_screens.py --out tests/snapshots
    "${HEADLESS_RUNNER[@]}" timeout "${PYTEST_TIMEOUT:-600}" python3 scripts/render_screens.py --dark --out tests/snapshots/dark
    ;;
  check)
    "${HEADLESS_RUNNER[@]}" timeout "${PYTEST_TIMEOUT:-600}" python3 -m pytest -q tests/gui/test_snapshots.py
    ;;
  *)
    echo "Usage: $0 [update|check]"
    exit 1
    ;;
esac
