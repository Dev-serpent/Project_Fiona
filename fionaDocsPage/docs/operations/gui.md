# GUI Mechanics

Fiona currently has one shared configuration GUI plus three standalone application GUIs.

## Shared Fiona GUI

Open it with:

```bash
fiona edit
```

or:

```bash
python3 -m fiona.cli edit
```

The shared GUI is implemented by `QuikTieper.gui.ConfigEditorApp`. It is a Tkinter `ttk.Notebook` application with this tab order:

```text
CamComs -> Vsee -> Bindings -> Raw Json -> Debug -> Host -> Pairing -> Voice
```

The footer contains:

- listener status indicator
- current config/status message
- `Start Listener` / stop listener control
- `Save All`
- `Minimize to tray` checkbox (when checked, closing hides to tray instead of quitting)

### System Tray

When `Minimize to tray` is checked, closing the window hides it to the system tray instead of destroying it. The system tray icon shows a color-coded status indicator:

- **Green**: service running and listening
- **Yellow**: service running but not listening
- **Red**: service not running

Right-click the tray icon to show or quit Fiona. The tray icon can also be started standalone:

```bash
fiona --tray-only
```

The tray state is refreshed every 5 seconds, showing service status, listening state, paired device count, and active macro name.

## CamComs Tab

Purpose: operate the encryption layer without leaving the GUI.

Operational areas:

- identity/key generation
- public key export
- plaintext/instruction input
- envelope encryption/decryption
- encoded send helpers
- smoke test output

### Key Management (new)

The CamComs tab now includes a **Key Management** section:

- **Current Fingerprint**: read-only display of the host identity's public key fingerprint
- **Rotate Keys** button: generates a new identity with confirmation dialog
- **Prune Expired Trust** button: removes expired trusted sender entries
- **Trust Store Location**: read-only path display (`~/.config/fiona/trusted/`)

Data flow:

```text
GUI fields -> CamComs identity/public bundle loaders -> encrypt_message/decrypt_text -> output text widget
```

The smoke-test handler creates in-memory sender/recipient identities, encrypts an `alt+s` press instruction, decrypts it, and writes the decoded JSON instruction to the output box. It does not require persistent key files.

## Vsee Tab

Purpose: edit and render 3D point/edge wireframes inside the shared GUI.

The tab holds:

- point table text
- edge table text
- validation/render controls
- canvas projection area
- rotation and scale controls

Data flow:

```text
points CSV + edges CSV -> HologramModel.from_text -> validation -> projected canvas coordinates -> Tk canvas render
```

Validation catches duplicate point ids and edges that reference missing points before rendering.

## Bindings Tab

Purpose: manage the QuikTieper binding model.

Main elements:

- left tree of apps, launch bindings, and shortcuts
- app metadata fields
- binding fields for name, keys, command, instruction, Fiona commands, and cooldown
- add app, add shortcut, delete, save selected
- mouse-position capture helper

Operational model:

```text
bindings.json -> load_config -> parse tree index -> edit selected item -> save_config
```

The listener uses the same config file, so saved GUI changes alter what `fiona run` will execute.

## Raw Json Tab

Purpose: expose the underlying QuikTieper JSON config directly.

Controls:

- reload from disk
- validate JSON
- save through `Save All`

Use this tab for structural edits that are faster in JSON than in the form editor. Invalid JSON is rejected before save.

## Debug Tab

Purpose: project-restricted text/code editor for development.

Allowed directories:

```text
tests/
scripts/
QuikTieper/
CamComs/
```

Skipped directories:

```text
__pycache__/
.pytest_cache/
```

Allowed file types include Python, Markdown, JSON, shell scripts, TOML, YAML, HTML, CSS, INI, CFG, TXT, and ESP32 `.ino` files.

Security boundary:

- it does not expose the whole filesystem
- it does not expose every project directory
- it validates resolved paths before saving
- it rejects files outside the configured debug roots

## Host Tab

Purpose: inspect and operate host-service state from the GUI.

Typical capabilities:

- initialize config
- show host status
- inspect key/trust paths
- list/remove trusted sender keys
- inspect audit log
- expose host receiver configuration
- **live systemd service state** (color-coded status dot, 3s polling)
- **Start/Stop/Restart/Journal** buttons (invoke `systemctl --user`)
- **scrollable journalctl output** display
- **SeeOnDesk info panel**: current workspace name, top processes, refresh button

Operational model:

```text
Host tab action -> HostService/load config/AuditLog/trust helpers -> rendered status/log text
```

## Pairing Tab (new)

Purpose: pair ESP32 and other devices with Fiona using the pairing protocol.

**Device Pairing** section:

- **Listen for Pairing Requests** toggle: starts/stops the pairing HTTP server on port 8090
- Status label showing "Listening" or "Stopped"

**Pending Requests** section:

- Treeview: Device ID, Fingerprint, Received At, Expires In
- **Approve** / **Deny** buttons
- Expires in (days) spinbox (default 30, 0 = no expiry)
- Polls every 2 seconds

**Trusted Devices** section:

- Treeview: Device ID, Fingerprint, Added At, Expires, Status
- Status shows "OK (expires in N days)", "EXPIRED" (red), or "Never"
- **Remove** button with confirmation dialog
- **Refresh** button
- Auto-poll every 10 seconds

## Voice Tab (new)

Purpose: control voice features from the GUI.

**Voice Control** section:

- Wake word engine status (Available / Unavailable)
- Start/Stop listening toggle
- Wake word text entry (default "fiona")
- Manual trigger button ("Hey Fiona")

**Feedback** section:

- Test sound buttons (Ack, Error, Success)
- Test Notification button
- Urgency selector (low / normal / critical)

**Push to Talk** section:

- Status indicator (Available / Unavailable)
- Hotkey display (Ctrl+Space)
- Start/Stop listener toggle

## Standalone Vsee

Open:

```bash
fiona vsee
```

The standalone Vsee window focuses only on holography data and rendering. It accepts optional `--points` and `--edges` files from the CLI and does not include the QuikTieper/CamComs configuration surface.

## Standalone PhiConnect

Open:

```bash
fiona phiconnect
```

PhiConnect is an encrypted chat application.

GUI mechanics:

- ensures a local identity exists
- shows local public key for sharing
- accepts/trusts a peer public key
- starts a local receiver on host/port
- encrypts outgoing chat with the peer public key
- decrypts incoming chat with the local private key
- shows recent chat messages from a rolling 3-minute window

Local test path:

```text
Use Local Public Key -> Start Receiver -> send to 127.0.0.1:5000
```

The PhiConnect GUI now includes trust expiry checking and an optional Agent bridge checkbox for forwarding chat messages to the local Ollama agent.

## Standalone DataClient

Open:

```bash
fiona dataclient
```

GUI areas:

- Research tab for quick and deep mining
- MiniExcel tab for CSV/JSON/SQLite table viewing/editing
- Miner menu for quick access to mining actions

Research flow:

```text
topic -> search -> scrape pages -> summarize text -> row model -> CSV export
```

MiniExcel flow:

```text
table file -> load_table -> grid rows/columns -> edit/formula/export -> save converted table
```

The formula bar evaluates only a safe expression subset: cell references, ranges, arithmetic, and a controlled function list.
