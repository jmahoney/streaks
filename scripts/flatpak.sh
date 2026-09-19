#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Parse arguments
action="${1:-build}"

case "$action" in
  build)
    flatpak-builder --user --install --force-clean _flatpak com.cheerschopper.Streaks.json
    ;;
  run)
    flatpak run com.cheerschopper.Streaks
    ;;
  *)
    echo "Usage: $0 [build|run]"
    exit 1
    ;;
esac
