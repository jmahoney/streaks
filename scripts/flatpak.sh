#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"

# Parse arguments
action="${1:-build}"

case "$action" in
  build)
    flatpak-builder --user --install --force-clean _flatpak com.cheerschopper.Streaks.json
    ;;
  run)
    flatpak run com.cheerschopper.Streaks
    ;;
  test)
    # Two deterministic, headless checks that the installed bundle is actually usable — never on
    # a live display (see CLAUDE.md's hard rule): both run under Xvfb, pinned to the X11 backend.

    echo "-- bundle import check --"
    # Proves the sandbox's Python can see both the vendored `peewee` module and the app's own
    # `streaks` package at the path Meson installed it to (`pkgdatadir` = /app/share/streaks —
    # see `src/com.cheerschopper.Streaks.in`, which puts that on `sys.path` itself; here we do
    # the same by hand via PYTHONPATH since `--command=python3` bypasses that launcher script).
    # `--no-documents-portal`: this check never opens a file, and some CI/dev sandboxes (this one
    # included) don't run `xdg-document-portal`, which `flatpak run` otherwise insists on.
    # Every `flatpak run` option must come *before* the app id — anything after it (and after
    # `--command`'s own arguments) is passed to the command running inside the sandbox instead.
    flatpak run --command=python3 --no-documents-portal --env=PYTHONPATH=/app/share/streaks \
      com.cheerschopper.Streaks -c \
      "import peewee, streaks; print('import OK:', peewee.__version__, streaks.__file__)"
    echo "PASS flatpak import check"

    echo "-- headless window-open check --"
    # Proves `flatpak run` actually opens the main window, without ever putting it on the live
    # display (see CLAUDE.md's hard rule): runs under Xvfb, forced onto the X11 backend.
    # `--nosocket=wayland` overrides the manifest's `--socket=wayland` finish-arg for this one
    # run: on a real desktop session (as in this dev sandbox, which has a live Wayland compositor
    # alongside Xvfb) GTK would otherwise happily connect to *that* real, live compositor instead
    # of the throwaway Xvfb display, which is exactly what must never happen headlessly.
    # `--socket=x11` overrides `--socket=fallback-x11` the same way, so Xvfb's X11 socket is
    # mounted even though a Wayland socket also exists on the host.
    # `STREAKS_QUIT_AFTER_STARTUP=1` makes the app quit itself right after the window is realised
    # (see `main.py`), so this exits 0 well before `timeout` would otherwise have to kill it.
    env -u WAYLAND_DISPLAY GDK_BACKEND=x11 xvfb-run -a -s '-screen 0 1600x1000x24 -dpi 96' \
      timeout 30 flatpak run --nosocket=wayland --socket=x11 --no-documents-portal \
      --env=GDK_BACKEND=x11 --env=STREAKS_QUIT_AFTER_STARTUP=1 com.cheerschopper.Streaks
    echo "PASS flatpak window-open check"
    ;;
  *)
    echo "Usage: $0 [build|run|test]"
    exit 1
    ;;
esac
