#!/usr/bin/env bash
# Verify (and optionally install) the development toolchain for Streaks.
# Usage: scripts/bootstrap.sh [--install]
# Exit 0 when everything is present; 1 otherwise (with the exact install command).
set -u
cd "$(dirname "$0")/.."

INSTALL=0
[[ "${1:-}" == "--install" ]] && INSTALL=1

missing_apt=()
missing_other=()
fail=0

pass() { printf 'PASS %s\n' "$1"; }
failmsg() { printf 'FAIL %s: %s\n' "$1" "$2"; fail=1; }

# name | apt package | check command
checks=(
  "python3|python3|command -v python3"
  "meson|meson|command -v meson"
  "ninja|ninja-build|command -v ninja"
  "blueprint-compiler|blueprint-compiler|command -v blueprint-compiler"
  "glib-compile-resources|libglib2.0-dev-bin|command -v glib-compile-resources"
  "glib-compile-schemas|libglib2.0-bin|command -v glib-compile-schemas"
  "desktop-file-validate|desktop-file-utils|command -v desktop-file-validate"
  "appstreamcli|appstream|command -v appstreamcli"
  "xvfb-run|xvfb|command -v xvfb-run"
  "flatpak|flatpak|command -v flatpak"
  "flatpak-builder|flatpak-builder|command -v flatpak-builder"
  "gettext (msgfmt)|gettext|command -v msgfmt"
  "python: gi (PyGObject)|python3-gi|python3 -c 'import gi'"
  "python: Gtk 4|gir1.2-gtk-4.0|python3 -c \"import gi; gi.require_version('Gtk','4.0'); from gi.repository import Gtk\""
  "python: Adw 1|gir1.2-adw-1|python3 -c \"import gi; gi.require_version('Adw','1'); from gi.repository import Adw\""
  "python: peewee|python3-peewee|python3 -c 'import peewee'"
  "python: pytest|python3-pytest|python3 -c 'import pytest'"
  "python: pytest_mock|python3-pytest-mock|python3 -c 'import pytest_mock'"
  "python: PIL (Pillow, for snapshot diffs)|python3-pil|python3 -c 'import PIL'"
  "font: Cantarell|fonts-cantarell|fc-list | grep -qi cantarell"
)

for entry in "${checks[@]}"; do
  IFS='|' read -r name pkg cmd <<<"$entry"
  if bash -c "$cmd" >/dev/null 2>&1; then
    pass "$name"
  else
    failmsg "$name" "apt package '$pkg'"
    missing_apt+=("$pkg")
  fi
done

if command -v ruff >/dev/null 2>&1; then
  pass "ruff"
else
  failmsg "ruff" "install with: uv tool install ruff  (or pipx install ruff)"
  missing_other+=("uv tool install ruff")
fi

# Matches com.cheerschopper.Streaks.json's own "runtime-version".
runtime_version=$(python3 -c "import json; print(json.load(open('com.cheerschopper.Streaks.json'))['runtime-version'])")

if flatpak info "org.gnome.Sdk//$runtime_version" >/dev/null 2>&1 \
  && flatpak info "org.gnome.Platform//$runtime_version" >/dev/null 2>&1; then
  pass "flatpak: org.gnome.Sdk//$runtime_version + Platform//$runtime_version"
else
  failmsg "flatpak: org.gnome.Sdk//$runtime_version" \
    "flatpak install flathub org.gnome.Sdk//$runtime_version org.gnome.Platform//$runtime_version"
  missing_other+=("flatpak install flathub org.gnome.Sdk//$runtime_version org.gnome.Platform//$runtime_version")
fi

if (( fail )); then
  echo
  if ((${#missing_apt[@]})); then
    echo "Missing apt packages. Install with:"
    echo "  sudo apt install -y ${missing_apt[*]}"
  fi
  for c in "${missing_other[@]}"; do echo "  $c"; done
  if (( INSTALL )); then
    echo
    echo "--install given: running installs now."
    ((${#missing_apt[@]})) && sudo apt install -y "${missing_apt[@]}"
    for c in "${missing_other[@]}"; do eval "$c"; done
    echo "Re-run scripts/bootstrap.sh to confirm."
  fi
  exit 1
fi
echo
echo "All toolchain checks passed."
