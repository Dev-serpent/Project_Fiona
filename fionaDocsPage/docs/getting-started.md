# Getting Started

Fiona can be run directly from a source checkout:

```bash
cd Fiona
python3 -m fiona.cli <command>
```

Examples:

```bash
python3 -m fiona.cli edit
python3 -m fiona.cli list
python3 -m fiona.cli camcoms smoke-test
python3 -m fiona.cli phiconnect
python3 -m fiona.cli dataclient
```

If the console script is installed and on `PATH`, use:

```bash
fiona <command>
```

## Shared GUI

Open the shared Fiona GUI:

```bash
python3 -m fiona.cli edit
```

Panel order:

```text
CamComs -> Vsee -> Bindings -> Raw Json -> Debug -> Host
```

Panel roles:

- `CamComs`: generate identities, export public keys, encrypt/decrypt messages, send encoded envelopes, and run a local smoke test.
- `Vsee`: edit 3D points and edges and render connected wireframe shapes.
- `Bindings`: edit QuikTieper app launchers and shortcut bindings.
- `Raw Json`: edit the QuikTieper config directly.
- `Debug`: restricted project file editor for `tests`, `scripts`, `QuikTieper`, and `CamComs`.
- `Host`: inspect host config, trusted devices, key paths, and audit logs.

## Web Dashboard

The `fionaLocalPages/` directory provides a modern single-page application (SPA) web frontend for Fiona. It is built with vanilla JavaScript and uses the aiohttp Python library for the backend server.

Start the web dashboard:

```bash
python3 fionaLocalPages/server/app.py
```

The dashboard is then available at:

```
http://localhost:8765
```

What the web dashboard provides:

- **Agent Chat**: conversational interface with streaming responses, personality selection, and multi-session management.
- **Action Runner**: list, search, filter, and execute Fiona actions with permission profiles and dry-run support.
- **Settings**: configure ACL rules, shell safety, voice engine, macros, and general preferences.
- **Browser Automation**: start/stop the Playwright engine, navigate, click, type, and capture screenshots.
- **File Explorer**: browse, read, write, and inspect files on the local filesystem.
- **Terminal**: execute shell commands and view the fAT system dashboard status.
- **Performance Monitoring**: real-time CPU, memory, disk, network, and system metrics with live gauge widgets.
- **Real-Time Updates**: WebSocket and SSE (Server-Sent Events) for live streaming of agent responses, system metrics, and event notifications.
- **RecallVault**: search, store, and manage categorized remembrance entries.
- **Desktop Awareness**: view active window and screen snapshot information.
- **CamComs**: view encryption status and identity information.

## Standalone Apps

```bash
python3 -m fiona.cli vsee
python3 -m fiona.cli phiconnect
python3 -m fiona.cli dataclient
```

## Useful First Checks

```bash
python3 -m fiona.cli list
python3 -m fiona.cli camcoms paths
python3 -m fiona.cli camcoms smoke-test
python3 -m fiona.cli seeondesk status
```
