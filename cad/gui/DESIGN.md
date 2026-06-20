# Implementation Architecture: Fiona CAD GUI Overhaul

## Executive Summary

This document specifies the complete implementation architecture for the Fiona CAD (ficad) GUI overhaul across 5 milestones (27 tasks). The architecture extends the existing Tkinter-based GUI with toolbar, status bar, face-filled rendering, ray-picking selection, property grouping, undo/redo, context menus, and search/filter — all while preserving 100% backward compatibility.

**Architecture Pattern:** Centralized coordinator (`SelectionCoordinator`) with decoupled panels communicating through the coordinator and via Tkinter virtual events (`<<CADEvent>>`). Undo/redo uses snapshot-based approach via `Document.to_dict()` / `Document.from_dict()`. All new features are additive: no existing method signatures change.

---

## Requirements

### Functional Requirements

| ID | Requirement | Milestone |
|----|------------|-----------|
| FR1 | Toolbar with primitive creation buttons (Box, Cylinder, Sphere) and action buttons (Recompute, Reset View, Toggle Grid) | M1 |
| FR2 | Status bar showing object count, cursor coordinates, mode hint | M1 |
| FR3 | Right-click / middle-click pan the viewport | M1 |
| FR4 | Keyboard shortcuts: Ctrl+Z/Y/A/Del/G/R/F5, Ctrl+N/O/S | M1 |
| FR5 | Window title shows file path for saved documents | M1 |
| FR6 | Primitives render with filled faces (flat-shaded) plus wireframe overlay | M2 |
| FR7 | XYZ axes indicator (triad) in viewport corner | M2 |
| FR8 | Visual selection highlight in viewport | M2 |
| FR9 | Ray-picking: click 3D object to select it | M3 |
| FR10 | Property editor groups properties by category with headers | M3 |
| FR11 | Apply/Reset buttons in property editor | M3 |
| FR12 | Color property support with color picker dialog | M3 |
| FR13 | Selection is coordinated between viewport, tree, and property editor | M3 |
| FR14 | Undo/Redo stack (snapshot-based, 50-deep) | M4 |
| FR15 | All mutation operations push to undo stack | M4 |
| FR16 | Delete confirmation dialog with "Don't ask again" | M4 |
| FR17 | Recent files list (5 files, persisted to JSON) | M4 |
| FR18 | Save-on-close confirmation when document modified | M4 |
| FR19 | Context menu in viewport (right-click) | M5 |
| FR20 | Context menu in project tree (right-click) | M5 |
| FR21 | Search/filter field above project tree | M5 |
| FR22 | Object duplication command | M5 |

### Non-Functional Requirements

| ID | Requirement | Target |
|----|------------|--------|
| NFR1 | Backward compatibility | All existing code continues to work unchanged |
| NFR2 | Undo stack memory | Max 50 snapshots; each snapshot is a serialized dict |
| NFR3 | Viewport refresh latency | < 50ms for scenes with < 100 primitives |
| NFR4 | Click vs drag discrimination | < 3px movement = click (select), ≥ 3px = drag (orbit) |

---

## Assumptions

1. **The `Property` constructor currently takes positional arguments.** We add `category` as a keyword-only argument with default `"General"` — no existing callers will break.
2. **`CadSerializer.deserialize()` exists and works** for restoring documents from dicts. We will move its logic into `Document.from_dict()` for reuse.
3. **Tkinter Canvas `create_polygon`** is performant enough for scenes with < 500 filled faces. If not, we will cache polygon IDs.
4. **`uuid.uuid4()` uniqueness** is sufficient for object UIDs across snapshots.
5. **The viewport always has a camera** with valid view/projection matrices.
6. **Coordinates in the viewport** are always available on mouse move events (event.x, event.y).

---

## Architectural Drivers

Ranked by importance:

1. **Maintainability** — The GUI code is ~850 lines across 5 files. Every addition must be cleanly structured to prevent it from becoming spaghetti. We use a coordinator pattern rather than tight coupling.
2. **Backward Compatibility** — No existing API signatures change. All additions are optional parameters, new methods, or new classes. Existing scripts, commands, and serialized files must work without modification.
3. **Extensibility** — The architecture must accommodate future additions (e.g., more primitive types, custom shaders, multi-viewport layouts) without restructuring.
4. **Simplicity** — Tkinter is the target toolkit; we avoid unnecessary abstraction layers. The snapshot-based undo is deliberately simple for the initial implementation.
5. **Performance** — The viewport must remain interactive. Face fills, ray-picking, and tree search are the most performance-sensitive features.

---

## Candidate Architectures

### Option A: Central Coordinator (`CadMainWindow` as hub)

All panels receive a reference to `CadMainWindow` and call its methods directly.

- **Advantages:** Simplest to implement, no extra classes, all wiring visible in one place.
- **Disadvantages:** `CadMainWindow` becomes a god object. Tight coupling makes testing hard. Each panel needs to know about the main window's interface.
- **Complexity:** Low initially, high as features grow.
- **Risks:** God object anti-pattern; hard to maintain beyond 30 methods.
- **Maintenance Cost:** Medium-high.

### Option B: Event Bus (virtual events via Tkinter `event_generate`)

Panels communicate by generating and listening to Tkinter virtual events (`<<CADObjectSelected>>`, `<<CADDocumentModified>>`, etc.).

- **Advantages:** Loose coupling. Panels don't need references to each other. Easy to add new listeners. Tkinter-native.
- **Disadvantages:** Debugging is harder (event flow is implicit). No type safety. Events are string-based, error-prone.
- **Complexity:** Medium.
- **Risks:** Hard to trace event flows; events can be fired in wrong order.
- **Maintenance Cost:** Low-medium.

### Option C: Dedicated `SelectionCoordinator` + Tkinter Virtual Events

A lightweight `SelectionCoordinator` object that manages selection state and provides a listener registration API. Panels register callbacks. The coordinator also fires Tkinter virtual events for broadcast notifications. `CadMainWindow` owns the coordinator and passes it to panels.

- **Advantages:** Selection logic is encapsulated. Type-safe callback registration. Panels remain decoupled from each other. Tkinter events handle UI-level broadcasts (e.g., refresh all).
- **Disadvantages:** Slightly more code than Option A.
- **Complexity:** Medium.
- **Risks:** Minimal — pattern is well-understood.
- **Maintenance Cost:** Low.

### Option D: Model-View-Controller with Observer Pattern

A formal observable `Document` model with views that subscribe to change notifications.

- **Advantages:** Clean separation; the model drives all UI updates.
- **Disadvantages:** Requires significant refactoring of `Document` and all panels. Highest implementation cost. Overkill for a Tkinter app of this size.
- **Complexity:** High.
- **Risks:** High risk of breaking existing code.
- **Maintenance Cost:** Low (once implemented).

---

## Recommended Architecture

**Option C: Dedicated `SelectionCoordinator` + Tkinter Virtual Events**

**Justification:**
- Selection is the most cross-cutting concern (viewport ↔ tree ↔ property editor). A dedicated coordinator encapsulates this cleanly.
- Tkinter virtual events are used for broadcast notifications (e.g., "document changed, refresh everything") where loose coupling is beneficial.
- Panels receive only the coordinator (and their specific dependencies), not the entire `CadMainWindow`.
- The pattern is familiar and easy to implement by the engineer.
- It avoids the god-object problem of Option A while being simpler than Option D.

**Rejection of alternatives:**
- **Option A** was rejected because `CadMainWindow` would grow from ~200 lines to ~600+ lines with 40+ methods, becoming unmaintainable.
- **Option B** alone (pure events) was rejected because selection state management would still need to live somewhere, and pure events make it hard to query "what is currently selected?"
- **Option D** was rejected because it requires refactoring `Document` (the core model) which violates backward compatibility and is disproportionate effort.

---

## Component Breakdown

### 1. `SelectionCoordinator` (new role, lived in `CadMainWindow`)

**Purpose:** Single source of truth for selection state. Coordinates selection across viewport, project tree, and property editor.

**Location:** Defined as a nested class or top-level class in `cad/gui/main_window.py`, or extracted to `cad/gui/selection.py` if it grows large.

```
class SelectionCoordinator:
    def __init__(self, main_window: CadMainWindow) -> None
    def select_object(self, obj_name: str | None) -> None
    def clear_selection(self) -> None
    def get_selected(self) -> CADObject | None
    def register_listener(self, callback: Callable[[str | None], None]) -> Callable  # returns unregister
```

**Key behaviors:**
- Maintains `self._selected_name: str | None = None`
- On `select_object()`: stores the name, notifies all registered listeners.
- Listeners registered by: `CadViewportWidget`, `ProjectTreePanel`, `PropertyEditorPanel`.
- When `select_object(None)` is called, all panels clear their selection/highlight.

### 2. `CadMainWindow` (modified — `cad/gui/main_window.py`)

**Changes:**
- New attributes: `self._file_path: str | None`, `self._undo_stack: UndoRedoStack`, `self._dirty: bool`, `self._recent_files: RecentFilesManager`, `self._selection_coordinator: SelectionCoordinator`
- Layout restructured (M1.8): Row 0 = toolbar, Row 1 = main content (tree|viewport|props), Row 2 = console, Row 3 = status bar
- New internal methods: `_build_toolbar()`, `_build_status_bar()`, `_build_keyboard_shortcuts()`, `_create_primitive(type)`, `_update_title()`
- Modified methods: `_file_new`, `_file_open`, `_file_save`, `_file_save_as` now track `_file_path` and `_dirty`
- Wired to `UndoRedoStack` for all mutations

### 3. `UndoRedoStack` (new — `cad/commands/command_stack.py`)

```
class UndoRedoStack:
    def __init__(self, max_size: int = 50) -> None
    def push(self, before_snapshot: dict, after_snapshot: dict) -> None
    def undo(self) -> dict  # returns 'before' snapshot
    def redo(self) -> dict  # returns 'after' snapshot
    @property
    def can_undo(self) -> bool
    @property
    def can_redo(self) -> bool
    def clear(self) -> None
```

**Behavior:**
- Snapshots are the output of `doc.to_dict()`. Restore via `Document.from_dict()`.
- On `push()`, clears redo stack (new branch).
- On `undo()`, pops from undo stack, pushes to redo stack, returns `before` snapshot.
- On `redo()`, pops from redo stack, pushes to undo stack, returns `after` snapshot.
- Max 50 entries; oldest entries are evicted from the front.

### 4. `RecentFilesManager` (new — `cad/core/recent_files.py`)

```
class RecentFilesManager:
    def __init__(self, max_files: int = 5, config_path: str | None = None) -> None
    def add_file(self, path: str) -> None
    def remove_file(self, path: str) -> None
    def get_files(self) -> list[str]
    def clear(self) -> None
    def _load(self) -> None
    def _save(self) -> None
```

**Behavior:**
- Stores paths in `~/.config/fiona/recent.json` (or `~/.fiona/recent.json`).
- On add, inserts at front, removes duplicates, trims to max_files.
- On load, reads JSON file; if file doesn't exist, returns empty list.
- On save, writes JSON array of strings.

### 5. `CadViewportWidget` (extended — `cad/gui/viewport.py`)

**New attributes:**
- `self._selection_callback: Callable[[str], None] | None` — called when user clicks an object
- `self._selected_objects: set[str]` — names of selected objects (for highlight rendering)
- `self._drag_start: tuple[int, int] | None` — already exists, used for click vs drag
- `self._drag_threshold: int = 3` — pixels threshold for click vs drag
- `self._context_menu: tk.Menu` — right-click menu (M5.1)

**New/changed methods:**
- `set_selection(names: set[str])` — update highlighted objects
- `_on_mouse_down(event)` — modified to track position for click/drag discrimination
- `_on_mouse_up(event)` — modified: if drag < threshold, call `_on_select_click(event)`
- `_on_select_click(event)` — new: perform ray-picking, call `_selection_callback`
- `_render_object(obj)` — modified: check if obj.name is in `_selected_objects`, use highlight color + thicker lines
- `_render_box_face_fills(obj)` — new: compute visible faces, draw filled quads
- `_render_cylinder_face_fills(obj)` — new: compute visible faces, draw filled polygons
- `_render_sphere_face_fills(obj)` — new: draw filled latitude rings
- `_draw_axes_indicator()` — new: overlay XYZ triad in bottom-left corner
- `_show_context_menu(event)` — new: display right-click menu

### 6. `ProjectTreePanel` (extended — `cad/gui/project_tree.py`)

**New attributes:**
- `self._search_var: tk.StringVar` — search entry text variable
- `self._search_entry: ttk.Entry` — search/filter field above tree
- `self._context_menu: tk.Menu` — right-click menu (M5.2)
- `self._on_selection_callback: Callable[[str], None] | None` — external callback
- `self._delete_confirm_var: tk.BooleanVar` — "Don't ask again" for delete

**New/changed methods:**
- `_build_search_filter()` — create search entry, bind `<KeyRelease>` to `_filter_tree`
- `_filter_tree(*args)` — show/hide tree items based on search string
- `_show_context_menu(event)` — right-click handler
- `_on_tree_select(event)` — modified: call `_on_selection_callback` if set
- `_rename_selected()` — new: prompt for new name, rename object
- `_duplicate_selected()` — new: duplicate selected object
- `_delete_selected()` — modified: show confirmation dialog

### 7. `PropertyEditorPanel` (extended — `cad/gui/property_editor.py`)

**New attributes:**
- `self._apply_btn: ttk.Button`
- `self._reset_btn: ttk.Button`
- `self._pending_changes: dict[str, Any]` — for delayed-apply mode (optional)

**New/changed methods:**
- `show_object(obj)` — modified: render category headers, sort by category/name
- `_render_category_header(category_name, row)` — new: insert bold label + separator
- `_render_color_property(prop, prop_name, row)` — new: swatch button + color picker
- `_on_apply()` — new: commit pending changes (immediate-apply mode: already applied, this provides visual confirmation)
- `_on_reset()` — new: reset all properties to defaults
- `_clear_widgets()` — modified: also clear category headers

### 8. `Document` (extended — `cad/core/document.py`)

**New methods:**
- `from_dict(data: dict) -> Document` — classmethod to reconstruct document from serialized dict (moves logic from `CadSerializer.deserialize`)
- `is_modified(self) -> bool` — property that tracks whether document has unsaved changes

**New attributes:**
- `self._modified: bool = False` — internal dirty flag, set `True` on any object add/remove/property change
- Track modifications in `add_object()`, `remove_object()`, and via property change listener

### 9. `Property` (extended — `cad/core/property.py`)

**New parameter:**
- `category: str = "General"` — keyword-only argument in `__init__`

**Changes to `__init__` signature:**
```python
def __init__(
    self,
    name: str,
    type_: PropertyType,
    value: Any = None,
    default: Any = None,
    description: str = "",
    unit: str = "",
    readonly: bool = False,
    visible: bool = True,
    choices: list[tuple[str, Any]] | None = None,
    *,  # keyword-only after this point
    category: str = "General",
) -> None
```

**Changes to `to_dict()`:**
- Include `"category": self.category` in the output dict.

**Changes to `CADObject.add_property()`:**
- Add `category: str = "General"` keyword-only parameter, pass to `Property` constructor.
- Ensure all existing callers (Box, Cylinder, Sphere, etc.) continue to work.

### 10. `TkinterViewportBackend` (extended — `cad/rendering/viewport.py`)

**New method on `ViewportBackend`:**
```python
@abstractmethod
def draw_polygon(self, points: list[tuple[float, float]],
                 fill_color: str = "#aaaaaa",
                 outline_color: str | None = None,
                 outline_width: float = 1.0) -> None: ...
```

**Implementation in `TkinterViewportBackend`:**
```python
def draw_polygon(self, points, fill_color="#aaaaaa",
                 outline_color=None, outline_width=1.0):
    flat_coords = []
    for pt in points:
        flat_coords.extend(pt)
    kwargs = {"fill": fill_color, "outline": outline_color or fill_color}
    self.canvas.create_polygon(*flat_coords, **kwargs)
```

### 11. `RecentFilesManager` (new — `cad/core/recent_files.py`)

As specified above in component 4.

### 12. Intersection utilities (new — `cad/geometry/intersection.py`)

Pure math functions for ray-object intersection tests:

```python
def ray_aabb_intersect(ray_origin: Vector3, ray_dir: Vector3,
                       aabb_min: Vector3, aabb_max: Vector3) -> float | None:
    """Returns t (distance along ray) or None if no intersection."""

def ray_sphere_intersect(ray_origin: Vector3, ray_dir: Vector3,
                         center: Vector3, radius: float) -> float | None:
    """Returns closest positive t or None."""

def ray_cylinder_intersect(ray_origin: Vector3, ray_dir: Vector3,
                           center: Vector3, radius: float,
                           height: float) -> float | None:
    """Returns closest positive t or None. Cylinder axis is Z."""
```

---

## Interfaces

### Inter-Component Communication

```
┌──────────────────────────────────────────────────────────────────┐
│                        CadMainWindow                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                 SelectionCoordinator                      │   │
│  │  select_object(name) → notifies all registered listeners │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Toolbar  │  │ Viewport │  │  Tree    │  │ Property │       │
│  │ (Frame)  │  │ (Widget) │  │ (Panel)  │  │ (Panel)  │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│       │              │             │              │             │
│       │              │  ──────────│──────────────│             │
│       │              │  SelectionCoordinator listens            │
│       │              │  and broadcasts to all                  │
│       │              │                                          │
│  ┌──────────┐  ┌──────────┐                                    │
│  │ Console  │  │StatusBar │                                    │
│  │ (Panel)  │  │ (Frame)  │                                    │
│  └──────────┘  └──────────┘                                    │
└──────────────────────────────────────────────────────────────────┘
```

### Selection Flow

1. **User clicks in viewport →** `CadViewportWidget._on_select_click()` → ray-picking → calls `SelectionCoordinator.select_object(obj_name)`
2. **SelectionCoordinator** stores `self._selected_name = obj_name` → calls all registered listeners:
   - `ProjectTreePanel._on_external_selection(name)` → highlights item in tree
   - `PropertyEditorPanel.show_object(obj)` → loads properties
   - `CadViewportWidget.set_selection({name})` → updates highlight rendering
3. **User clicks in tree →** `ProjectTreePanel._on_tree_select()` → calls `SelectionCoordinator.select_object(name)`
4. **Coordinator** broadcasts again (same as step 2), but viewport listener skips re-selection if already selected to avoid feedback loop.

### Undo/Redo Flow

1. **Before mutation** (e.g., before changing a property, before creating an object):
   - Capture `snapshot_before = self.doc.to_dict()`
2. **Perform mutation** (existing code path)
3. **After mutation**:
   - Capture `snapshot_after = self.doc.to_dict()`
   - Call `self._undo_stack.push(snapshot_before, snapshot_after)`
   - Set `self._dirty = True`
4. **On Undo** (Ctrl+Z):
   - `before = self._undo_stack.undo()`
   - `self.doc = Document.from_dict(before)`
   - Refresh all panels: tree, viewport, property editor, status bar count
   - Set `self._dirty = True`
5. **On Redo** (Ctrl+Y):
   - `after = self._undo_stack.redo()`
   - `self.doc = Document.from_dict(after)`
   - Refresh all panels

### Communication Contracts

| Sender | Receiver | Mechanism | Payload |
|--------|----------|-----------|---------|
| Viewport (click) | SelectionCoordinator | Direct call | `obj_name: str` |
| Tree (select) | SelectionCoordinator | Direct call | `obj_name: str` |
| SelectionCoordinator | Viewport | Listener callback | `obj_name: str \| None` |
| SelectionCoordinator | Tree | Listener callback | `obj_name: str \| None` |
| SelectionCoordinator | PropEditor | Listener callback | `obj_name: str \| None` |
| Console | All panels | Virtual event `<<CADCommandExecuted>>` | None |
| Toolbar | CadMainWindow | Direct call | Primitive type string |
| Any mutation | CadMainWindow | Direct or event | None (triggers doc refresh) |

---

## Data Flow

### Selection Data Flow

```
[Viewport click] → ray-pick → obj_name
       │
       ▼
SelectionCoordinator.select_object(obj_name)
       │
       ├──► ProjectTreePanel: highlight tree item (select by name)
       ├──► PropertyEditorPanel: show_object(obj) → render property widgets
       └──► CadViewportWidget: set_selection({name}) → re-render with highlight
```

### Undo/Redo Data Flow

```
[Before any mutation]
       │
       ▼
snapshot_before = doc.to_dict()
       │
       ▼
[Execute mutation] → doc is modified
       │
       ▼
snapshot_after = doc.to_dict()
       │
       ▼
undo_stack.push(snapshot_before, snapshot_after)
       │
       ▼
[Ctrl+Z pressed]
       │
       ▼
snapshot = undo_stack.undo()  # returns 'before'
       │
       ▼
doc = Document.from_dict(snapshot)
       │
       ▼
[Refresh all panels]
```

### Property Change Data Flow

```
[User edits property value in PropertyEditorPanel]
       │
       ▼
property.value = new_value  (immediate-apply mode)
       │
       ▼
CADObject._on_property_changed() → _mark_dirty()
       │
       ▼
Document.recompute() (called from _on_float_change etc.)
       │
       ▼
CadMainWindow._dirty = True
       │
       ▼
viewport.refresh() (if needed, via recompute callback or manual trigger)
```

---

## Mouse Interaction Design

### Click vs Drag Discrimination

```
Mouse Down (ButtonPress-1):
  _drag_start = (event.x, event.y)
  _last_x, _last_y = event.x, event.y

Mouse Drag (B1-Motion):
  dx = event.x - _last_x
  dy = event.y - _last_y
  if abs(event.x - _drag_start[0]) >= 3 or abs(event.y - _drag_start[1]) >= 3:
      # It's a drag — orbit camera
      camera.orbit(-dx * 0.005, dy * 0.005)
      _last_x, _last_y = event.x, event.y
      refresh()

Mouse Up (ButtonRelease-1):
  if _drag_start is not None:
      total_dx = abs(event.x - _drag_start[0])
      total_dy = abs(event.y - _drag_start[1])
      if total_dx < 3 and total_dy < 3:
          # It's a click — perform ray-picking
          _on_select_click(event)
  _drag_start = None
```

**Important:** This maps left-click to both orbit (drag) and select (click). Middle-click and right-click remain for pan (M1.3). On macOS, use `<Button-3>` for right-click; on Linux, `<Button-2>` is middle-click and `<Button-3>` is right-click. Bind both.

### Right-click Pan (M1.3)

```python
self.canvas.bind("<ButtonPress-2>", self._on_pan_down)
self.canvas.bind("<ButtonPress-3>", self._on_pan_down)
self.canvas.bind("<B2-Motion>", self._on_pan_drag)
self.canvas.bind("<B3-Motion>", self._on_pan_drag)
```

### Scroll Zoom (existing, unchanged)

`<MouseWheel>` (Windows/macOS), `<Button-4>`/`<Button-5>` (Linux) → `camera.zoom(factor)`

---

## Rendering Design

### Face Fills with Wireframe Overlay (M2.1)

**Strategy:** Draw filled polygons first, then draw wireframe lines on top with same or contrasting color. The wireframe provides structural clarity while fills give visual weight.

**Box face fill algorithm:**
1. Compute 8 vertices of the box.
2. For each of the 6 faces (each defined by 4 vertices), compute the face normal in world space.
3. Compute the camera view direction (from camera position to face center).
4. If face normal · view direction < 0, the face is front-facing — draw it filled.
5. Use `self.backend.draw_polygon(face_points, fill_color=..., outline_color=None)`.
6. After all faces, draw wireframe edges on top with `draw_line`.

**Color selection:**
- Base color: derive from object type (Box=#2fffd3, Cylinder=#35a7ff, Sphere=#9fffe8) or from a future `color` property.
- Lighter shade for faces facing more toward the camera (dot product based).
- Darker shade for faces more perpendicular to view direction.

**Cylinder face fill algorithm:**
1. Generate top and bottom circle vertices (24 segments).
2. Compute camera view direction at center of cylinder.
3. Front-facing top face: if cam is looking down at top, draw filled polygon of top circle.
4. Front-facing bottom face: if cam is looking up at bottom, draw filled polygon of bottom circle.
5. Body strips: for each quad segment, compute its normal; if front-facing, draw filled quad.
6. Draw wireframe overlay (existing logic) on top.

**Sphere face fill algorithm:**
1. Generate latitude rings (e.g., 8 latitude divisions × 12 longitude divisions).
2. For each quad facet, compute normal at center.
3. If front-facing, draw filled quad with shade based on dot product with view direction.
4. Draw wireframe overlay (existing 3 rings) on top.

**Performance consideration:** Cache polygon/line IDs on the Canvas rather than doing `delete("all")` + full rebuild. However, initial implementation can use full rebuild — the plan flags this as a low-priority optimization (M2.4).

### Axes Indicator (M2.2)

**Strategy:** Overlay rendered last, in fixed screen-space position (bottom-left corner, 80×80 px area).

**Algorithm:**
1. After rendering the scene, compute a small coordinate frame in the bottom-left corner.
2. The origin of the indicator is at screen position (60, height - 60).
3. The axis directions are derived from the camera's view matrix:
   - X-axis = camera right vector (red)
   - Y-axis = camera up vector (green)
   - Z-axis = camera forward vector (blue, but show it pointing toward viewer)
4. For each axis, project a point 30px in that direction from the origin.
5. Draw: line from origin to projected point (colored), then a small cone/arrowhead.
6. Add text label "X", "Y", "Z" at the end of each axis.

**Implementation detail:**
```python
def _draw_axes_indicator(self):
    w = self.canvas.winfo_width()
    h = self.canvas.winfo_height()
    origin_x, origin_y = 60, h - 60
    size = 30

    # Get camera basis vectors in screen space
    cam = self.viewport.camera
    forward = (cam.target - cam.position).normalized()
    right = forward.cross(cam.up).normalized()
    up = right.cross(forward)

    axes = [
        (right, "#ff4444", "X"),
        (up, "#44ff44", "Y"),
        (forward, "#4444ff", "Z"),
    ]

    for axis_vec, color, label in axes:
        # Project axis direction to screen
        end_world = cam.target + axis_vec * size
        end_screen = self._project(end_world)
        if end_screen:
            cx, cy = origin_x, origin_y
            ex, ey = end_screen
            # We need to compute screen-space offset more carefully
            # Better: use the camera's view matrix to get the axis in screen space
```

**Alternative (simpler):** Use a hardcoded 2D overlay with lines that rotate according to the camera's azimuth/elevation angles. This avoids projecting 3D points back to 2D and is simpler to implement correctly.

### Visual Selection Highlight (M2.3)

**Strategy:** Selected objects render with:
- Fill color shifted toward yellow/orange (e.g., add `#ff8800` overlay)
- Wireframe lines drawn in bright yellow (`#ffff00`) with `width=3`
- Non-selected objects render normally

**Implementation:**
```python
def _render_object(self, obj_dict: dict, obj_name: str) -> None:
    is_selected = obj_name in self._selected_objects
    if is_selected:
        fill_color = "#ff8800"  # highlight fill
        line_color = "#ffff00"  # highlight wireframe
        line_width = 3
    else:
        fill_color = self._get_default_fill(obj_dict.get("type", ""))
        line_color = self._get_default_line(obj_dict.get("type", ""))
        line_width = 1

    # Render fills with fill_color, wireframe with line_color/line_width
```

---

## Class/Interface Skeletons

### `cad/commands/command_stack.py` (NEW)

```python
"""Undo/Redo command stack — snapshot-based undo management."""

from __future__ import annotations

from typing import Any


class UndoRedoStack:
    """A stack of document snapshots for undo/redo.

    Each entry stores a (before, after) pair of document dicts.
    Undo restores the 'before' dict. Redo restores the 'after' dict.
    """

    def __init__(self, max_size: int = 50) -> None:
        self._undo_stack: list[tuple[dict[str, Any], dict[str, Any]]] = []
        self._redo_stack: list[tuple[dict[str, Any], dict[str, Any]]] = []
        self._max_size = max_size

    def push(self, before_snapshot: dict[str, Any], after_snapshot: dict[str, Any]) -> None:
        """Record a mutation. Clears the redo stack (new branch)."""
        self._undo_stack.append((before_snapshot, after_snapshot))
        self._redo_stack.clear()
        if len(self._undo_stack) > self._max_size:
            self._undo_stack.pop(0)

    def undo(self) -> dict[str, Any]:
        """Undo last operation. Returns the 'before' snapshot to restore."""
        if not self._undo_stack:
            raise IndexError("Nothing to undo")
        entry = self._undo_stack.pop()
        self._redo_stack.append(entry)
        return entry[0]  # before snapshot

    def redo(self) -> dict[str, Any]:
        """Redo last undone operation. Returns the 'after' snapshot to restore."""
        if not self._redo_stack:
            raise IndexError("Nothing to redo")
        entry = self._redo_stack.pop()
        self._undo_stack.append(entry)
        return entry[1]  # after snapshot

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def clear(self) -> None:
        """Clear all stored snapshots (e.g., on new document)."""
        self._undo_stack.clear()
        self._redo_stack.clear()

    def __len__(self) -> int:
        return len(self._undo_stack)

    def __repr__(self) -> str:
        return f"UndoRedoStack(undo={len(self._undo_stack)}, redo={len(self._redo_stack)})"
```

### `cad/core/recent_files.py` (NEW)

```python
"""Recent files manager — persists recently-opened file paths to JSON."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class RecentFilesManager:
    """Manages a list of recently opened CAD files, persisted to ~/.config/fiona/recent.json."""

    def __init__(self, max_files: int = 5, config_path: str | None = None) -> None:
        self._max_files = max_files
        if config_path is None:
            config_dir = Path.home() / ".config" / "fiona"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = str(config_dir / "recent.json")
        self._config_path = config_path
        self._files: list[str] = []
        self._load()

    def add_file(self, path: str) -> None:
        """Add a file path to the recent list (insert at front, remove duplicates)."""
        path = os.path.abspath(path)
        if path in self._files:
            self._files.remove(path)
        self._files.insert(0, path)
        if len(self._files) > self._max_files:
            self._files = self._files[:self._max_files]
        self._save()

    def remove_file(self, path: str) -> None:
        """Remove a file path from the recent list."""
        path = os.path.abspath(path)
        if path in self._files:
            self._files.remove(path)
            self._save()

    def get_files(self) -> list[str]:
        """Return the list of recent file paths (newest first)."""
        return list(self._files)

    def clear(self) -> None:
        """Clear all recent files."""
        self._files.clear()
        self._save()

    def _load(self) -> None:
        try:
            data = Path(self._config_path).read_text(encoding="utf-8")
            self._files = json.loads(data)
        except (FileNotFoundError, json.JSONDecodeError):
            self._files = []

    def _save(self) -> None:
        Path(self._config_path).write_text(
            json.dumps(self._files, indent=2), encoding="utf-8"
        )

    def __len__(self) -> int:
        return len(self._files)

    def __getitem__(self, index: int) -> str:
        return self._files[index]

    def __repr__(self) -> str:
        return f"RecentFilesManager({len(self._files)} files)"
```

### `cad/core/document.py` — Additions

```python
class Document:
    # ... existing code ...

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Document:
        """Reconstruct a document from a serialized dictionary.

        This is the inverse of to_dict(). Used for undo/restore and loading.
        """
        doc = cls(data.get("name", "Untitled"))
        doc._metadata = dict(data.get("metadata", {}))

        # Reconstruct objects using a type registry
        from cad.geometry.primitives import Box, Cylinder, Sphere, Cone, Torus
        from cad.sketch.workspace import Sketch
        from cad.assembly.assembly import Assembly, PartInstance
        from cad.part.features import Pad, Pocket, Revolve
        # Note: extend this map as new types are added

        TYPE_MAP: dict[str, type] = {
            "Box": Box,
            "Cylinder": Cylinder,
            "Sphere": Sphere,
            "Cone": Cone,
            "Torus": Torus,
            "Sketch": Sketch,
            "Assembly": Assembly,
            "PartInstance": PartInstance,
            "Pad": Pad,
            "Pocket": Pocket,
            "Revolve": Revolve,
        }

        for obj_data in data.get("objects", []):
            obj_type = obj_data.get("type", "")
            obj_name = obj_data.get("name", "Unknown")
            cls_type = TYPE_MAP.get(obj_type)
            if cls_type is None:
                continue  # Skip unknown types

            # Create object (this calls _define_properties which sets defaults)
            obj = cls_type(obj_name)

            # Override UID if present (preserve identity across snapshots)
            if "uid" in obj_data:
                import uuid
                obj.uid = uuid.UUID(obj_data["uid"])

            # Restore properties
            for prop_name, prop_data in obj_data.get("properties", {}).items():
                prop = obj.get_property(prop_name)
                if prop is not None:
                    prop.value = prop_data.get("value", prop._default)

            # Restore dependencies
            if "dependencies" in obj_data:
                obj._dependencies = list(obj_data["dependencies"])

            doc.add_object(obj)

        return doc

    @property
    def is_modified(self) -> bool:
        """True if the document has unsaved changes."""
        return self._modified

    @is_modified.setter
    def is_modified(self, value: bool) -> None:
        self._modified = value

    # In __init__, add: self._modified = False

    # Modify add_object to set modified flag:
    def add_object(self, obj, name=None):
        # ... existing code ...
        self._modified = True
        return obj

    # Modify remove_object to set modified flag:
    def remove_object(self, obj):
        # ... existing code ...
        self._modified = True
```

**Note on `from_dict` location:** The type registry must be kept in sync. Consider extracting it to a shared constant or a module-level dict. For now, it lives inside `from_dict`.

### `cad/core/property.py` — Additions

```python
class Property:
    def __init__(
        self,
        name: str,
        type_: PropertyType,
        value: Any = None,
        default: Any = None,
        description: str = "",
        unit: str = "",
        readonly: bool = False,
        visible: bool = True,
        choices: list[tuple[str, Any]] | None = None,
        *,  # KEYWORD-ONLY from here
        category: str = "General",
    ) -> None:
        # ... existing init ...
        self.category = category

    def to_dict(self) -> dict[str, Any]:
        result = {
            # ... existing fields ...
            "category": self.category,
        }
        return result
```

### `cad/core/object.py` — Changes to `add_property`

```python
def add_property(
    self,
    name: str,
    type_: PropertyType,
    value: Any = None,
    default: Any = None,
    description: str = "",
    unit: str = "",
    readonly: bool = False,
    visible: bool = True,
    choices: list[tuple[str, Any]] | None = None,
    *,  # KEYWORD-ONLY
    category: str = "General",
) -> Property:
    prop = Property(name, type_, value, default, description, unit,
                    readonly, visible, choices, category=category)
    self._properties[name] = prop
    prop.on_change(lambda n, o, new: self._on_property_changed(n, o, new))
    return prop
```

### `cad/core/document.py` — `is_modified` wiring

Add to `__init__`:
```python
self._modified = False
```

Modify to track modifications:
```python
def add_object(self, obj, name=None):
    # ... existing code ...
    self._modified = True
    return obj

def remove_object(self, obj):
    # ... existing code ...
    self._modified = True

@property
def is_modified(self):
    return self._modified

@is_modified.setter
def is_modified(self, value):
    self._modified = value
```

To detect property changes, we need to listen for property changes on all objects. This can be done by adding a listener to each object when it's added to the document, or by implementing a simpler approach: whenever `set_property` is called on any object, the document's `_modified` flag is set. The simplest path is to add a listener in `add_object`:

```python
def add_object(self, obj, name=None):
    # ... existing code ...
    # Listen for property changes to mark document modified
    def on_prop_change(prop_name, old, new):
        self._modified = True
    # We need access to properties; iterate and attach
    for prop in obj._properties.values():
        prop.on_change(lambda n, o, new, self_ref=self: setattr(self_ref, '_modified', True))
    # But this is tricky with closures. Alternative: override CADObject to notify document.
    # Simplest: have CadMainWindow set _dirty = True when any mutation happens.
    # Since the GUI is the only entry point for mutations, this is sufficient.
```

**Decision:** Rather than adding property change listeners to the document (which adds complexity and may have side effects), we set `self._dirty = True` from `CadMainWindow` whenever any mutation occurs (object add/remove, property change via GUI). The `Document._modified` flag is set by `add_object`/`remove_object`; for property changes, the GUI sets it. We accept that programmatic mutations via the console/scripting won't set the flag — that's acceptable for the initial implementation.

### `cad/geometry/intersection.py` (NEW)

```python
"""Ray-object intersection utilities for ray-picking."""

from __future__ import annotations

import math
from typing import Any

from cad.geometry.math import Vector3


def ray_aabb_intersect(
    ray_origin: Vector3,
    ray_dir: Vector3,
    aabb_min: Vector3,
    aabb_max: Vector3,
) -> float | None:
    """Returns t (distance along ray) of closest intersection, or None.

    Uses the slab method for ray-AABB intersection.
    """
    inv_dir = Vector3(
        1.0 / ray_dir.x if abs(ray_dir.x) > 1e-15 else float('inf'),
        1.0 / ray_dir.y if abs(ray_dir.y) > 1e-15 else float('inf'),
        1.0 / ray_dir.z if abs(ray_dir.z) > 1e-15 else float('inf'),
    )

    t1 = (aabb_min.x - ray_origin.x) * inv_dir.x
    t2 = (aabb_max.x - ray_origin.x) * inv_dir.x
    t3 = (aabb_min.y - ray_origin.y) * inv_dir.y
    t4 = (aabb_max.y - ray_origin.y) * inv_dir.y
    t5 = (aabb_min.z - ray_origin.z) * inv_dir.z
    t6 = (aabb_max.z - ray_origin.z) * inv_dir.z

    tmin = max(min(t1, t2), min(t3, t4), min(t5, t6))
    tmax = min(max(t1, t2), max(t3, t4), max(t5, t6))

    if tmax < 0 or tmin > tmax:
        return None

    if tmin < 0:
        return tmax if tmax > 0 else None

    return tmin


def ray_sphere_intersect(
    ray_origin: Vector3,
    ray_dir: Vector3,
    center: Vector3,
    radius: float,
) -> float | None:
    """Returns closest positive t of ray-sphere intersection, or None."""
    oc = ray_origin - center
    a = ray_dir.dot(ray_dir)
    b = 2.0 * oc.dot(ray_dir)
    c = oc.dot(oc) - radius * radius
    disc = b * b - 4 * a * c

    if disc < 0:
        return None

    sqrt_disc = math.sqrt(disc)
    t1 = (-b - sqrt_disc) / (2.0 * a)
    t2 = (-b + sqrt_disc) / (2.0 * a)

    if t1 > 0:
        return t1
    if t2 > 0:
        return t2
    return None


def ray_cylinder_intersect(
    ray_origin: Vector3,
    ray_dir: Vector3,
    center: Vector3,
    radius: float,
    height: float,
) -> float | None:
    """Returns closest positive t of ray-infinite-cylinder intersection, then
    checks height bounds. Cylinder axis is assumed to be Z (after translating to center).
    """
    # Translate to cylinder local space
    oc = ray_origin - center

    # Solve for intersection with infinite cylinder (radius in x-y plane)
    a = ray_dir.x * ray_dir.x + ray_dir.y * ray_dir.y
    b = 2.0 * (oc.x * ray_dir.x + oc.y * ray_dir.y)
    c = oc.x * oc.x + oc.y * oc.y - radius * radius

    disc = b * b - 4 * a * c
    if disc < 0 or abs(a) < 1e-15:
        return None

    sqrt_disc = math.sqrt(disc)
    t1 = (-b - sqrt_disc) / (2.0 * a)
    t2 = (-b + sqrt_disc) / (2.0 * a)

    # Check height bounds for each t
    half_h = height / 2.0
    best_t = None

    for t in (t1, t2):
        if t < 0:
            continue
        pz = oc.z + ray_dir.z * t
        if abs(pz) <= half_h:
            if best_t is None or t < best_t:
                best_t = t

    # Check caps (top and bottom circles)
    # Bottom cap: z = -half_h
    if abs(ray_dir.z) > 1e-15:
        t_cap = (-half_h - oc.z) / ray_dir.z
        if t_cap > 0:
            px = oc.x + ray_dir.x * t_cap
            py = oc.y + ray_dir.y * t_cap
            if px * px + py * py <= radius * radius:
                if best_t is None or t_cap < best_t:
                    best_t = t_cap

        # Top cap: z = +half_h
        t_cap = (half_h - oc.z) / ray_dir.z
        if t_cap > 0:
            px = oc.x + ray_dir.x * t_cap
            py = oc.y + ray_dir.y * t_cap
            if px * px + py * py <= radius * radius:
                if best_t is None or t_cap < best_t:
                    best_t = t_cap

    return best_t
```

---

## Deployment Topology

No changes to deployment. The application remains a single-process Python desktop application launched from the command line. No new services, containers, or network dependencies.

```
┌─────────────────────────────────────────────────────────────┐
│                   Python Process                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Tkinter Application Window               │  │
│  │  ┌────────┐ ┌────────────────────┐ ┌──────────────┐  │  │
│  │  │ Toolbar │ │                    │ │  Property    │  │  │
│  │  ├────────┤ │    3D Viewport     │ │  Editor      │  │  │
│  │  │  Tree   │ │    (Canvas)       │ │              │  │  │
│  │  │  Panel  │ │                    │ │              │  │  │
│  │  ├────────┤ │                    │ │              │  │  │
│  │  │ Search  │ │                    │ │              │  │  │
│  │  └────────┘ └────────────────────┘ └──────────────┘  │  │
│  │  ┌──────────────────────────────────────────────────┐ │  │
│  │  │               Console Panel                      │ │  │
│  │  ├──────────────────────────────────────────────────┤ │  │
│  │  │               Status Bar                         │ │  │
│  │  └──────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  Filesystem:                                                │
│  - ~/.config/fiona/recent.json (recent files)               │
│  - *.cad files (document serialization)                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Technology Decisions

| Decision | Choice | Reason | Alternatives |
|----------|--------|--------|-------------|
| Undo mechanism | Snapshot-based (deep copy of `to_dict()`) | Simplest to implement correctly; works with any document state. No need for command pattern inversion. | Command pattern (more complex but more memory-efficient) |
| Selection coordination | Dedicated `SelectionCoordinator` | Encapsulates selection logic; panels stay decoupled | Pure event bus (harder to debug); God object (harder to maintain) |
| Face rendering | Tkinter `create_polygon` | No external dependencies; good enough performance for MVP | Pillow rendering to image buffer (higher quality, more complex) |
| Axes indicator | 2D overlay computed from camera angles | Simple, no 3D-to-2D reprojection issues | 3D arrow objects rendered in scene (more complex) |
| Persistence format for recent files | JSON in `~/.config/fiona/recent.json` | Standard, human-readable, no external deps | SQLite (overkill), proprietary format (bad practice) |
| Intersection tests | New `cad/geometry/intersection.py` | Keeps math.py focused on core types, intersection is a separate concern | Add to math.py (would make it too large) |
| Color property editing | `tk.colorchooser.askcolor()` | Built into Tkinter, zero dependencies | Third-party color picker (additional dependency) |

---

## Architecture Decision Records

### ADR-1: Snapshot-Based Undo

**Decision:** Use full-document snapshots (`doc.to_dict()`) for undo/redo rather than a command pattern with inverse operations.

**Context:** The current codebase has no undo infrastructure. Commands are simple functions/methods, not objects. Introducing a command pattern would require refactoring all mutation operations.

**Alternatives considered:**
1. Command pattern — each operation is an object with `execute()` and `undo()`. More memory-efficient but requires significant refactoring of existing code.
2. Memento pattern — similar to snapshots but with incremental state.

**Consequences:** Each undo entry stores two complete document dicts. For documents with 100+ objects, this is ~50-200KB per entry. With 50 entries max, worst case is ~10MB — acceptable for a desktop app. The approach is simple, correct, and can be replaced with a command pattern later if needed.

### ADR-2: SelectionCoordinator Over Pure Events

**Decision:** Create a `SelectionCoordinator` class rather than using only Tkinter virtual events for selection.

**Context:** Selection state needs to be queried ("what is selected?") and synchronized across three panels. Pure events make it hard to query state and hard to debug event ordering.

**Alternatives considered:**
1. Pure Tkinter virtual events (`<<CADObjectSelected>>`). Loose coupling but no queryable state.
2. Centralized state in `CadMainWindow` with direct method calls. Simple but creates tight coupling.

**Consequences:** Slightly more code upfront, but the coordinator can grow to manage multi-select later. Panels don't need to know about each other.

### ADR-3: Keyword-Only `category` Parameter

**Decision:** Add `category` as a keyword-only argument (after `*`) to both `Property.__init__` and `CADObject.add_property`.

**Context:** Properties currently have 9 positional parameters. Adding one more positional parameter would be fragile and error-prone for existing callers.

**Alternatives considered:**
1. Positional parameter with default — would break any caller using positional args.
2. Separate `set_category()` method — adds mutation where immutability is preferred.
3. Category lookup dictionary on CADObject — more flexible but obscures the category at definition site.

**Consequences:** All existing caller code (Box, Cylinder, Sphere, etc.) continues to work unchanged. New code can use `add_property("color", PropertyType.COLOR, "#ff0000", category="Appearance")`.

### ADR-4: Inline Type Map in `Document.from_dict`

**Decision:** Keep the type registry as an inline dict in `Document.from_dict` rather than extracting it to a global registry.

**Context:** Deserialization needs to map type name strings to Python classes. There is no global type registry in the codebase.

**Alternatives considered:**
1. Global `TYPE_REGISTRY` dict in `cad/core/object.py` — cleaner but requires maintenance discipline.
2. Metaclass-based auto-registration — elegant but over-engineered for current needs.
3. Reuse `CommandRegistry` — wrong abstraction (commands vs primitives).

**Consequences:** Every time a new primitive type is added, the `TYPE_MAP` in `from_dict` must be updated. This is a simple, visible, one-line change. We can extract to a registry later as the type system grows.

### ADR-5: Immediate-Apply Property Editor

**Decision:** Keep the current immediate-apply model (property changes take effect as soon as the user presses Enter or leaves the field), supplemented by Apply/Reset buttons that provide visual confirmation.

**Context:** The plan (M3.3) asks for Apply/Reset buttons. The current behavior applies changes immediately on field blur/Enter.

**Alternatives considered:**
1. Delayed-apply — changes are buffered until "Apply" is clicked. More standard form behavior but requires undo for each buffered change.
2. Apply button useful only as visual confirmation for properties that already auto-apply.

**Consequences:** "Apply" button is a no-op (changes already applied) or provides a visual confirmation flash. "Reset" restores all properties to defaults. This is less disruptive than changing to delayed-apply. The UI is consistent with user expectations for CAD tools (most use immediate-apply).

---

## Risk Analysis

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| **Ray-picking is inaccurate** due to Tkinter Canvas coordinate system vs 3D projection mismatch | High | Medium | Test with known camera configurations. Implement visual debug overlay showing ray direction. Start with AABB picking (simpler), add per-face picking later. |
| **Face fills slow rendering** — Tkinter `create_polygon` may be slow for many faces | Medium | Medium | Cache polygon IDs; only recreate on geometry change. Add `self._render_cache` dict mapping object IDs to canvas item IDs. If too slow, switch to `Canvas` image buffer with Pillow rendering. |
| **Undo stack via deepcopy is memory-intensive** for large documents | Low | Medium | Limit stack to 50 entries. For 100 objects, each snapshot is ~100KB. 50 snapshots = ~5MB. Acceptable. If problematic later, migrate to command pattern. |
| **Property category addition changes Property API** | Low | Medium | Add `category` as keyword-only argument with default `"General"`. No existing callers use positional args beyond the first 9. Verified by checking all `add_property` calls. |
| **Document.from_dict() is complex** — must reconstruct object graph with correct types and UIDs | Medium | High | Implement carefully with tests. Use existing serialization schema. Preserve UIDs. Add fallback for unknown types (skip gracefully). |
| **Mouse binding conflicts** between left-click orbit vs left-click select | High | Medium | Use 3px drag threshold — well-known pattern in CAD tools. Test on all supported platforms. Consider adding configurable threshold. |
| **Tkinter grid layout refactoring** breaks existing panel arrangement | Medium | Low | Keep existing panel references unchanged. Only modify the grid row/column assignments. Test by running the app after layout change. |
| **Window close protocol conflicts** with existing quit behavior | Low | Low | Only bind `WM_DELETE_WINDOW` on root. Existing `File→Exit` can bypass the check or use the same handler. |
| **Recent files JSON file corrupts** | Low | Low | Wrap `_load()` in try/except; corrupt file results in empty list. Never overwrite without valid data. |

---

## Dependency Graph (File Modification Order)

The following order ensures each file's dependencies are available before it's modified:

```
Phase 0 — No dependencies (can be done in parallel):
  A. cad/core/property.py          → Add category parameter
  B. cad/core/object.py            → Add category to add_property()
  C. cad/core/recent_files.py      → NEW: RecentFilesManager
  D. cad/commands/command_stack.py → NEW: UndoRedoStack
  E. cad/geometry/intersection.py  → NEW: Intersection utilities

Phase 1 — Depends on Phase 0:
  F. cad/core/document.py          → Add from_dict(), is_modified
                                    → Depends on: Phase 0 (property category for deserialization)

Phase 2 — Depends on Phase 1:
  G. cad/rendering/viewport.py     → Add draw_polygon() to ViewportBackend interface
                                    → Depends on: Phase 0 (none)

Phase 3 — Depends on Phase 2:
  H. cad/gui/viewport.py           → Face fills, axes indicator, ray-picking, selection highlight,
                                      context menu, click-vs-drag discrimination
                                    → Depends on: Phase 0E (intersection), Phase 2G (draw_polygon)

Phase 4 — Depends on Phase 3 and Phase 0:
  I. cad/gui/property_editor.py    → Category grouping, color property, Apply/Reset
                                    → Depends on: Phase 0A (property category)

Phase 5 — Depends on all previous phases:
  J. cad/gui/project_tree.py       → Context menu, search/filter, delete confirmation
                                    → Depends on: Phase 4I (for property integration)

Phase 6 — Depends on all previous phases:
  K. cad/gui/main_window.py        → Layout restructure, toolbar, status bar, keyboard shortcuts,
                                      undo wiring, recent files integration, SelectionCoordinator
                                    → Depends on: all phases

Phase 7 — Hardens the type map:
  L. cad/commands/builtins.py      → Add DuplicateObject command
                                    → Depends on: Phase 5J (for tree integration)
```

### Modified/New Files Summary

| File | Status | Phase |
|------|--------|-------|
| `cad/core/property.py` | MODIFY | 0 |
| `cad/core/object.py` | MODIFY | 0 |
| `cad/core/recent_files.py` | NEW | 0 |
| `cad/commands/command_stack.py` | NEW | 0 |
| `cad/geometry/intersection.py` | NEW | 0 |
| `cad/core/document.py` | MODIFY | 1 |
| `cad/rendering/viewport.py` | MODIFY | 2 |
| `cad/gui/viewport.py` | MODIFY | 3 |
| `cad/gui/property_editor.py` | MODIFY | 4 |
| `cad/gui/project_tree.py` | MODIFY | 5 |
| `cad/gui/main_window.py` | MODIFY | 6 |
| `cad/commands/builtins.py` | MODIFY | 7 |

**No changes to:** `cad/gui/console.py`

---

## Backward Compatibility Assessment

| Change | Backward Compatible? | Rationale |
|--------|---------------------|-----------|
| `Property.__init__` gains `category` kwarg | ✅ Yes | Keyword-only with default "General" |
| `CADObject.add_property` gains `category` kwarg | ✅ Yes | Keyword-only with default "General" |
| `Document.from_dict()` added | ✅ Yes | New classmethod; existing code not affected |
| `Document.is_modified` added | ✅ Yes | New property; no existing code uses it |
| `Document._modified` added | ✅ Yes | Private attribute; no external access |
| `CadSerializer.deserialize` still works | ✅ Yes | Can be updated to delegate to `Document.from_dict()` |
| `UndoRedoStack` is new class | ✅ Yes | New file; no existing code references it |
| `RecentFilesManager` is new class | ✅ Yes | New file; no existing code references it |
| `ViewportBackend.draw_polygon()` added | ✅ Yes | New abstract method; all backends must implement it. `TkinterViewportBackend` is the only backend. |
| `CadViewportWidget` new methods/attributes | ✅ Yes | All new; existing references to old API unchanged |
| `ProjectTreePanel` new methods/attributes | ✅ Yes | All new; constructor signature unchanged |
| `PropertyEditorPanel` new methods/attributes | ✅ Yes | All new; constructor signature unchanged |
| `CadMainWindow` new methods/attributes | ✅ Yes | All new; constructor signature unchanged |
| `CadMainWindow._build_layout()` grid changed | ⚠️ Test | Grid rows/columns reorganized but all child widgets still present. Must verify widget positions after change. |
| `Intersection utilities` new file | ✅ Yes | New file; no existing code references it |
| `DuplicateObject` command added | ✅ Yes | New class registered; no existing code affected |

**Key principle:** All new parameters are keyword-only with defaults. All new methods are additive. No existing method signatures change. No existing files are deleted.

---

## Future Evolution

This architecture is designed to accommodate the following future changes:

1. **Multi-select:** The `SelectionCoordinator` can evolve from `selected_name: str | None` to `selected_names: set[str]`. Listeners already receive the selection; only the type changes.

2. **Command-pattern undo:** When snapshot-based undo becomes too memory-heavy, individual commands can be extended with `undo()` methods. The `UndoRedoStack` can be refactored to store command objects instead of snapshots without changing its public API.

3. **Viewport switch to OpenGL/Pillow:** Face fills may need hardware acceleration. The `ViewportBackend` abstraction allows swapping `TkinterViewportBackend` for an `OpenGLViewportBackend` or `PillowViewportBackend` without changing rendering code.

4. **Persistent property categories:** Category definitions could be moved to a declarative schema per object type, allowing user-customizable property grouping.

5. **Improved ray-picking:** Can be extended to support per-face picking, edge picking, and snap-to-vertex.

6. **Multi-viewport layouts:** The viewport is a `tk.Frame` subclass; multiple viewport instances can be created for split-view layouts (top/front/right/perspective).

---

## Next Engineering Tasks

### Sprint 1 — Foundation (implement in order)

1. **M1.8** — Restructure layout in `main_window.py` to add rows for toolbar and status bar
2. **M1.3** — Add right-click and middle-click pan bindings to `viewport.py`
3. **M1.5** — Add `_file_path` tracking and `_update_title()` to `main_window.py`
4. **M1.1** — Build toolbar with create primitive buttons in `main_window.py`
5. **M1.2** — Build status bar with object count and coordinate display
6. **M1.4** — Add keyboard shortcut bindings to `main_window.py`
7. **M4.3** — Add delete confirmation dialog to `project_tree.py`

### Sprint 2 — Viewport + Selection

1. **Phase 0.E** — Create `cad/geometry/intersection.py` with ray-AABB, ray-sphere, ray-cylinder
2. **Phase 2.G** — Add `draw_polygon()` to `ViewportBackend` and `TkinterViewportBackend`
3. **M2.1** — Implement face fills and flat shading in `CadViewportWidget`
4. **M2.2** — Implement axes indicator overlay in `CadViewportWidget`
5. **M3.1** — Implement ray-picking and click-vs-drag discrimination
6. **M3.5** — Create `SelectionCoordinator` and wire viewport ↔ tree ↔ property editor
7. **M2.3** — Implement visual selection highlight in viewport

### Sprint 3 — Property Editor + Polish

1. **Phase 0.A, 0.B** — Add `category` to `Property` and `CADObject.add_property`
2. **M3.2** — Add category grouping and headers to `PropertyEditorPanel`
3. **M3.4** — Add color property support with color picker
4. **M3.3** — Add Apply/Reset buttons
5. **Phase 0.C** — Create `RecentFilesManager`
6. **M4.4** — Wire recent files into File menu in `main_window.py`
7. **Phase 1.F** — Add `Document.from_dict()` and `is_modified`
8. **M4.5** — Add save-on-close confirmation

### Sprint 4 — Undo + Context Menus

1. **Phase 0.D** — Create `UndoRedoStack`
2. **M4.1** — Complete undo/redo core (test with unit tests)
3. **M4.2** — Integrate undo/redo with all mutations in `main_window.py`
4. **M5.1** — Add viewport context menu
5. **M5.2** — Add project tree context menu
6. **M5.3** — Add search/filter field above tree
7. **M5.4** — Add `DuplicateObject` command and wire into context menus

---

*End of Architecture Design Document*
