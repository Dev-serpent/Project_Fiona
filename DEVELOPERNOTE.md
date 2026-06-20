## Fiona Developer Notes

This file records the current Fiona project structure, runtime setup, and latest verification results.

## Project Structure

Fiona is the umbrella project. It exposes nine sibling subsystems:

- `QuikTieper`: the local access layer for keyboard, mouse, app launch, clicks, and shortcuts
- `CamComs`: the communication layer for encoded/encrypted host communication
- `Vsee`: the 3D coordinate hologram viewer
- `Agent`: the local LM Studio bridge for future agent inference
- `PhiConnect`: the standalone encrypted computer-to-computer chat app
- `SeeOnDesk`: the desktop-awareness layer for active app/window identification
- `DataClient`: the standalone research/data collection app
- `EyeControl`: optional camera-based eye-controlled mouse tracker
- `TerminalAssist`: Fiona Terminal Assistance (`fAT`) terminal dashboard and Zellij workspace helper

Current file structure:

```text
Fiona/
├── fiona/                  umbrella package and CLI entrypoint
├── cad/                    CAD platform (parametric 3D modeling)
│   ├── core/               Document, Object, Property system
│   ├── geometry/            Primitives, math, transforms, modifiers
│   ├── constraints/         Constraint types and solver
│   ├── sketch/              2D sketch workspace
│   ├── part/                Part features (Pad, Pocket, Revolve, etc.)
│   ├── assembly/            Assembly hierarchy and constraints
│   ├── commands/            Command registry and built-in commands
│   ├── scripting/           Python scripting console
│   ├── rendering/           Viewport, camera, projection
│   ├── plugins/             Plugin manager
│   ├── io/                  STL, OBJ, SVG exporters
│   ├── tests/               18 test files, 446 tests
│   └── serialization/       JSON serializer
├── QuikTieper/             local access layer implementation
├── CamComs/                communication/encryption layer implementation
│   └── esp32payload/       ESP32 sender payload template
├── Vsee/                   3D point/edge hologram viewer model
├── Agent/                  local LM Studio bridge
├── PhiConnect/             encrypted computer-to-computer chat app
├── SeeOnDesk/              desktop awareness and active-window identification
├── DataClient/             research/data collection app
├── EyeControl/             optional eye-controlled mouse tracker integration
├── TerminalAssist/         fAT terminal dashboard and Zellij layout generation
├── tests/                  Python tests (legacy)
├── scripts/                local launch wrappers
├── .backups/               timestamped backup snapshots
├── backup-20260430-185502/ older backup snapshot
├── fiona.egg-info/         editable-install metadata
├── .git/                   Git metadata
├── .agents/                agent metadata
├── .codex                  Codex metadata
├── README.md
├── DEVELOPERNOTE.md
├── pyproject.toml
├── devlog.md
├── dependencies.md
├── logo.svg
└── .gitignore
```

Current direction for communication:

- ESP32 is the sender.
- The host running Fiona is the receiver.
- ESP32 sends encoded encrypted envelopes to a host IP endpoint.
- The host decodes and decrypts using its CamComs private identity.

Important directories:

```text
fiona/                 umbrella package and CLI entrypoint
QuikTieper/            access layer implementation
CamComs/               communication/encryption layer implementation
CamComs/esp32payload/  ESP32 sender payload template
Vsee/                  3D coordinate hologram viewer implementation
Agent/                 local LM Studio bridge
PhiConnect/            encrypted computer-to-computer chat implementation
SeeOnDesk/             desktop awareness and active-window identification
DataClient/            research/data collection implementation
EyeControl/            optional camera-based eye-controlled mouse tracker
TerminalAssist/        Fiona Terminal Assistance terminal UI helpers
tests/                 Python verification tests
```

Make sure to put this in bashrc for convinience and run the aliased cmd from the project root:

```bash 
alias fiona='python3 -m fiona.cli'
```

however this 'fiona' cmd described through the projects is not created yet: So replace fiona with python3 -m fiona.cli

The umbrella CLI supports both layers:

```bash
fiona edit
fiona run
fiona list
fiona import-apps --dry-run
fiona import-apps
fiona normalize-app-cmds --dry-run
fiona normalize-app-cmds
fiona assign-keys --dry-run
fiona assign-keys
fiona quiktieper edit
fiona quiktieper run
fiona quiktieper list
fiona camcoms smoke-test
fiona camcoms keygen
fiona camcoms paths
fiona camcoms encrypt
fiona camcoms decrypt
fiona camcoms send
fiona camcoms trust
fiona camcoms trust --list
fiona camcoms trust --remove esp32
fiona camcoms audit
fiona camcoms receive
fiona camcoms service init
fiona camcoms service status
fiona camcoms service run
fiona host init
fiona host status
fiona host run
fiona phiconnect
fiona seeondesk active
fiona seeondesk status
fiona dataclient
fiona dataclient mine "topic" --out ./research.csv
fiona dataclient deep "topic" --out ./deep.csv --depth 1 --page-limit 50
fiona eyecontrol status
fiona eyecontrol run --camera-index 0 --no-click
fiona cli
fiona cli --preview
fiona fat status
fiona fat tui
fiona fat layout --print
fiona fat run
fiona ficad
fiona ficad --headless --doc my_doc --create-box 10 20 30
fiona ficad --gui
```

## Missing Issues

These are known project gaps that still need implementation. Manual GUI/workflow roughness is intentionally not listed here.

- The ESP32 payload now has a real firmware crypto adapter implementation using `mbedtls` and `libsodium`.
- Implemented X25519 key agreement, HKDF-SHA256 key derivation, AES-GCM encryption, and Ed25519 signing.
- Added NTP synchronization to the ESP32 payload to ensure valid Unix timestamps for the host's `ReplayGuard`.
- Refined WiFi reconnection behavior and added basic retry logic for message delivery.
- Fixed JSON canonicalization in the ESP32 template to match Python's `sort_keys=True` (putting `ciphertext` at the start of the signed JSON).
- Verified compatibility with Python's `cryptography` library primitives.
- Added support for both 32-byte seed and 64-byte full secret key formats for Ed25519 provisioning.
- ESP32 payload now requires `libsodium` (built-in to ESP32 core), `mbedtls` (built-in), and `ArduinoJson` 6.x/7.x.
- On 2026-06-03, hardware-ready crypto logic was refined in `CamComs/esp32payload/esp32payload.ino`.
- **Verified via Simulation**: Created `tests/test_esp32_firmware_sim.py` which mocks the exact C++ implementation of canonicalization and encoding to ensure 100% compatibility with the host's `CamComs` module.
- The ESP32 path still needs hardware validation and a robust pairing/provisioning UI.
- On 2026-06-20, the **CAD platform** (`cad/`) was added to `main` from the `windows-ide` branch. It is a FreeCAD-inspired parametric 3D modeling system with:
  - Geometry primitives (Box, Cylinder, Cone, Sphere, Torus, Line, Circle, Arc, etc.)
  - 2D Sketch workspace with entities, constraints, and constraint solver
  - Part features (Pad, Pocket, Revolve, Loft, Sweep, Fillet, Chamfer, Shell)
  - Assembly hierarchy with parts, subassemblies, and assembly constraints
  - Command system with registry, aliases, and built-in commands
  - Python scripting console for interactive CAD automation
  - Plugin manager for extensibility
  - 3D viewport with Camera, projection, and render backend abstraction
  - STL/OBJ/SVG export
  - 6 production bugs fixed (init ordering, console doc reference, sketch add_point, sphere STL indexing, SVG viewBox formatting)
  - **446 tests, all passing** (up from 38)
  - New CLI command: `fiona ficad` with `--headless`, `--doc`, and GUI launch modes
- Voice, speech output, desktop tray/background status, and rich desktop notifications are still not implemented.
- SeeOnDesk does not yet have screen recording or an ML classifier; the current implementation uses desktop/window metadata.

Recently fixed:

- CamComs host service skeleton exists through `fiona camcoms service init/status/run`.
- Fiona now also exposes the host service directly through `fiona host init/status/run`.
- CamComs host receiver/server exists through `fiona camcoms receive`.
- Decrypted CamComs messages route into an allowlisted QuikTieper remote-action runner.
- Host service config now controls receiver host/port, replay path, audit path, trusted directory, listener startup, dry-run execution, and allowed remote actions.
- Host service status now reports system/session info, QuikTieper app/binding summary, import checks, command checks, key/trust paths, audit path, replay path, and receiver port availability when requested.
- Host service can optionally own the QuikTieper listener and CamComs receiver in one process.
- QuikTieper can now discover installed Linux desktop applications from `.desktop` files and import them into the config with unassigned launch keys.
- QuikTieper app import now filters games, education apps, settings panels, helper launchers, demos, uninstallers, and most `K...` apps by default while keeping a practical allowlist such as Konsole, Kate, KWrite, KCalc, KDE Connect, KDE System Settings, Kdenlive, KDevelop, KMail, KOrganizer, KRDC, and KSystemLog.
- On 2026-05-19, filtered app import wrote 244 new launch entries to `~/.config/fiona/bindings.json`; imported entries are visible in the GUI and remain unassigned until launch keys are set.
- On 2026-05-19, generated launch keys were assigned for the 244 imported app entries. The assignment preserves the original default app chords, uses `alt` plus three distinct safer letters for generated launch chords, and checks uniqueness by pressed-key set.
- On 2026-05-19, `normalize-app-cmds` was added and applied. Fiona now has 251 app launch entries, no unassigned launch keys, and no duplicate launch key sets. The command preset pass normalizes common apps such as Brave, VS Code, Terminal, Files, KDE tools, Jupyter, media apps, and system utilities while preserving installed full-path/AppImage fallbacks when needed.
- Trusted sender public keys are stored under `~/.config/fiona/camcoms/trusted`.
- Trusted sender lifecycle now includes list/add/remove helpers and CLI access.
- CamComs audit logging records accepted/rejected host message processing and can be read through `fiona camcoms audit`.
- Replay protection rejects duplicate or stale `message_id` / `created_at` envelopes.
- Remote instruction payloads use strict JSON.
- Remote instruction payloads now support a structured `macro` instruction with nested validated steps.
- Private key files support optional passphrase encryption.
- The GUI now includes a Host tab for config init/status, trusted device inspection/removal, audit log viewing, and host path visibility.
- The GUI now includes a Debug tab that can view/edit project text files, restricted to `tests`, `scripts`, `QuikTieper`, and `CamComs`.
- The project now includes `Vsee`, a separate sibling package for point/edge 3D hologram viewing.
- The GUI now includes a Vsee tab with editable point and edge tables, a dark grid canvas, and rotation/scale controls for rendering connected 3D wireframe shapes.
- The project now includes `Agent`, a local Ollama bridge for chat-completion inference.
- Fiona now exposes `fiona agent status` and `fiona agent ask` for Ollama integration.
- Fiona now exposes `fiona vsee` for a separate `Vsee Holography` window outside the main `fiona edit` GUI.
- The project now includes `PhiConnect`, a standalone encrypted computer-to-computer chat app outside `fiona edit`.
- PhiConnect creates local chat identities, stores a peer public key for outbound encryption, trusts peer public keys for inbound verification, encrypts outbound chat with CamComs, decrypts inbound chat, and shows a rolling 3-minute chat window.
- PhiConnect defaults to port `5000` for local communication. The GUI can now set listen host/port, set a peer public key, and use the local public key for Fiona loopback testing on `127.0.0.1:5000`.
- The project now includes `SeeOnDesk`, a sibling package for desktop-awareness snapshots.
- Fiona now exposes `fiona seeondesk active` and `fiona seeondesk status`.
- SeeOnDesk currently identifies the active app/window through `kdotool` on KDE/Wayland and `xdotool`/`xprop` fallback paths when available.
- The project now includes `DataClient`, a standalone research app outside `fiona edit`.
- Fiona now exposes `fiona dataclient` for the GUI, `fiona dataclient mine` for quick topic mining, `fiona dataclient deep` for bounded deep research, `fiona dataclient convert` for CSV/JSON/SQLite conversion, and `fiona dataclient view` for terminal previews.
- DataClient exports research CSV files with topic, URL, title, summary, depth, and parent URL fields.
- DataClient now includes MiniExcel, a lightweight CSV/JSON/SQLite viewer/editor with selected-cell editing, row/column creation, row deletion, save/export support, and a safe formula bar for cell references/ranges and common functions.
- DataClient GUI now has a Miner menu for quick mining, deep research, and clearing the miner log.
- The project now includes `RecallVault`, a persistent remembrance store for key-value snippets and categories.
- Fiona now exposes `fiona recall remember/search/forget/clear/categories` for memory management.
- The project now includes `CmdTrace`, a high-performance JSONL-based observability log for all routed actions.
- Fiona now exposes `fiona action history` and `fiona action clear` for auditing system activity.
- `fiona action history` supports filtering by specific action name with `--name`.
- The imported tracker now lives at `EyeControl/Eye_Controlled_Mouse_Tracker.py` and is wrapped as the optional `EyeControl` package.
- Fiona now exposes `fiona eyecontrol status` and `fiona eyecontrol run`.
- EyeControl imports OpenCV, MediaPipe, PyAutoGUI, and camera resources only at runtime, so normal Fiona imports and tests do not require a camera.
- The project now includes `TerminalAssist`, a high-fidelity terminal dashboard and sliding command center exposed through `fiona fat`.
- fAT Dashboard now includes comprehensive system metrics: **Hostname**, **Kernel**, **CPU (Model/Usage/Temp/Speed)**, **Memory/Swap**, **Disk (Usage/IO)**, **Network (IP/Traffic/Signal)**, **GPU**, **Power (Battery/AC)**, and **Security (Firewall/Updates)**.
- fAT TUI was upgraded to a **fullscreen-style layout** with a guaranteed 1-second non-blocking auto-refresh engine.
- fAT TUI now includes **Quick Actions** for session control (Lock/Logout/Suspend) with automatic Desktop Environment detection (KDE/GNOME/XFCE).
- Fiona now exposes a **system status JSON API** through the top-level `fiona api` shortcut.
- Fiona now exposes `fiona fat`, `fiona fat status`, `fiona fat api`, `fiona fat layout`, and `fiona fat run`.
- Fiona now exposes `fiona cli`, a sliding curses-based command center for common Fiona workflows.
- `fiona fat tui` opens the same command center through the fAT namespace.
- The fAT command center now captures one-shot command output inside an in-app output panel. Interactive or long-running actions are marked external and still run through the real terminal/session.
- Fiona now exposes `fiona host install-service` to print or write a user systemd service file for startup/background operation.
- Launcher scripts point at `/home/Dhruv/Documents/Projects/Fiona`.
- README matches the current Fiona / QuikTieper / CamComs structure.
- GUI handler coverage exists for the CamComs smoke-test handler without requiring a display.

## Missing From Jarvis Except The AI Agent

recorded on 2026-05-19. Fiona already has a local action layer (`QuikTieper`), encrypted communication layer (`CamComs`), GUI, host-service skeleton, audit log, trusted-device storage, debug editor, basic `Vsee` wireframe hologram viewer, separate Vsee Holography window, standalone PhiConnect encrypted chat, a desktop-awareness layer (`SeeOnDesk`), a standalone research app (`DataClient`), and a local Ollama inference bridge (`Agent`).
 Ignoring the AI agent itself, these are the remaining systems needed for it to feel like a Jarvis-style host:

1. Real always-on service lifecycle: `fiona host install-service` can generate the user systemd unit, but Fiona still needs service enable/disable/status wrappers, clean shutdown, restart policy tuning, and GUI status integration.
2. Real ESP32 device link: the ESP32 payload now has refined firmware crypto, NTP sync, and reconnection logic. It still needs a provisioning UI, host discovery, and hardware testing on more chip variants.
3. Secure pairing flow: Fiona needs first-time pairing, fingerprint display/approval, trusted key installation, host public key provisioning, key rotation, and device removal UX.
4. Stronger command router: current routing is basic allowlisted JSON actions. It still needs sender-specific permissions, richer action categories, named command registry, better result objects, and safety prompts for risky actions.
5. Deeper system awareness: SeeOnDesk now provides a first active-window/app snapshot. Fiona still needs process registry, workspace/session state, available-action discovery, device state, richer command history search, and screen/visual recognition.
6. Voice and input surface: no wake word, push-to-talk, speech-to-text, typed command console, or confirmation flow exists yet.
7. Feedback layer: Fiona needs spoken responses, desktop notifications, visible status overlay/tray indicators, clear local failure states, and encrypted replies back to ESP32 or other devices.
8. Desktop tray/background control: no tray icon, quick open, pause/resume, service status indicator, or quit control exists yet.
9. GUI control center expansion: Host tab exists, but it still needs live receiver start/stop, listener start/stop, connected-device state, last-message view, test command buttons, pairing UI, and service logs.
10. Automation/macro expansion: basic nested macros exist, but waits, conditions, window targeting, named reusable macros, branching, and per-step failure handling are not implemented.
11. Security hardening: passphrase keys, trust store, replay protection, and audit log exist, but file permission checks, replay cleanup policy, key rotation, secure pairing, and threat-oriented validation still need work.
12. Vsee/holography expansion: Vsee is currently a point/edge wireframe viewer. It still needs saved scenes, import/export, richer primitives, camera controls, animation, live data binding, and any real hologram/projection output path.
13. Packaging and public install polish: README is public-facing, but Fiona still needs stable package discovery, tested console-script install, dependency install guidance per platform, and release packaging.
14. Cross-platform/runtime reliability: the current control stack is Linux/KDE/Wayland-oriented. Fiona still needs clearer platform support boundaries, graceful degradation, and dependency checks for missing tools like `ydotool`, `kdotool`, and `pynput`.
15. Agent training/fine-tuning system: Ollama integration is local inference only. Fiona still needs dataset capture, training/fine-tuning scripts, GPU/runtime selection, resource limits, evaluation, and rollback before any real model training should be attempted.

## Build Order

Most basic to most advanced:

1. Done: unified Fiona config at `~/.config/fiona/config.json` for QuikTieper path, CamComs key paths, trusted directory, receiver host/port, dry-run mode, allowed actions, replay path, and audit log.
2. Done: host service skeleton through `fiona host init/status/run`.
3. Done: service health checks verify config, key files, trusted dir, `ydotool`, `kdotool`, listener import, audit/replay dirs, and receiver port binding when requested.
4. Done: CamComs receiver integration is owned by `HostService.run`.
5. Done: QuikTieper listener can be owned by the host service through `start_quiktieper_listener`.
6. Done: remote action router connects decrypted CamComs instructions to configured QuikTieper actions with `execute_remote_actions` and `allowed_remote_actions`.
7. Done: standalone encrypted computer-to-computer chat exists through PhiConnect.
8. Partial: GUI Host tab shows config, health status, trusted keys, logs, and paths; live receiver process controls still need expansion.
9. Done: command history / audit log records accepted/rejected host message processing and is visible through CLI/GUI.
10. Done: trusted device manager can list, add, remove, and inspect stored sender public key JSON.
11. Partial: configurable macro layer supports structured multi-step remote actions; waits, conditions, window targeting, named macros, and per-step failure handling remain.
12. Partial: local structured success/failure result objects exist; response messages to sender and local notifications still remain.
13. Not started: desktop tray / background status.
14. Done: refined crypto adapter for X25519, HKDF-SHA256, AES-GCM, Ed25519, and NTP sync in firmware.
15. Not started: ESP32 pairing flow.
16. Not started: voice / speech interface.
17. Partial: desktop awareness through SeeOnDesk active-window snapshots; screen recording and ML recognition remain.

## Setup

The project is currently expected to run from the `quiktieper` Conda environment.

```bash
source ~/Applications/miniconda3/etc/profile.d/conda.sh
conda activate quiktieper
cd /home/Dhruv/Documents/Projects/Fiona
```

Install the project in editable mode after dependency changes:

```bash
pip install -e .
```

Required Python packages:

- `python` 3.11+
- `pynput`
- `cryptography`
- `numpy`
- `pandas`
- `requests`
- `wayland-automation` for optional Wayland pointer automation fallback

Required system tools for the launcher:

- `bash`
- `kdotool`
- `ydotool`
- `ydotoold`
- `tk` / `tkinter`
- optional fallback tools: `xprop`, `xdotool`

## Part 1: QuikTieper Launcher

QuikTieper is Fiona's keyboard control layer. It listens for global simultaneous key chords and launches apps or app-specific shortcuts.

Create the default config:

```bash
python3 -m fiona.cli init
```

List configured bindings:

```bash
python3 -m fiona.cli list
```

Start the global listener:

```bash
python3 -m fiona.cli run
```

Open the GUI editor:

```bash
python3 -m fiona.cli edit
```

Equivalent umbrella CLI commands:

```bash
fiona edit
fiona quiktieper edit
```

Preferred launcher wrappers:

```bash
./scripts/fiona-edit
./scripts/fiona-run
```

These wrappers:

- activate the `quiktieper` Conda environment
- request privilege up front for `ydotoold` with `pkexec` if needed
- start Fiona normally as the desktop user

The default config path is:

```text
~/.config/fiona/bindings.json
```

Example app commands used in the default config:

- `brave`
- `code`
- `konsole`
- `dolphin`

Runtime assumptions:

- Current target desktop is KDE Plasma on Wayland.
- App-specific shortcut routing prefers `kdotool`.
- Mouse movement and click actions prefer `ydotool`.
- `xprop` and `xdotool` are fallback / legacy paths.

## SeeOnDesk Desktop Awareness

SeeOnDesk is Fiona's current desktop-awareness subsystem. It does not do screen recording or ML recognition yet; it identifies the focused app/window through desktop metadata.

Current commands:

```bash
fiona seeondesk active
fiona seeondesk status
```

Current implementation:

- prefers `kdotool` for KDE/Wayland focused-window detection
- falls back to `xdotool` and `xprop` on X11-compatible sessions
- returns active window id, app class, inferred app name, title, process id, process name, session type, and desktop name when available
- fails closed with `backend: unavailable` when run from a sandbox/service without desktop session access

## Part 2: CamComs Communication

CamComs is Fiona's communications layer. The current implemented parts are:

- `CamComs/encryption.py`: public/private encryption and signing
- `CamComs/codec.py`: base64url JSON envelope encoding/decoding
- `CamComs/transport.py`: HTTP POST client for encoded messages
- `CamComs/esp32payload/`: ESP32 sender payload template

The current model is ESP32 sender to host receiver.

Run the CamComs tests:

```bash
python3 -m unittest tests.test_camcoms_encryption tests.test_camcoms_transport
```

Minimal ESP32-to-host smoke test:

```bash
fiona camcoms smoke-test
```

Expected output:

```text
{"keys":["alt","s"],"type":"press","version":1}
```

What the CamComs encrypter currently provides:

- `CamComsIdentity.generate()` creates a device identity.
- Each identity has an X25519 encryption keypair.
- Each identity has an Ed25519 signing keypair.
- `identity.public_bundle` is safe to share with another device.
- `encrypt_message(...)` encrypts a payload to the recipient public key.
- `decrypt_message(...)` decrypts using the recipient private key.
- `decrypt_text(...)` is a UTF-8 text helper around `decrypt_message(...)`.
- Sender signatures are verified during decrypt when `expected_sender` is provided.
- Tampered messages and wrong-recipient messages raise `CamComsCryptoError`.
- Remote instruction payloads use strict JSON objects, for example `{"keys":["alt","s"],"type":"press","version":1}`.

The encrypted envelope uses:

- X25519 for public/private key agreement
- HKDF-SHA256 for message key derivation
- AES-GCM for authenticated encryption
- Ed25519 for sender signatures

### ESP32 Payload

ESP32 payload files:

```text
CamComs/esp32payload/README.md
CamComs/esp32payload/esp32payload.ino
```

Host receiver identity:

```bash
fiona camcoms keygen --device-id host
```

ESP32 sender identity for provisioning:

```bash
fiona camcoms keygen --device-id esp32
```

The ESP32 payload needs:

- host device id
- host encryption public key
- ESP32 device id
- ESP32 signing private key

The ESP32 static encryption private key is not needed for the current one-way sender-to-host direction. It becomes relevant once the host also encrypts replies back to the ESP32.

Default visible key paths:

```text
~/.config/fiona/camcoms/host.private.json
~/.config/fiona/camcoms/host.public.json
~/.config/fiona/camcoms/esp32.private.json
~/.config/fiona/camcoms/esp32.public.json
```

## Validation Commands

Run the launcher CLI check:

```bash
fiona list
```

Run all current tests:

```bash
python -m unittest discover -s tests -v
```

Latest result, run on 2026-06-20:

```text
446 passed, 5 subtests passed in 0.41s
```

CAD platform tests can also be run independently:

```bash
python -m pytest cad/tests/ --tb=short -q
```

Note: Legacy `tests/` tests use `unittest discover`. CAD tests use `pytest` for modern fixture support. Both test suites pass.

Direct host-service CLI smoke checks, run on 2026-05-05:

```bash
python -m fiona.cli host init --config /tmp/fiona-host-test.json --force
python -m fiona.cli host status --config /tmp/fiona-host-test.json
python -m fiona.cli camcoms audit --path /tmp/fiona-audit-missing.log --limit 5
python -m fiona.cli camcoms trust --list --trusted-dir /tmp/fiona-trusted-missing
```

Latest direct CLI result:

```text
host init wrote /tmp/fiona-host-test.json
host status returned config, checks, system summary, and QuikTieper app/binding summary
camcoms audit returned an empty event list for a missing audit log
camcoms trust --list returned an empty sender list for a missing trusted directory
```

Run the CamComs ESP32-to-host smoke test:

```bash
fiona camcoms smoke-test
```

Latest output:

```text
{"keys":["alt","s"],"type":"press","version":1}
```

Compile the main packages:

```bash
python -m compileall Agent CamComs DataClient EyeControl PhiConnect QuikTieper SeeOnDesk TerminalAssist Vsee fiona
```

Latest result, run on 2026-05-26:

```text
Compiled without syntax errors.
```

## Debugging Files

Primary debug log:

```text
~/.config/fiona/debug.log
```

Fallback debug log:

```text
/tmp/fiona-debug.log
```

These logs may contain:

- key press / release traces
- binding match / skip reasons
- active window detection results
- pointer backend success / failure
- shell command launch events

## Agent Personalities & Orchestration System

Added 2026-06-20 as part of the agent expansion milestone.

### New Subsystems

#### Personality System (`Agent/personality.py`)
- `Personality` frozen dataclass with name, description, system_prompt, allowed_tools, model_override
- `PersonalityRegistry` thread-safe singleton with 5 built-in personalities:
  - `general`: All tools, general-purpose assistant
  - `planner`: Read-only analysis tools, strategic planning
  - `engineer`: Automation and execution tools
  - `analyst`: Research and memory tools
  - `security`: Read-only security audit tools
- `PermissionEnforcer` (`Agent/permission.py`) — runtime tool authorization gate
- `SafeActionRouter` (`Agent/permission.py`) — wraps ActionRouter with personality-based permission checks

#### SQLite Chat Persistence (`Agent/chat_store.py`)
- `ChatStore` — thread-safe SQLite-backed chat storage with WAL mode
- Schema: `sessions` + `messages` tables with indexes
- Context window builder with token-aware truncation
- JSONL import for migration from legacy formats

#### Cancellation System (`Agent/cancellation.py`)
- `CancellationToken` — threading.Event-based cooperative cancellation
- `CancelledError` — raised when operation is cancelled
- Used across all layers from GUI to LLM calls

#### Orchestration Engine (`Agent/orchestration.py`)
- `ComplexityAssessor` — LLM-based goal complexity classification
- `TaskPlan` — validated goal decomposition with retry logic
- `SubAgent` — personality-wrapped ReAct agent with SafeActionRouter
- `ForemanAgent` — top-level orchestrator: assess → decompose → execute → synthesize
- `ForemanConfig` — configuration dataclass (parallel default off, configurable limits)

#### PhiConnect Agent Tab (`PhiConnect/gui.py` — Agent tab)
- New "Agent" tab in PhiConnect notebook
- Personality selector dropdown (5 personalities)
- Color-coded chat display (blue user, green agent, grey system, red error, orange cancelled)
- Cancel button with full cancellation propagation
- Foreman toggle for advanced orchestration
- Foreman configuration in Settings tab

### Backward Compatibility
All existing Agent APIs remain unchanged:
- `AgentOrchestrator`, `AgentTurn`, `CommandSpec`, `OllamaClient`, `command_registry()`, `run_agent_goal()`
- PhiConnect Chat and Settings tabs are untouched

### New Dependencies
None. All new code uses Python 3.11+ stdlib only.

### Test Coverage
- `tests/test_agent_personalities.py` — 59 tests
- `tests/test_agent_chat_store.py` — 54 tests
- `tests/test_agent_chat_handler.py` — 34 tests
- `tests/test_agent_orchestration.py` — 66 tests
- `tests/test_agent_foreman_handler.py` — 59 tests
- `tests/test_agent_stress.py` — 28 tests
- `tests/test_agent_backward_compat.py` — 12 tests

Total new tests: ~312

## Permission Notes

`ydotoold` may need privileged startup depending on the machine setup.

Fiona may attempt daemon startup using:

```text
pkexec ydotoold
sudo -n ydotoold
ydotoold
```
