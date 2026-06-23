# SeeOnDesk

SeeOnDesk is Fiona's first desktop-awareness subsystem. It identifies the active app/window from desktop metadata.

Screen capture is implemented. Visual recognition via an ML classifier is not yet integrated.

## Commands

Show the currently focused app/window:

```bash
python3 -m fiona.cli seeondesk active
```

Show a fuller desktop-awareness snapshot:

```bash
python3 -m fiona.cli seeondesk status
```

Installed-command equivalents:

```bash
fiona seeondesk active
fiona seeondesk status
```

## Detection Backends

SeeOnDesk currently:

- prefers `kdotool` for KDE/Wayland active-window detection
- falls back to `xdotool` and `xprop` on X11-compatible sessions
- reports `backend: unavailable` when it cannot access the desktop session

## Output

Depending on the backend and session permissions, output can include:

- success/failure state
- backend used
- active window id
- app class
- inferred app name
- window title
- process id
- process name
- session type
- current desktop name

## Process Tracking

ProcessTracker iterates `/proc/*/comm` to find processes by name substring, with no `psutil` dependency required. It registers and triggers watcher callbacks when matching processes are detected.

```bash
fiona seeondesk status  # includes process tracking output
```

## Workspace Awareness

WorkspaceWatcher polls workspace state via `kdotool` (with `wmctrl` fallback), detects active workspace changes, fires change callbacks, and tracks the current workspace ID.

## Action Discovery

Discover available actions from system state:

```bash
fiona --discover-actions
```

Prints a categorized list of actions grouped by process, workspace, and window context, with action name, description, and confirmation requirements.

## Screen Capture

The `vision.py` module captures the full screen or a specific window to disk. It prioritizes KDE's `spectacle` on Wayland, falls back to `grim` for generic Wayland, and uses `scrot` or `gnome-screenshot` on X11. Screen captures are used by the Agent's `seeondesk_analyze` action for vision-based QA via the local Ollama model.

```python
from SeeOnDesk.vision import capture_screen, capture_window, analyze_screen

capture_screen("/tmp/screenshot.png")
analyze_screen("What application is visible?")
```

## Remaining Work

SeeOnDesk is the base for richer context:

- ML classifier for visual recognition
- app-specific action contexts
- agent integration
