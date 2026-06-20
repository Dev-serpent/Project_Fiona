# Execution Plan: Fiona CAD GUI — "Human Usable" Improvements

## Overview

This plan addresses 15 specific usability deficiencies in the Fiona CAD (ficad) Tkinter GUI. The current GUI is functional for a developer but not pleasant or productive for a human user. The plan decomposes work into 5 milestones with prioritized, dependency-aware tasks.

**Architecture Context:**
- GUI code lives in `cad/gui/` — 5 files totaling ~850 lines
- Core CAD engine in `cad/core/`, `cad/geometry/`, `cad/commands/`, etc.
- Rendering backend abstraction in `cad/rendering/`
- No undo/redo infrastructure exists (stubs only)
- No viewport selection/picking exists
- No toolbar, status bar, or axes indicator exists
- All rendering is wireframe-only via Tkinter Canvas `create_line`

**Guiding Principles:**
1. Extend existing systems rather than rewrite
2. Each change must be backward-compatible
3. Work is ordered to unblock downstream features
4. Every milestone produces a shippable improvement

---

## Milestones

| # | Milestone | Objective | Effort |
|---|-----------|-----------|--------|
| 1 | **Foundation & Core Interaction** | Immediate usability wins: toolbar, status bar, keyboard shortcuts, right-click pan, window title | 9 tasks |
| 2 | **Viewport Enhancement** | Visual quality jump: filled faces/shading, axes indicator, selection feedback | 4 tasks |
| 3 | **Object Selection & Property Editor** | Interactive 3D picking, improved property editing with apply/reset, grouping, color | 5 tasks |
| 4 | **Undo/Redo & Delete Safety** | Full undo/redo stack, delete confirmation, recent files | 5 tasks |
| 5 | **Context Menus & Tree Search** | Right-click context menus, project tree search/filter | 4 tasks |

**Total: ~27 tasks**

---

## Milestone 1: Foundation & Core Interaction

*Objective: Fix the most obvious gaps so the GUI feels immediately more professional. All tasks are independent or have minimal dependencies.*

### Tasks

| ID | Task Description | Affected Files | Dependencies | Priority | Complexity |
|----|-----------------|----------------|--------------|----------|------------|
| 1.1 | **Add toolbar with primitive creation buttons** — Create a `ttk.Frame` toolbar below the menu with icon+text buttons for Box, Cylinder, Sphere, and a separator then buttons for Recompute, Reset View, Toggle Grid. Wire buttons to existing command/registry execution or direct `_file_*` calls. Use simple Unicode/ASCII glyphs or colored rectangles as fallback icons (no external icon assets needed). | `main_window.py` | None | High | Medium |
| 1.2 | **Add status bar** — Add a `ttk.Frame` at the very bottom of the window (row 2, below console). Show: object count, cursor coordinates from viewport (update on mouse move), current mode hint. Use `ttk.Label` widgets within the status bar frame. Expose a `set_status(text)` method and a `update_coords(x, y)` method. | `main_window.py`, `viewport.py` | None | High | Medium |
| 1.3 | **Implement right-click middle-mouse pan** — Bind `<ButtonPress-2>` (middle) and `<ButtonPress-3>` (right) to pan the camera. On drag, call `self.viewport.camera.pan(dx, dy)`. Keep left-click as orbit. On Linux, `<Button-2>` is middle-click; on Windows/macOS `<Button-3>` is right-click. Use platform detection or bind both. | `viewport.py` | None | High | Simple |
| 1.4 | **Add comprehensive keyboard shortcuts** — Add bindings to `main_window.py` `__init__`: Ctrl+Z (undo), Ctrl+Y (redo), Ctrl+A (select all), Del/Delete (delete selected), Ctrl+G (toggle grid), Ctrl+R (reset view), F5 (recompute), Ctrl+N (new — already works via menu accelerator, ensure root binding). Use `<Control-Key-z>`, etc. Bind to root window. | `main_window.py`, `project_tree.py` | None | Medium | Simple |
| 1.5 | **Show file path in window title** — Track `self._file_path` in `CadMainWindow`. Update `_update_title()` to show `"CAD Platform - filename (filepath)"` for saved files, and `"CAD Platform - Untitled"` for new files. Update `_file_open()`, `_file_save()`, `_file_save_as()` to set `self._file_path`. | `main_window.py` | None | Medium | Simple |
| 1.6 | **Wire existing commands to keyboard accelerators** — The menu `accelerator` strings exist but don't actually bind keys. Ensure root-level `<Control-key>` bindings call the same handlers as the menu commands. Remove duplication between menu accelerators and keyboard bindings by making a single binding table. | `main_window.py` | 1.4 | Medium | Simple |
| 1.7 | **Add mode indicator label** — Add a small label in the viewport corner (or status bar) showing "Orbit Mode" vs "Pan Mode". When user holds Shift while dragging, switch to pan; otherwise orbit. Or simpler: always show current mouse mode. | `viewport.py`, `main_window.py` | 1.2, 1.3 | Low | Simple |
| 1.8 | **Refactor layout to accommodate toolbar and status bar** — Restructure `_build_layout()` grid. Add row 0 for toolbar, row 1 (weight=1) for the main content (tree, viewport, props), row 2 for console, row 3 for status bar. Adjust column/row weights accordingly. Use `grid_remove()` for hide/show if needed. | `main_window.py` | 1.1, 1.2 | High | Medium |
| 1.9 | **Add "Create Primitive" menu entries** — (Already partially exist via toolbar/console). Ensure the File → New Object or Tools → Create submenu has entries for Box, Cylinder, Sphere so keyboard-only users can create objects without the console. | `main_window.py` | None (can reuse toolbar callbacks) | Low | Simple |

### Milestone 1 Deliverables
- Toolbar with create buttons visible at all times
- Status bar showing object count and coordinates
- Right-click pans the viewport
- Ctrl+Z/Y/A/Del/G/R/F5 all work
- Window title shows full file path
- Layout cleanly accommodates new bars

---

## Milestone 2: Viewport Enhancement

*Objective: Make the viewport visually informative and pleasant — fill faces, show axes, highlight selections.*

### Tasks

| ID | Task Description | Affected Files | Dependencies | Priority | Complexity |
|----|-----------------|----------------|--------------|----------|------------|
| 2.1 | **Add face fills with basic shading** — Extend the `TkinterViewportBackend` with a `draw_polygon(points, fill_color, outline_color)` method. In `_render_box`, compute visible faces (front-facing via winding order or distance heuristic) and draw filled quads with a light color. For cylinders, draw filled circles for top/bottom and a filled rectangle for the body. For spheres, draw filled rings. Use simple flat shading (lighter = facing camera). Keep wireframe overlay on top of fills. | `viewport.py`, `cad/rendering/viewport.py` (backend interface) | None | High | Complex |
| 2.2 | **Add axes indicator (XYZ triad)** — In the bottom-left corner of the viewport (fixed 2D overlay), draw three arrows or lines for X (red), Y (green), Z (blue) with labels. Use the viewport camera's orientation to rotate the axes correctly. Implement as an overlay rendered after the scene in `refresh()`. Must be a fixed screen-space position (80x80 px area). | `viewport.py` | None | High | Medium |
| 2.3 | **Add visual selection feedback in viewport** — Highlight selected objects with a different color (e.g., bright yellow/orange) and/or thicker lines. Store `self._selected_objects` set in `CadViewportWidget`. When rendering, check if the object is selected and use highlight color + increased line width. Clear highlights when selection changes. This requires wiring selection state from `CadMainWindow` selection into viewport. | `viewport.py`, `main_window.py` | 1.8 (for callback wiring), 3.1 (viewport selection) or tree selection | High | Medium |
| 2.4 | **Add viewport performance optimization** — Cache the scene object list and only re-build when document changes. Avoid full `canvas.delete("all")` + redraw on every mouse move. Use `Canvas` item IDs to update transforms instead. Or, as a simpler first step: debounce `refresh()` calls using `after()` to coalesce rapid mouse events. | `viewport.py` | None | Low | Medium |

### Milestone 2 Deliverables
- Primitives render with filled faces (colored, flat-shaded)
- XYZ axes indicator visible in viewport corner
- Selected objects glow/highlight
- Viewport redraws are smoother

---

## Milestone 3: Object Selection & Property Editor

*Objective: Make objects clickable in 3D and improve the property editing experience.*

### Tasks

| ID | Task Description | Affected Files | Dependencies | Priority | Complexity |
|----|-----------------|----------------|--------------|----------|------------|
| 3.1 | **Implement viewport ray-picking for object selection** — When the user clicks (button-1 without drag, i.e., short click) in the viewport, cast a ray from the click position through the scene using the camera's inverse view-projection matrix. For each scene object, test intersection with the ray (AABB for boxes, sphere for spheres, cylinder-ray test for cylinders). Select the closest object. Emit a callback to `main_window` to update the property editor and project tree. Distinguish click vs drag by checking if mouse moved < 3px between press and release. | `viewport.py`, `main_window.py`, `cad/geometry/` (add ray-intersection utilities) | 1.3 (mouse handling) | High | Complex |
| 3.2 | **Add visual grouping and category headers to property editor** — Group properties by logical category (e.g., "Position", "Dimensions", "Appearance"). Add `category` attribute to `Property` class (default `"General"`). In `PropertyEditorPanel.show_object()`, render group headers as `ttk.Label` with bold+underline or `ttk.Separator`. Sort properties by category then name. | `property_editor.py`, `cad/core/property.py` | None | Medium | Medium |
| 3.3 | **Add Apply/Reset buttons to property editor** — Add a button bar at the bottom of `PropertyEditorPanel` with "Apply" and "Reset" buttons. "Apply" commits pending changes (if using a delayed-apply model). "Reset" restores all properties to their default values. Keep immediate-apply (current behavior) as default but add visual confirmation. | `property_editor.py` | None | Medium | Simple |
| 3.4 | **Add color property support to property editor** — Support `PropertyType.COLOR` in the editor. Show a colored swatch button that opens a `tk.colorchooser.askcolor()` dialog. Display the hex value next to the swatch. Store the color string `"#rrggbb"` back to the property. | `property_editor.py` | 3.2 (for "Appearance" category) | Medium | Simple |
| 3.5 | **Wire viewport selection to tree and property editor** — Ensure that clicking an object in the viewport (Task 3.1) highlights it in the project tree and loads its properties in the property editor. Conversely, clicking in the project tree highlights the object in the viewport. Create a centralized selection manager or event bus in `CadMainWindow` to coordinate this. | `main_window.py`, `viewport.py`, `project_tree.py`, `property_editor.py` | 3.1, 2.3, 1.8 | High | Medium |

### Milestone 3 Deliverables
- Click any 3D object to select it
- Selection is reflected in tree, viewport, and property editor
- Properties are grouped under category headers
- Color properties can be edited with a color picker
- Apply/Reset buttons work

---

## Milestone 4: Undo/Redo & Delete Safety

*Objective: Make operations safe and reversible.*

### Tasks

| ID | Task Description | Affected Files | Dependencies | Priority | Complexity |
|----|-----------------|----------------|--------------|----------|------------|
| 4.1 | **Build undo/redo command stack** — Create `UndoRedoStack` class in `cad/commands/` (new file `command_stack.py` or within `registry.py`). Each entry stores a snapshot (deep copy) of the document state before and after the command, or a command/rollback pair. Implement `push(snapshot_before, snapshot_after)`, `undo()` → restore previous snapshot, `redo()` → restore next snapshot. Limit stack depth to 50. Use `copy.deepcopy` on the document's `to_dict()` for simplicity initially. | `cad/commands/command_stack.py` (new), `cad/core/document.py` (add `from_dict` classmethod for restore) | None | High | Complex |
| 4.2 | **Integrate undo/redo with all mutation operations** — Wrap every operation that modifies the document (create object, delete object, property change) with a snapshot before/after. In `CadMainWindow`, modify `_file_new`, `_file_open`, primitives creation (toolbar), delete, and property change to push to the UndoRedoStack. Wire `_undo` and `_redo` callbacks to the stack. | `main_window.py`, `project_tree.py`, `property_editor.py`, `viewport.py` | 4.1 | High | Medium |
| 4.3 | **Add delete confirmation dialog** — Before `_delete_selected()` removes an object, show `messagebox.askyesno("Confirm Delete", f"Delete '{obj_name}'?\nThis cannot be undone.")`. Only delete if user clicks Yes. Provide a "Don't ask again" checkbox (store in `self.root` boolean attribute). | `project_tree.py`, `main_window.py` | None | Medium | Simple |
| 4.4 | **Add recent files list** — Store recent file paths in `tkinter`'s `tk.StringVar` list or a simple JSON file at `~/.config/fiona/recent.json`. Show last 5 files in File menu with numbered shortcuts (Ctrl+1 through Ctrl+5). Update on file open/save. Load on startup. | `main_window.py`, `cad/core/recent_files.py` (new) | None | Medium | Medium |
| 4.5 | **Add "Save on close" confirmation** — Bind `WM_DELETE_WINDOW` protocol on the root window. If the document has unsaved changes (track a `self._dirty` flag), show messagebox with Save/Discard/Cancel. Track dirty state via document property changes and object add/remove. | `main_window.py`, `cad/core/document.py` (add `is_modified` property) | None | Medium | Medium |

### Milestone 4 Deliverables
- Ctrl+Z undoes the last operation, Ctrl+Y redoes
- Property changes, object creation/deletion are all undoable
- Delete asks "Are you sure?"
- File menu shows recent files
- Closing with unsaved changes prompts to save

---

## Milestone 5: Context Menus & Tree Search

*Objective: Add power-user conveniences for rapid workflow.*

### Tasks

| ID | Task Description | Affected Files | Dependencies | Priority | Complexity |
|----|-----------------|----------------|--------------|----------|------------|
| 5.1 | **Add context menu to viewport** — Create a `tk.Menu` that pops up on right-click (or control-click on macOS) in the viewport. Include: Select All, Delete Selected, Duplicate, Reset View, Toggle Grid. Wire to existing callbacks. Show only if an object is selected (for Delete/Duplicate). Show a separator then "Create Box", "Create Cylinder", "Create Sphere". | `viewport.py`, `main_window.py` | 1.3 (mouse events), 3.1 (selection) | Medium | Medium |
| 5.2 | **Add context menu to project tree** — Right-click on a tree item shows menu: Rename, Delete, Duplicate, Copy, Properties. Use `tk.Menu` with `post()` at mouse position. Wire rename to an inline edit or simple dialog. Duplicate creates a copy with incremented name. | `project_tree.py`, `main_window.py` | None | Medium | Medium |
| 5.3 | **Add search/filter field above project tree** — Add a `ttk.Entry` between the "Project Tree" label and the tree widget. As the user types, filter visible tree items to those whose name or type matches the search string (case-insensitive). Use `tree.insert`/`tree.delete` or `tree.reattach` to show/hide items. Clear filter on Escape key. | `project_tree.py` | None | Medium | Medium |
| 5.4 | **Add object duplication command** — Implement a Duplicate action that deep-copies an object, adds it to the document with a new unique name (append "_001", "_002", etc.), places it at offset (x+10, y+10, z+0). Wire into context menus (5.1, 5.2) and add as a toolbar button. | `cad/commands/builtins.py` (new `DuplicateObject` command), `project_tree.py`, `viewport.py`, `main_window.py` | 5.1, 5.2 for wiring | Low | Medium |

### Milestone 5 Deliverables
- Right-click in viewport shows creation/selection context menu
- Right-click in tree shows rename/delete/duplicate menu
- Search box filters the project tree in real-time
- Objects can be duplicated from context menus

---

## Dependencies and Blockers

### Task Dependency Graph (simplified)

```
M1.1 (toolbar) ──┐
M1.2 (status) ───┤
M1.3 (rclick pan)┤
M1.4 (keys) ─────┤
M1.5 (title) ────┤
M1.9 (menu) ─────┤
                 ├──> M1.8 (layout refactor)
M1.6 (accelerators) ─── depends on M1.4
M1.7 (mode label) ───── depends on M1.2, M1.3
                 │
M2.1 (fills) ────┼── (independent)
M2.2 (axes) ─────┼── (independent)
M2.4 (perf) ─────┘── (independent)
                 │
M2.3 (sel feedback) ── depends on 3.5 (selection wiring) OR tree selection
M3.1 (ray-pick) ───── depends on M1.3 (mouse handler split)
M3.5 (wiring) ─────── depends on M3.1, M2.3
M3.2 (grouping) ───── (independent)
M3.3 (apply/reset) ── (independent)
M3.4 (color) ──────── depends on M3.2 (for category)
                 │
M4.1 (undo stack) ─── (independent core work)
M4.2 (integrate undo) depends on M4.1, M1.1 (toolbar creates), M3.1 (selection creates)
M4.3 (delete confirm) ─ (independent)
M4.4 (recent files) ─── (independent)
M4.5 (save confirm) ─── (independent)
                 │
M5.1 (context viewport) ─ depends on M1.3, M3.1
M5.2 (context tree) ───── (independent of selection, but richer with it)
M5.3 (filter tree) ────── (independent)
M5.4 (duplicate) ──────── depends on M5.1, M5.2 for wiring
```

### External / Cross-Cutting Blocker

- **Ray-picking (3.1)** requires adding ray-AABB and ray-cylinder intersection tests to `cad/geometry/math.py` or a new `cad/geometry/intersection.py`. These are pure math functions with no other dependencies.
- **Undo stack (4.1)** requires `Document.from_dict()` — a method to reconstruct a Document from a dictionary. This does not exist yet; `to_dict()` does. This is straightforward but must be added to `cad/core/document.py`.

---

## Prioritization Rationale

**High Priority (Must have for MVP):**
- **Toolbar (1.1)** — Directly addresses the #1 complaint; high visibility, high value.
- **Status bar (1.2)** — Essential for spatial awareness; every professional CAD has one.
- **Right-click pan (1.3)** — Standard 3D navigation; without it the viewport feels broken.
- **Layout refactor (1.8)** — Blocking dependency for toolbar and status bar placement.
- **Face fills (2.1)** — Wireframe-only is the #5 complaint; visual quality matters most.
- **Axes indicator (2.2)** — Without it, orientation is confusing.
- **Selection feedback (2.3)** — Without it, you can't tell what's selected.
- **Ray-picking (3.1)** — Core interaction model; unlocks context menus, selection, highlight.
- **Selection wiring (3.5)** — Makes the whole app feel cohesive.
- **Undo stack (4.1 & 4.2)** — Safety net; users expect to undo mistakes.

**Medium Priority (Should have soon):**
- Keyboard shortcuts (1.4) — Power users need them.
- Property grouping (3.2) — Readability improvement.
- Apply/Reset (3.3) — Standard form pattern.
- Color picker (3.4) — Needed for visual differentiation.
- Delete confirmation (4.3) — Safety.
- Recent files (4.4) — Workflow efficiency.
- Save-on-close (4.5) — Safety.
- Window title (1.5) — Quick fix, low effort.
- Search/filter tree (5.3) — Scales to large documents.

**Low Priority (Nice to have):**
- Mode indicator (1.7) — Polish.
- Context menus (5.1, 5.2) — Convenience.
- Duplicate (5.4) — Convenience.
- Performance optimization (2.4) — Not yet a bottleneck.
- Create primitive menu (1.9) — Redundant with toolbar.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Ray-picking is inaccurate** due to Tkinter Canvas coordinate system vs 3D projection mismatch | Medium | High | Test with known camera configurations; implement visual debug overlay showing ray. Start with AABB picking (simpler), add per-face picking later. |
| **Face fills significantly slow rendering** — Tkinter Canvas `create_polygon` may be slow for many faces | Medium | Medium | Cache polygon IDs; only recreate on geometry change. Add `self._render_cache` dict. If Tkinter is too slow, consider switching viewport to `tkinter.Canvas` image buffer with Pillow rendering. |
| **Undo stack via deepcopy is memory-intensive** for large documents | Medium | Medium | Limit stack to 50 entries; use command-pattern (record inverse operations) instead of snapshot for phase 2. Phase 1 deepcopy is acceptable for prototyping. |
| **Property category addition changes Property API** — downstream code uses positional args | Medium | Low | Add `category="General"` as keyword-only argument with default. No existing callers will break. |
| **Document.from_dict() is complex** — must reconstruct object graph with correct types and UIDs | Low | High | Implement carefully with tests. Use the existing serialization schema. Ensure UIDs are preserved so dependency references remain valid. |
| **Mouse binding conflicts** between left-click orbit vs left-click select | Medium | High | Distinguish click vs drag by measuring pixel distance between press and release. <3px = select, >=3px = orbit. This is a well-known pattern in CAD tools. |

---

## Effort Summary

| Milestone | Simple | Medium | Complex | Total Tasks | Estimated Person-Days |
|-----------|--------|--------|---------|-------------|----------------------|
| M1: Foundation & Core Interaction | 3 | 5 | 0 | 8 | 5–7 |
| M2: Viewport Enhancement | 0 | 2 | 1 | 3 | 6–8 |
| M3: Selection & Property Editor | 2 | 1 | 2 | 5 | 7–10 |
| M4: Undo/Redo & Delete Safety | 1 | 2 | 2 | 5 | 6–9 |
| M5: Context Menus & Tree Search | 0 | 3 | 0 | 4 | 3–4 |
| **Total** | **6** | **13** | **5** | **25** | **27–38** |

**Estimation scale:** Simple = 0.5 day, Medium = 1–2 days, Complex = 3–5 days.

---

## Suggested Implementation Order (Recommended Sprint Plan)

### Sprint 1 (Foundation)
1. M1.8 Layout refactor (must come first to avoid rework)
2. M1.3 Right-click pan (low effort, high value)
3. M1.5 Window title path
4. M1.1 Toolbar (create primitives)
5. M1.2 Status bar
6. M1.4 Keyboard shortcuts
7. M4.3 Delete confirmation (quick safe win)

### Sprint 2 (Viewport + Selection)
1. M2.1 Face fills and shading
2. M2.2 Axes indicator
3. M3.1 Ray-picking infrastructure
4. M3.5 Selection wiring
5. M2.3 Selection highlight in viewport

### Sprint 3 (Property Editor + Polish)
1. M3.2 Property grouping with categories
2. M3.3 Apply/Reset buttons
3. M3.4 Color property support
4. M4.4 Recent files
4. M4.5 Save-on-close confirmation

### Sprint 4 (Undo + Context Menus)
1. M4.1 Undo/Redo stack (core)
2. M4.2 Integration of undo with all mutations
3. M5.1 Viewport context menu
4. M5.2 Tree context menu
5. M5.3 Tree search/filter
6. M5.4 Duplicate command

---

## Files Modified Summary

| File | Milestones | Nature of Changes |
|------|-----------|-------------------|
| `cad/gui/main_window.py` | M1, M3, M4, M5 | Layout restructure, toolbar, status bar, keyboard bindings, undo wiring, recent files, selection coordinator |
| `cad/gui/viewport.py` | M1, M2, M3, M5 | Mouse handler split (click vs drag), face rendering, axes indicator, ray-picking, selection highlight, context menu |
| `cad/gui/project_tree.py` | M3, M4, M5 | Delete confirmation, context menu, search/filter entry |
| `cad/gui/property_editor.py` | M3 | Category headers, Apply/Reset buttons, color picker |
| `cad/gui/console.py` | None | No changes expected |
| `cad/core/document.py` | M4 | `from_dict()`, `is_modified` property |
| `cad/core/property.py` | M3 | `category` attribute |
| `cad/commands/command_stack.py` (new) | M4 | Undo/Redo stack class |
| `cad/commands/builtins.py` | M5 | DuplicateObject command |
| `cad/geometry/math.py` | M3 | Ray-AABB, ray-sphere, ray-cylinder intersection functions |
| `cad/rendering/viewport.py` | M2 | Backend interface may need `draw_polygon` method |
| `cad/core/recent_files.py` (new) | M4 | JSON-based recent files persistence |

---

## Appendix: Detailed Task Specifications

### M1.1 — Toolbar Implementation Notes
- Location: Below the menubar, full-width across the window
- Style: `ttk.Frame` with `ttk.Button` children, relief `tk.RAISED` or flat
- Buttons needed:
  - □ Box (calls `self._create_primitive("Box")` )
  - ◎ Cylinder (calls `self._create_primitive("Cylinder")` )
  - ◯ Sphere (calls `self._create_primitive("Sphere")` )
  - Separator (ttk.Separator)
  - ⟳ Recompute (calls `_recompute`)
  - ⊞ Reset View (calls `_reset_view`)
  - ⊞ Toggle Grid (calls `_toggle_grid`)
- New method `_create_primitive(primitive_type)` that creates using `self.registry.execute(f"create_{primitive_type.lower()}", ...)` with default dimensions
- After creation: refresh tree, viewport, status bar count

### M3.1 — Ray-Picking Detailed Algorithm
1. On mouse release, if total drag distance < 3px, trigger selection
2. Convert screen (x, y) to NDC: `ndc_x = (2 * x / w) - 1`, `ndc_y = 1 - (2 * y / h)`
3. Get inverse of (projection × view) matrix
4. Transform NDC point to get ray origin and direction in world space
5. For each object in scene:
   - Box: ray-AABB intersection test
   - Sphere: ray-sphere intersection test
   - Cylinder: ray-cylinder intersection test
6. Return closest object with intersection distance > 0
7. Emit `_on_select_object(obj_name)` to main window callback

### M4.1 — Undo/Redo Stack Design
```python
class UndoRedoStack:
    def __init__(self, max_size=50):
        self._undo_stack = []
        self._redo_stack = []
        self._max_size = max_size
    
    def push(self, before_snapshot: dict, after_snapshot: dict) -> None:
        self._undo_stack.append((before_snapshot, after_snapshot))
        self._redo_stack.clear()
        if len(self._undo_stack) > self._max_size:
            self._undo_stack.pop(0)
    
    def undo(self) -> dict:
        # Returns the 'before' snapshot to restore
        entry = self._undo_stack.pop()
        self._redo_stack.append(entry)
        return entry[0]  # before
    
    def redo(self) -> dict:
        entry = self._redo_stack.pop()
        self._undo_stack.append(entry)
        return entry[1]  # after
    
    @property
    def can_undo(self) -> bool: return len(self._undo_stack) > 0
    
    @property
    def can_redo(self) -> bool: return len(self._redo_stack) > 0
```

Snapshots are document dictionaries from `doc.to_dict()`. Restore via `Document.from_dict()`.

---

*End of Plan*
