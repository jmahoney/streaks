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
| **Distribution** | Flatpak (via `org.gnome.Sdk//47` or latest stable) |
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

*   **Isolation:** Keep database models separate from your view/UI logic (e.g., inside `src/models.py`). 
*   **Thread Safety:** Use Peewee's `SqliteDatabase` engine. For high-volume UI interactions, wrap read/write queries in worker threads and return results to the UI thread using `GLib.idle_add()`.
*   **Sandbox Storage:** Production data must always resolve to the secure user data sandbox provided by GLib.

```python
import os
from peewee import SqliteDatabase, Model, CharField, DateTimeField, IntegerField
from gi.repository import GLib

# Safe data path resolution inside Flatpak sandbox
data_dir = os.path.join(GLib.get_user_data_dir(), "streaks")
os.makedirs(data_dir, exist_ok=True)
db_path = os.path.join(data_dir, "streaks.db")

db = SqliteDatabase(db_path, pragmas={'foreign_keys': 1})

class BaseModel(Model):
    class Meta:
        database = db

class Streak(BaseModel):
    title = CharField()
    current_count = IntegerField(default=0)
    created_at = DateTimeField()
```

### 3. Testing Strategy
We enforce rigorous, automated separation between pure unit logic and active UI tests.

#### A. Automated Unit Tests (`tests/test_unit.py`)
When testing database operations, **NEVER** write to the user's live production database. Use Peewee's built-in support for an in-memory SQLite database context during execution.

```python
import pytest
from peewee import SqliteDatabase
from com.cheerschopper.Streaks.models import Streak

@pytest.fixture(autouse=True)
def test_db():
    """Swaps the production database for an isolated, safe in-memory database."""
    test_db = SqliteDatabase(':memory:')
    test_db.bind([Streak])
    test_db.connect()
    test_db.create_tables([Streak])
    yield test_db
    test_db.close()

def test_create_streak():
    streak = Streak.create(title="Gym Routine", current_count=5)
    assert streak.id is not None
    assert streak.title == "Gym Routine"
```

#### B. Automated GUI Integration Tests (`tests/test_gui.py`)
Initialize components and iteratively flush the standard GLib context pipeline to simulate desktop interactions without needing manual clicking.

```python
import pytest
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
from com.cheerschopper.Streaks.window import AppWindow

def process_events():
    """Flushes the current GLib main context queue to simulate runtime loop."""
    context = GLib.MainContext.default()
    while context.pending():
        context.iteration(False)

def test_window_initialization(app):
    window = AppWindow(application=app)
    window.present()
    process_events()
    
    assert window.title_text == "Default Title"
```

---

## Tooling & Core Commands

### Development Lifecycle
Meson compiles your Blueprint files, checks resources, and packages the environment smoothly.

*   **Configure Build:** `meson setup _build`
*   **Compile Code & Layouts:** `meson compile -C _build`
*   **Run App Locally:** `_build/src/com.cheerschopper.Streaks`

### Running Tests Automatically via Meson
*   **Run all automated test suites:**
    ```bash
    meson test -C _build --verbose
    ```
*   **Headless CI Execution:**
    If running UI tests in an environment without an active display server, prefix the test harness command with a virtual framebuffer wrapper:
    ```bash
    xvfb-run pytest tests/
    ```

---

## Agent Guardrails
*   **NEVER** build layout templates imperatively in Python. Implement all UI wireframes in Blueprint (`.blp`) files following the `claude-design/` source-of-truth instructions.
*   **NEVER** construct database queries using raw string concatenation or custom SQL fragments. Always utilize Peewee’s API methods (`.select()`, `.create()`, `.where()`) for safety.
*   **NEVER** execute heavy data queries iteratively directly on the main UI thread loop.
*   **ALWAYS** verify that any dependency added (like `peewee`) is explicitly added to the Flatpak manifest (`com.cheerschopper.Streaks.json`) so it correctly installs inside the containerised environment.
