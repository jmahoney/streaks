# Streaks

Keep track of things you do regularly. Streaks is a GNOME application that helps you maintain habits and track your progress on recurring goals.

## Quick Start

### Setup

Install dependencies:

```bash
scripts/bootstrap.sh --install
```

### Development

Run checks:

```bash
scripts/check.sh
```

Run the app:

```bash
scripts/run.sh
```

Run with seed data:

```bash
scripts/run.sh --seed
```

### Distribution

Build and run as a Flatpak:

```bash
scripts/flatpak.sh build
scripts/flatpak.sh run
```

## Architecture

- **Language**: Python 3.11+
- **UI Toolkit**: GTK 4 + Libadwaita
- **Build System**: Meson
- **Database**: Peewee ORM with SQLite
- **Testing**: pytest with PyGObject integration

For more details, see `CLAUDE.md` and `docs/design-spec.md`.
