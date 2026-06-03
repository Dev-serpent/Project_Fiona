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
CamComs -> Vsee -> Bindings -> Raw Json -> Debug -> Host
```

The footer contains:

- listener status
- current config/status message
- `Start Listener` / stop listener control
- `Save All`

## CamComs Tab

Purpose: operate the encryption layer without leaving the GUI.

Operational areas:

- identity/key generation
- public key export
- plaintext/instruction input
- envelope encryption/decryption
- encoded send helpers
- smoke test output

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
- list trusted sender keys
- remove trusted sender keys
- inspect audit log
- expose host receiver configuration

Operational model:

```text
Host tab action -> HostService/load config/AuditLog/trust helpers -> rendered status/log text
```

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
