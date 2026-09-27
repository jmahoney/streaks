# Contributing to Streaks

Thanks for your interest! Please read this first, because it'll save us both some time.

## This is a hobby project

I built Streaks for me, in my spare time. I think it's pretty much "done" for what I want. That said, there are likely  bugs or simple changes that make things better. So please feel free to suggest a feature or contribute some code. If I think it's worth including, then yay. If it changes things in a way that doesn't work for me (see the philosophy beind Streaks in the README), then I may not merge it. 

## Forking is encouraged

Feel free to fork the project and make whatever changes you want. Open source is great, eh? 

## Start with an issue

If you do want to contribute, please create and issue at <https://github.com/jmahoney/streaks/issues>.

- **Bugs:** say what you did, what you expected, and what happened instead. Include your
  distro/GNOME version and whether you're running the Flatpak or a source build.
- **Ideas:** describe the problem you're trying to solve, not just the feature you want.
- **Pull requests must reference an issue** (e.g. `Fixes #12` in the description). If a PR isn't
  tied to an issue, I'll probably close it and ask you to open one first.

## Keep pull requests small

Vibe-coding is totally allowed. Use Claude, Copilot, Cursor or whatever you like; this app was
built that way too (see the README). But **I won't review huge changes.** Big refactors,
sweeping rewrites, or a PR that touches most of the codebase will be closed, however good the
code is. If a change needs to be big, talk it through in the issue first and split it into
small, reviewable steps.

Whoever or whatever wrote the code, you own it. Before you open a PR:

- run `scripts/check.sh` and make sure it passes;
- add or update tests for the behaviour you changed;
- if you changed the UI deliberately, update the goldens with `scripts/snapshots.sh update` and
  put before/after screenshots in the PR description;
- make sure the PR contains only the change the issue asked for.

Please don't commit AI agent or editor configuration (`AGENTS.md`, `CLAUDE.md`, `.cursor/`, design
handoff bundles and so on). Those files are yours to keep locally, and the common ones are already
in `.gitignore`.

## How the code works

[docs/HACKING.md](docs/HACKING.md) covers the code layout, conventions (Blueprint for UI,
Peewee for data, `_()` for every string), test fixtures and helper scripts.

## Code of conduct

Be kind. This project follows the [GNOME Code of Conduct](https://conduct.gnome.org).
