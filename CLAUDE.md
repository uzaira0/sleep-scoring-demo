# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run application
uv run python -m sleep_scoring_app

# Run all tests
pytest tests/ -v

# Run single test file
pytest tests/unit/test_algorithm_factory.py -v

# Lint and format
ruff check . && ruff format .

# Type check
basedpyright

# Build executable
pyinstaller sleep-scoring-demo.spec
```

## Project Overview

PyQt6 desktop application for visual sleep scoring of accelerometer data. Implements multiple sleep scoring algorithms (Sadeh, Cole-Kripke, van Hees 2015 SIB), nonwear detection (Choi, van Hees), and sleep period detection with interactive visualization.

---

## LAYERED ARCHITECTURE (MANDATORY)

```
┌─────────────────────────────────────────────────────────────┐
│  UI Layer (PyQt6)                                           │
│  ├── Widgets (dumb, emit signals only)                      │
│  ├── Connectors (subscribe to store, update widgets)        │
│  └── Coordinators (QTimer, QThread - Qt glue)               │
├─────────────────────────────────────────────────────────────┤
│  Redux Store (Single Source of Truth)                       │
│  └── Actions → Reducer → State → Subscribers                │
├─────────────────────────────────────────────────────────────┤
│  Services Layer (Headless, no Qt)                           │
│  ├── FileService, MarkerService, DiaryService               │
│  └── Use callbacks, not signals                             │
├─────────────────────────────────────────────────────────────┤
│  Core Layer (Pure domain logic)                             │
│  ├── Algorithms, Constants, Dataclasses                     │
│  └── No imports from UI or Services                         │
├─────────────────────────────────────────────────────────────┤
│  IO Layer (Unified sources/)                                │
│  └── CSV/GT3X loaders with DatabaseColumn enum              │
└─────────────────────────────────────────────────────────────┘
```

### Layer Rules

1. **Widgets are DUMB** - They emit signals, they do NOT:
   - Reference MainWindow or parent directly
   - Use `hasattr()` to check for parent attributes
   - Call services directly
   - Dispatch to store directly

2. **Connectors bridge Widget ↔ Store**:
   - Subscribe to store state changes
   - Update widget properties when state changes
   - Connect widget signals to store.dispatch()
   - Located in `ui/store_connectors.py`

3. **Services are HEADLESS** - No Qt imports, no signals:
   - Pure Python, testable without Qt
   - Use callbacks for async results
   - Located in `services/`

4. **Core has NO dependencies** on UI or Services:
   - Pure domain logic
   - Algorithms, dataclasses, constants
   - Located in `core/`

### Redux Pattern

```python
# Store is in ui/store.py
from sleep_scoring_app.ui.store import Actions

# Dispatch actions (never mutate state directly)
store.dispatch(Actions.file_selected(filename))
store.dispatch(Actions.date_navigated(1))

# Subscribe to changes (in Connectors)
store.subscribe(self._on_state_change)

def _on_state_change(self, old_state: UIState, new_state: UIState) -> None:
    if old_state.current_file != new_state.current_file:
        self._update_widget()
```

### Protocols Replace hasattr()

```python
# WRONG - Widget calling parent directly
class MyWidget(QWidget):
    def do_something(self):
        if hasattr(self.parent(), "plot_widget"):  # NO!
            self.parent().plot_widget.clear()

# CORRECT - Widget emits signal, Connector handles it
class MyWidget(QWidget):
    actionRequested = pyqtSignal()

    def do_something(self):
        self.actionRequested.emit()

# Connector in store_connectors.py
class MyWidgetConnector:
    def __init__(self, store, main_window):
        widget.actionRequested.connect(self._handle_action)

    def _handle_action(self):
        self.main_window.plot_widget.clear()  # Protocol guarantees this exists
```

---

## MANDATORY CODING STANDARDS

**These rules are NON-NEGOTIABLE. Violating them is unacceptable.**

### 1. StrEnums for ALL String Constants

```python
# WRONG - hardcoded strings
algorithm = "sadeh_1994"
marker_type = "MAIN_SLEEP"

# CORRECT - StrEnums from core/constants/
from sleep_scoring_app.core.constants import AlgorithmType, MarkerType

algorithm = AlgorithmType.SADEH_1994_ACTILIFE
marker_type = MarkerType.MAIN_SLEEP
```

### 2. Dataclass Access Over Dicts

```python
# WRONG - unnecessary dict conversion
metrics_dict = sleep_metrics.to_dict()
tst = metrics_dict.get("total_sleep_time")

# CORRECT - direct attribute access
tst = sleep_metrics.total_sleep_time

# ONLY use to_dict() when exporting/serializing to CSV/JSON/database
```

### 3. Type Annotations on ALL Function Signatures

```python
# WRONG
def calculate_metrics(period, results, x_data):
    ...

# CORRECT
def calculate_metrics(
    period: SleepPeriod,
    results: list[int],
    x_data: list[float],
) -> SleepMetrics | None:
    ...
```

### 4. Frozen Dataclasses for Configs

```python
@dataclass(frozen=True)  # Always frozen for configs
class AlgorithmConfig:
    threshold: float = 0.5
```

### 5. NO hasattr() Abuse

```python
# WRONG - hiding init order bugs
if hasattr(self.parent, "plot_widget"):
    self.parent.plot_widget.clear()

# CORRECT - Protocol guarantees attribute exists
self.parent.plot_widget.clear()

# VALID hasattr() uses only:
# - Optional library features: hasattr(gt3x_rs, 'load')
# - Duck typing for external objects
```

### 6. NO Backwards Compatibility When Refactoring

- **DELETE** old code completely
- **NO** deprecated wrappers or "legacy" fallbacks
- **UPDATE** all imports to new locations
- **GREP** for old names to ensure nothing references deleted code

### 7. Metrics are PER-PERIOD, Not Per-Date

```python
# WRONG - metrics at date level
class DailyData:
    sleep_metrics: dict  # NO!

# CORRECT - metrics attached to each period
for period in daily.sleep_markers.get_complete_periods():
    metrics = period.metrics  # Each period has its own metrics
```

---

## Data Hierarchy

```
Study → Participant → Date → (Sleep + Nonwear Markers) → Period → Metrics
```

- **DailyData** contains BOTH `sleep_markers` AND `nonwear_markers`
- **Metrics** belong to each **SleepPeriod**, NOT to the date
- **Nonwear** is a first-class citizen

---

## Key Files

| File | Purpose |
|------|---------|
| `ui/store.py` | Redux store, Actions, UIState |
| `ui/store_connectors.py` | All Connectors (Widget ↔ Store bridges) |
| `ui/protocols.py` | Protocol interfaces (replace hasattr) |
| `services/` | Headless services (no Qt) |
| `core/constants/` | All StrEnums |
| `core/dataclasses*.py` | Domain dataclasses |

---

## Database Migrations

```bash
uv run python -m sleep_scoring_app.data.migration_cli status
uv run python -m sleep_scoring_app.data.migration_cli migrate
```

- **ALWAYS** use numbered migrations in `migrations_registry.py`
- **NEVER** use `_migrate_*` or `_add_column_if_not_exists`
