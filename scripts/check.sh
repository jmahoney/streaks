#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
source scripts/lib/headless.sh

# Set test environment
export STREAKS_GRESOURCE="${STREAKS_GRESOURCE:-builddir/src/streaks.gresource}"
export GSETTINGS_SCHEMA_DIR="${GSETTINGS_SCHEMA_DIR:-builddir/data}"
export GSETTINGS_BACKEND="${GSETTINGS_BACKEND:-memory}"

headless_setup
# Every pytest run is bounded so a hung GUI test fails instead of spinning forever.
PYTEST_TIMEOUT="${PYTEST_TIMEOUT:-600}"

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
  run_stage "unit" "timeout $PYTEST_TIMEOUT python3 -m pytest -q tests/unit"
else
  # Full check or GUI check
  run_stage "ruff format" "ruff format --check src tests scripts"
  run_stage "ruff check" "ruff check src tests scripts"
  blp_out=$(mktemp -d)
  run_stage "blueprint" "blueprint-compiler batch-compile $blp_out src \$(find src -name '*.blp')"
  rm -rf "$blp_out"
  if [[ -f builddir/build.ninja ]]; then
    run_stage "meson" "meson compile -C builddir"
  else
    run_stage "meson" "meson setup builddir && meson compile -C builddir"
  fi
  run_stage "templates" "python3 scripts/check_templates.py"
  run_stage "manifest" "python3 scripts/check_manifest.py"
  run_stage "desktop" "desktop-file-validate builddir/data/com.cheerschopper.Streaks.desktop"
  run_stage "appstream" "appstreamcli validate --no-net --explain builddir/data/com.cheerschopper.Streaks.metainfo.xml"
  run_stage "schema" "glib-compile-schemas --strict --dry-run data"

  if [[ $gui_only -ne 1 ]]; then
    run_stage "unit" "timeout $PYTEST_TIMEOUT python3 -m pytest -q tests/unit"
  fi

  # GUI tests
  run_stage "gui" "timeout $PYTEST_TIMEOUT ${HEADLESS_RUNNER_STR}python3 -m pytest -q tests/gui --ignore=tests/gui/test_snapshots.py"

  # Snapshots (only if not --fast or --no-snapshots)
  if [[ $fast -eq 0 ]] && [[ $no_snapshots -eq 0 ]]; then
    if [[ -d tests/snapshots ]] && [[ $(find tests/snapshots -name '*.png' 2>/dev/null | wc -l) -gt 0 ]]; then
      run_stage "snapshots" "timeout $PYTEST_TIMEOUT ${HEADLESS_RUNNER_STR}python3 -m pytest -q tests/gui/test_snapshots.py"
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
