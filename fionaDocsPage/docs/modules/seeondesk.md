# SeeOnDesk

SeeOnDesk is Fiona's first desktop-awareness subsystem. It identifies the active app/window from desktop metadata.

It does not yet train or run a screen-recording machine-learning model.

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

## Future Direction

SeeOnDesk is the base for richer context:

- screen capture
- visual recognition
- workspace/session state
- app-specific available actions
- command context for the future Fiona agent
