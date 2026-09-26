# Streaks

A native GNOME app for keeping track of things you want to do regularly: cutting your
fingernails every couple of weeks, going to the gym five times a week, or getting through all 75
days of 75 Hard. Streaks is a tracker, not a coach. It won't nag you and it won't cheer you on.
You tell it what you did, and it keeps count.

## What it does

- **Streaks on your schedule.** A streak can be daily, weekdays only, N times a week, or monthly.
- **One goal or a checklist.** A streak can be a single thing ("Floss") or several goals that
  must all be done ("75 Hard": two workouts, a gallon of water, ten pages…).
- **Today view.** A check-in card for every running streak, so you can tick things off as you
  go.
- **Catch up on quiet days.** If you forget to open the app for a few days, one dialog lets you
  answer for every unconfirmed day at once.
- **History.** Each streak has a heatmap, current and best runs, earlier runs, and a per-goal
  breakdown for the month.
- **Ended streaks.** You can end a streak and still look back at it later.
- **Preferences.** Set when your day starts (so a 1 a.m. check-in counts for the night before),
  how far back you can answer for, and how runs are counted.
- **Your data stays yours.** Everything is stored in a local SQLite database. There's no
  account, no network access and no telemetry. You can export everything to JSON.
- Light and dark styles that follow your system setting.

## Screenshots

| | |
|---|---|
| ![Today](docs/screenshots/today.png) Today — check-in cards, quiet-days banner | ![Sidebar](docs/screenshots/sidebar.png) Sidebar — running/ended streaks |
| ![Streak history](docs/screenshots/streak.png) Streak history — stats, heatmap, per-goal bars | ![New streak](docs/screenshots/new-streak.png) New/Edit streak dialog — single goal |
| ![New streak, multi-goal](docs/screenshots/new-streak-goals.png) New/Edit streak dialog — "Add more goals" | ![Catch up](docs/screenshots/catch-up.png) Catch-up dialog |
| ![Preferences](docs/screenshots/preferences.png) Preferences | ![Edit streak, multi-goal](docs/screenshots/edit-streak-goals.png) Editing a streak into a checklist |
| ![Today, dark](docs/screenshots/dark/today.png) Dark style — amber accent | ![Streak history, dark](docs/screenshots/dark/streak.png) Dark style — amber chart scale |

More in [`docs/screenshots/`](docs/screenshots/).

## Project status

This is a **hobby project**. I work on it in my spare time, when and as I feel like it. It
works, I use it, and there is no roadmap or release schedule. Issues and small pull requests
are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

## Getting started

These steps assume a Debian/Ubuntu-style system with GNOME 50-era libraries. The app is written
in Python 3.11+ with GTK 4, libadwaita, Blueprint and Meson.

### 1. Get the code and the toolchain

```bash
git clone https://github.com/jmahoney/streaks.git
cd streaks
scripts/bootstrap.sh            # check what's missing and print how to install it
scripts/bootstrap.sh --install  # or: install it (apt, plus ruff and the Flatpak runtime)
```

### 2. Build and run

```bash
meson setup _build
meson compile -C _build
scripts/run.sh          # run from the build tree (rebuilds first if needed)
scripts/run.sh --seed   # start fresh with five sample streaks, with "today" pinned to 13 Sep 2026
```

`scripts/run.sh` keeps its data in `_build/devdata/`, so development never touches the database
of an installed copy of the app.

### 3. Or build it as a Flatpak

```bash
scripts/flatpak.sh build   # flatpak-builder --user --install
scripts/flatpak.sh run
```

## Running the tests

`scripts/check.sh` runs everything CI would. That covers lint and formatting (Ruff), the
Blueprint and Meson build, template and translation checks, desktop-file/AppStream/GSettings
validation, the unit tests, the GUI tests and the screenshot comparison tests.

```bash
scripts/check.sh                # everything
scripts/check.sh --fast         # unit + GUI tests, no screenshot comparison (the usual inner loop)
scripts/check.sh --unit         # Ruff + unit tests only
scripts/check.sh --no-snapshots # everything except the screenshot comparison
```

The GUI tests open real GTK windows, but inside a virtual X display (Xvfb), so nothing pops up
on your desktop and a stuck test can't lock up your session.

The **snapshot tests** render every screen and compare it pixel by pixel against the approved
images in `tests/snapshots/`. If you change the UI on purpose, check the new renders with
`scripts/screenshot.sh`, then accept them:

```bash
scripts/snapshots.sh update
```

## Making changes

[docs/HACKING.md](docs/HACKING.md) covers the code layout, the conventions the code follows, the
test fixtures, the helper scripts and translations. [CONTRIBUTING.md](CONTRIBUTING.md) explains how
to get a change merged.

## How this was built

Streaks started as a rapid prototype built mostly by [Claude](https://claude.com/claude-code). I
decided what to build and reviewed and steered the result, and Claude wrote most of the code. It's
a good way to go from an idea to a working app in days, but the prompts don't prove anything. The
tests do, and I care that they pass:

- a unit suite for the streak engine, which pins every rule in
  [docs/engine-rules.md](docs/engine-rules.md);
- GUI integration tests that drive the real widgets;
- golden-image snapshot tests of every screen, in both light and dark styles, so the app keeps
  looking the way it was designed to look.

You don't need an AI assistant to work on Streaks, and the repo doesn't ship any agent
configuration. If you use one, bring your own setup. `AGENTS.md`, `CLAUDE.md` and similar files
are gitignored.

## Known gaps

- **Reminders are stored but never sent.** A streak's reminder time is saved, edited and
  exported, but nothing schedules or delivers a notification yet. Hooking it up to
  `Gio.Notification` or a scheduled background activation is future work.
- **No narrow-window layout.** Only the desktop-width layout exists. The sidebar and the Today
  card grid don't adapt to narrow windows.
- **No in-app light/dark switch.** The dark style (amber accent and chart scale) always follows
  the system setting.

## License

MIT. See [COPYING](COPYING).
