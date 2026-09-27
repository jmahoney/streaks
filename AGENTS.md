# AGENTS.md

## Project Context
You are an expert GNOME software developer. This is a modern, native GNOME application built using **Python 3**, **PyGObject (GLib/GObject/GTK 4)**, and **libadwaita**. 

*   **Application ID:** `com.cheerschopper.Streaks`
*   **Design Rule:** Detailed layouts must strictly follow the provided UI mocks from `claude-design/`. Do not improvise UI padding or hierarchies. Use the exact structural widgets defined in those designs.

The application helps the user keep track of things they want to do regularly - daily, weekly, monthly, whatever. It might be remembering to cut their fingernails, going to the gym five times a week, or particpating in 75Hard. The application helps them keep track - it's not a scold, nor a supporter, it's a tracker that they deliberately update manually.

---

## Tech Stack & Standards

| Component | Standard Technology |
| :--- | :--- |
| **Language** | Python 3.11+ (Strictly type-hinted) |
| **UI Toolkit** | GTK 4 + Libadwaita (`Adw`) |
| **Layout Definition**| Blueprint markup compiler (`.blp`) |
| **Build System** | Meson (`meson.build`) |
| **Database & ORM** | **Peewee ORM** with an underlying SQLite engine |
| **Testing** | `pytest` + `pytest-mock` (Unit) & PyGObject integration (GUI) |
| **Distribution** | Flatpak (via `org.gnome.Sdk//50` or latest stable) |
| **Formatting / Lint**| Ruff (black-compatible styling) |

---

## Idiomatic Architecture Rules

### 1. Blueprint UI Markup (`.blp`)
Do **not** build complex UI layouts imperatively in Python, and **never** use standard raw XML (`.ui`) files. Write or update `.blp` files, which compile cleanly into binary GResources via Meson.

*   **Template Linking:** Bind your Blueprint layouts directly to your Python source files using the `template` tag. The template name inside Blueprint must exactly match the `__gtype_name__` of your Python subclass.
*   **Typography & Styles:** Leverage Libadwaita’s built-in style classes (e.g., `styles ["title-1"]`, `card`, `boxed-list`) instead of custom padding or hardcoded fonts.
*   **Internationalisation:** Wrap all user-facing strings using the `_()` Gettext format to support translation pipelines.

```blueprint
using Gtk 4.0;
using Adw 1;

template $AppWindow : Adw.ApplicationWindow {
  default-width: 800;
  default-height: 600;

  content: Adw.ToolbarView {
    top: Adw.HeaderBar {}
    content: Gtk.Box {
      orientation: vertical;
      halign: center;
      valign: center;

      Gtk.Label {
        label: _("Hello, GNOME!"); // Use _() for translatable strings
        styles ["title-1"]         # Use Adwaita typography classes
      }
    }
  };
}
```

```python
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import GObject, Gtk, Adw

class AppWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'AppWindow' # Must match the class name inside Blueprint

    title_text = GObject.Property(type=str, default="Default Title")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Components map automatically via GResource compilation
```

### 2. Secure Database Layer (Peewee ORM)
Using an ORM completely eliminates raw string manipulation, protecting the application against SQL injections. It also enforces strong relational data constraints natively in Python code.

*   **Isolation:** Keep database models separate from your view/UI logic (e.g., inside `src/streaks/models.py`). 
*   **Thread Safety:** Use Peewee's `SqliteDatabase` engine. For high-volume UI interactions, wrap read/write queries in worker threads and return results to the UI thread using `GLib.idle_add()`.
*   **Sandbox Storage:** Production data must always resolve to the secure user data sandbox provided by GLib.

```python
from streaks.models import Streak, init_db

init_db()  # resolves the sandboxed path via GLib.get_user_data_dir() and creates tables

streak = Streak.create(name="75 Hard", colour="#3584e4", period_kind="daily", created_on=today)
```

### 3. Testing Strategy
We enforce rigorous, automated separation between pure unit logic and active UI tests.

#### A. Automated Unit Tests (`tests/unit/`)
When testing database operations, **NEVER** write to the user's live production database. The
`in_memory_db` fixture in `tests/unit/conftest.py` swaps in an isolated, in-memory SQLite database
for every test (autouse); reuse it.

```python
from streaks.models import Streak

def test_create_streak(today):
    streak = Streak.create(name="Gym Routine", colour="#2ec27e", period_kind="daily", created_on=today)
    assert streak.id is not None
    assert streak.name == "Gym Routine"
```

#### B. Automated GUI Integration Tests (`tests/gui/`)
Initialize components and iteratively flush the standard GLib context pipeline to simulate desktop
interactions without needing manual clicking. Reuse the `app`/`fresh_state`/`seeded_state`/
`fresh_window`/`seeded_window`/`process_events` fixtures `tests/gui/conftest.py` provides.

```python
def test_window_initialization(fresh_window, process_events):
    window = fresh_window
    process_events()

    assert window.content_stack.get_visible_child_name() == "empty"
```

---

## Tooling & Core Commands

### Development Lifecycle
Meson compiles your Blueprint files, checks resources, and packages the environment smoothly.

*   **Configure Build:** `meson setup builddir`
*   **Compile Code & Layouts:** `meson compile -C builddir`
*   **Run App Locally:** `scripts/run.sh` (add `--seed` to pre-load the design-fixture data)

### Running Tests Automatically via Meson
*   **Run all automated test suites:**
    ```bash
    meson test -C builddir --verbose
    ```
*   **Headless CI Execution:**
    ```bash
    scripts/check.sh
    ```
    Pins GTK to the X11 backend under Xvfb, keeping GUI and snapshot test windows on a virtual display.

---

## Agent Guardrails
*   **NEVER** build layout templates imperatively in Python. Implement all UI wireframes in Blueprint (`.blp`) files following the `claude-design/` source-of-truth instructions.
*   **NEVER** construct database queries using raw string concatenation or custom SQL fragments. Always utilize Peewee’s API methods (`.select()`, `.create()`, `.where()`) for safety.
*   **NEVER** execute heavy data queries iteratively directly on the main UI thread loop.
*   **ALWAYS** verify that any dependency added (like `peewee`) is explicitly added to both Flatpak manifests (`com.cheerschopper.Streaks.json` and the Builder one, `com.cheerschopper.Streaks.Devel.json`) so it correctly installs inside the containerised environment.
