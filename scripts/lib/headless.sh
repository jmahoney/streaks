# Shared Xvfb/X11 setup for scripts/check.sh, screenshot.sh, snapshots.sh and flatpak.sh.
#
# `headless_setup [always]` decides whether the caller needs Xvfb (`STREAKS_HEADLESS=0` opts
# into the live display; pass "always" to skip that opt-out for a caller that must never touch a
# real desktop) and sets:
#   NEED_XVFB           1 if Xvfb is required, 0 otherwise
#   HEADLESS_RUNNER      xvfb-run prefix array, to run a command through directly (empty when
#                        NEED_XVFB=0)
#   HEADLESS_RUNNER_STR  the same prefix as a string, for a caller that builds its command with
#                        `eval` (empty when NEED_XVFB=0)
# Xvfb needs GTK on the X11 backend; see docs/HACKING.md › Headless tests.
headless_setup() {
  NEED_XVFB=0
  if [[ "${1:-}" == "always" ]] || [[ "${STREAKS_HEADLESS:-1}" == "1" ]] \
    || ([[ -z "${DISPLAY:-}" ]] && [[ -z "${WAYLAND_DISPLAY:-}" ]]); then
    NEED_XVFB=1
  fi

  HEADLESS_RUNNER=()
  HEADLESS_RUNNER_STR=""
  if [[ $NEED_XVFB -eq 1 ]]; then
    if ! command -v xvfb-run >/dev/null; then
      echo "FAIL setup: xvfb-run not found (sudo apt install xvfb), or run with STREAKS_HEADLESS=0"
      exit 1
    fi
    export GDK_BACKEND=x11
    unset WAYLAND_DISPLAY
    HEADLESS_RUNNER=(xvfb-run -a -s "-screen 0 1600x1400x24 -dpi 96")
    HEADLESS_RUNNER_STR="xvfb-run -a -s '-screen 0 1600x1400x24 -dpi 96' "
  fi
}
