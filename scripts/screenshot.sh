#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"

mkdir -p _build/screenshots

# Check if render_screens.py exists
if [[ ! -f scripts/render_screens.py ]]; then
  echo "FAIL: scripts/render_screens.py missing"
  exit 1
fi

# Set test environment
export STREAKS_GRESOURCE="_build/src/streaks.gresource"
export GSETTINGS_SCHEMA_DIR="_build/data"
export GSETTINGS_BACKEND="memory"
export PYTHONPATH="src"

# Check if we need xvfb
if [[ "${STREAKS_HEADLESS:-1}" == "1" ]] || ([[ -z "${DISPLAY:-}" ]] && [[ -z "${WAYLAND_DISPLAY:-}" ]]); then
  # Under xvfb GTK must be pinned to the X11 backend: with WAYLAND_DISPLAY still set, GTK4 prefers
  # Wayland and the "headless" windows would open on the user's real desktop.
  env -u WAYLAND_DISPLAY GDK_BACKEND=x11 xvfb-run -a -s "-screen 0 1600x1000x24 -dpi 96" timeout "${PYTEST_TIMEOUT:-600}" python3 scripts/render_screens.py --out _build/screenshots "$@"
else
  python3 scripts/render_screens.py --out _build/screenshots "$@"
fi

# List PNGs written
find _build/screenshots -name '*.png' -type f
