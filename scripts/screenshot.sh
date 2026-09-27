#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
source scripts/lib/headless.sh

mkdir -p builddir/screenshots

# Check if render_screens.py exists
if [[ ! -f scripts/render_screens.py ]]; then
  echo "FAIL: scripts/render_screens.py missing"
  exit 1
fi

# Set test environment
export STREAKS_GRESOURCE="builddir/src/streaks.gresource"
export GSETTINGS_SCHEMA_DIR="builddir/data"
export GSETTINGS_BACKEND="memory"
export PYTHONPATH="src"

headless_setup
"${HEADLESS_RUNNER[@]}" timeout "${PYTEST_TIMEOUT:-600}" python3 scripts/render_screens.py \
  --out builddir/screenshots "$@"

# List PNGs written
find builddir/screenshots -name '*.png' -type f
