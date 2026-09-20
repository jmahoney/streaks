#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"

# Parse arguments
action="${1:-update}"

# Set test environment
export STREAKS_GRESOURCE="_build/src/streaks.gresource"
export GSETTINGS_SCHEMA_DIR="_build/data"
export GSETTINGS_BACKEND="memory"
export PYTHONPATH="src"

# Render under xvfb by default (STREAKS_HEADLESS=0 uses the live display) so nothing pops up
# on the desktop; the offscreen renderer is display-independent anyway.
runner=()
if [[ "${STREAKS_HEADLESS:-1}" == "1" ]] || ([[ -z "${DISPLAY:-}" ]] && [[ -z "${WAYLAND_DISPLAY:-}" ]]); then
  # Under xvfb GTK must be pinned to the X11 backend: with WAYLAND_DISPLAY still set, GTK4 prefers
  # Wayland and the "headless" windows would open on the user's real desktop.
  export GDK_BACKEND=x11
  unset WAYLAND_DISPLAY
  runner=(xvfb-run -a -s "-screen 0 1600x1000x24 -dpi 96")
fi

case "$action" in
  update)
    if [[ ! -f scripts/render_screens.py ]]; then
      echo "FAIL: scripts/render_screens.py missing"
      exit 1
    fi
    "${runner[@]}" timeout "${PYTEST_TIMEOUT:-600}" python3 scripts/render_screens.py --out tests/snapshots
    "${runner[@]}" timeout "${PYTEST_TIMEOUT:-600}" python3 scripts/render_screens.py --dark --out tests/snapshots/dark
    ;;
  check)
    "${runner[@]}" timeout "${PYTEST_TIMEOUT:-600}" python3 -m pytest -q tests/gui/test_snapshots.py
    ;;
  *)
    echo "Usage: $0 [update|check]"
    exit 1
    ;;
esac
