#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"

# Set test environment
export STREAKS_GRESOURCE="${STREAKS_GRESOURCE:-_build/src/streaks.gresource}"
export GSETTINGS_SCHEMA_DIR="${GSETTINGS_SCHEMA_DIR:-_build/data}"
export GSETTINGS_BACKEND="${GSETTINGS_BACKEND:-memory}"

# Check if we need xvfb for headless testing
need_xvfb=0
if [[ "${STREAKS_HEADLESS:-0}" == "1" ]] || ([[ -z "${DISPLAY:-}" ]] && [[ -z "${WAYLAND_DISPLAY:-}" ]]); then
  need_xvfb=1
fi

declare -A results
stages=()

# Parse arguments
unit_only=0
gui_only=0
no_snapshots=0
fast=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --unit) unit_only=1; shift ;;
    --gui) gui_only=1; shift ;;
    --no-snapshots) no_snapshots=1; shift ;;
    --fast) fast=1; no_snapshots=1; shift ;;
    *) shift ;;
  esac
done

# Helper function to run a stage
run_stage() {
  local stage="$1"
  local cmd="$2"
  stages+=("$stage")

  echo -n "Running $stage... "
  if output=$(eval "$cmd" 2>&1); then
    echo "PASS $stage"
    results["$stage"]="PASS"
  else
    echo "FAIL $stage"
    results["$stage"]="FAIL"
    if [[ -n "$output" ]]; then
      echo "$output" | sed 's/^/    /'
    fi
  fi
}

# Determine which stages to run
if [[ $unit_only -eq 1 ]]; then
  run_stage "ruff format" "ruff format --check src tests scripts"
  run_stage "ruff check" "ruff check src tests scripts"
  run_stage "unit" "python3 -m pytest -q tests/unit"
else
  # Full check or GUI check
  run_stage "ruff format" "ruff format --check src tests scripts"
  run_stage "ruff check" "ruff check src tests scripts"
  blp_out=$(mktemp -d)
  run_stage "blueprint" "blueprint-compiler batch-compile $blp_out src \$(find src -name '*.blp')"
  rm -rf "$blp_out"
  if [[ -f _build/build.ninja ]]; then
    run_stage "meson" "meson compile -C _build"
  else
    run_stage "meson" "meson setup _build && meson compile -C _build"
  fi
  run_stage "templates" "python3 scripts/check_templates.py"
  run_stage "manifest" "python3 scripts/check_manifest.py"
  run_stage "desktop" "desktop-file-validate _build/data/com.cheerschopper.Streaks.desktop"
  run_stage "appstream" "appstreamcli validate --no-net --explain _build/data/com.cheerschopper.Streaks.metainfo.xml"
  run_stage "schema" "glib-compile-schemas --strict --dry-run data"

  if [[ $gui_only -ne 1 ]]; then
    run_stage "unit" "python3 -m pytest -q tests/unit"
  fi

  # GUI tests
  if true; then
    if [[ $need_xvfb -eq 1 ]]; then
      run_stage "gui" "xvfb-run -a -s '-screen 0 1600x1000x24 -dpi 96' python3 -m pytest -q tests/gui --ignore=tests/gui/test_snapshots.py"
    else
      run_stage "gui" "python3 -m pytest -q tests/gui --ignore=tests/gui/test_snapshots.py"
    fi
  fi

  # Snapshots (only if not --fast or --no-snapshots)
  if [[ $fast -eq 0 ]] && [[ $no_snapshots -eq 0 ]]; then
    if [[ -d tests/snapshots ]] && [[ $(find tests/snapshots -name '*.png' 2>/dev/null | wc -l) -gt 0 ]]; then
      if [[ $need_xvfb -eq 1 ]]; then
        run_stage "snapshots" "xvfb-run -a -s '-screen 0 1600x1000x24 -dpi 96' python3 -m pytest -q tests/gui/test_snapshots.py"
      else
        run_stage "snapshots" "python3 -m pytest -q tests/gui/test_snapshots.py"
      fi
    else
      echo "SKIP snapshots: no tests/snapshots yet"
      stages+=("snapshots")
      results["snapshots"]="SKIP"
    fi
  fi
fi

# Print summary
echo ""
echo "Summary:"
printf "%-20s | %s\n" "stage" "result"
printf "%-20s | %s\n" "---" "---"
for stage in "${stages[@]}"; do
  printf "%-20s | %s\n" "$stage" "${results[$stage]}"
done

# Exit with error if any test failed
for stage in "${stages[@]}"; do
  if [[ "${results[$stage]}" == "FAIL" ]]; then
    exit 1
  fi
done

exit 0
