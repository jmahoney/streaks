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
if [[ "${STREAKS_HEADLESS:-0}" == "1" ]] || ([[ -z "${DISPLAY:-}" ]] && [[ -z "${WAYLAND_DISPLAY:-}" ]]); then
  xvfb-run -a -s "-screen 0 1600x1000x24 -dpi 96" python3 scripts/render_screens.py --out _build/screenshots "$@"
else
  python3 scripts/render_screens.py --out _build/screenshots "$@"
fi

# List PNGs written
find _build/screenshots -name '*.png' -type f
