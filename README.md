# Fiona

Fiona is a local host-control project inspired by JARVIS-style workstation control. It is not a full AI agent yet. The current project is the software base around that future agent: local actions, encrypted device communication, desktop awareness, optional eye-controlled pointer experiments, a local LM Studio bridge, and a simple 3D hologram viewer.

After installation, the command is:

```bash
fiona
```

When running from a source checkout before installing the console script, use the module form from the repository root:

```bash
cd Fiona
python3 -m fiona.cli <command>
```

Examples:

```bash
python3 -m fiona.cli edit
python3 -m fiona.cli list
python3 -m fiona.cli camcoms smoke-test
```

If `fiona` prints `command not found`, the package has not been installed into the active environment yet, or that environment's script directory is not on `PATH`. Use `python3 -m fiona.cli ...` from the repository root, or run `pip install -e .` inside the environment you want to use.

## Current Architecture

Fiona is the umbrella package. It exposes eight sibling subsystems:

- `QuikTieper`: local access layer for keyboard chords, app launching, shortcuts, pointer movement, clicks, and remote action execution.
- `CamComs`: communication layer for encoded/encrypted messages, currently focused on ESP32 sender to Fiona host receiver.
- `Vsee`: 3D coordinate hologram viewer for point/edge wireframe shapes.
- `Agent`: local LM Studio bridge for the future agent layer.
- `PhiConnect`: standalone encrypted computer-to-computer chat using CamComs crypto.
- `SeeOnDesk`: desktop-awareness layer for identifying the current session and focused app/window.
- `DataClient`: standalone research/data collection app for topic search, page scraping, summarization, deep research, and CSV export.
- `EyeControl`: optional camera-based eye-controlled mouse tracker.

Project layout:

```text
fiona/                 umbrella package and CLI entrypoint
QuikTieper/            local access/action layer
CamComs/               communication/encryption/host service layer
CamComs/esp32payload/  ESP32 sender payload template
Vsee/                  3D point/edge hologram model
Agent/                 local LM Studio client
PhiConnect/            encrypted computer-to-computer chat app
SeeOnDesk/             desktop awareness and active-window identification
DataClient/            research/data collection app
EyeControl/            optional eye-controlled mouse tracker integration
scripts/               local launch wrappers
tests/                 Python tests
DEVELOPERNOTE.md       detailed project notes and latest verification log
pyproject.toml         package metadata and Python dependencies
```

## Install

Clone the repository, create or activate a Python environment, and install the project in editable mode:

```bash
git clone <repo-url> Fiona
cd Fiona
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Conda works too:

```bash
conda create -n fiona python=3.13
conda activate fiona
git clone <repo-url> Fiona
cd Fiona
pip install -e .
```

Core Python dependencies are declared in `pyproject.toml`:

- `cryptography`
- `pynput`
- `numpy`
- `pandas`
- `requests`

LM Studio is optional. Fiona talks to it over its local OpenAI-compatible server API when the agent bridge is used.

EyeControl is optional. Install its camera/vision dependencies only on machines that will run the tracker:

```bash
pip install -e ".[eyecontrol]"
```

System/runtime tools used by local control:

- `ydotool` for pointer/keyboard automation
- `kdotool` for KDE/Wayland active-window checks
- `xdotool` / `xprop` as fallback or legacy paths

## GUI

Open the shared GUI:

```bash
cd Fiona
python3 -m fiona.cli edit
```

If the project is installed and the console script is on `PATH`, this is equivalent:

```bash
fiona edit
```

Current panel order:

```text
CamComs -> Vsee -> Bindings -> Raw Json -> Debug -> Host
```

Panel roles:

- `CamComs`: generate identities, export public keys, encrypt/decrypt messages, send encoded envelopes, and run a local smoke test.
- `Vsee`: edit 3D `points` and `edges` tables and render them as a connected wireframe hologram.
- `Bindings`: edit QuikTieper app launchers and shortcut bindings.
- `Raw Json`: edit the QuikTieper config JSON directly.
- `Debug`: restricted project file editor for `tests`, `scripts`, `QuikTieper`, and `CamComs`.
- `Host`: inspect host service config, trusted devices, key paths, and audit logs.

Open the separate holography-only window:

```bash
python3 -m fiona.cli vsee
```

Open the separate encrypted chat window:

```bash
python3 -m fiona.cli phiconnect
```

Open the separate DataClient research window:

```bash
python3 -m fiona.cli dataclient
```

## SeeOnDesk

SeeOnDesk is Fiona's first desktop-awareness layer. The current version does not train a screen-recording model yet. It identifies what is open/focused using desktop session metadata, `kdotool` on KDE/Wayland, and `xdotool`/`xprop` fallback paths where available.

Show the current focused app/window:

```bash
python3 -m fiona.cli seeondesk active
```

Show a full desktop-awareness snapshot:

```bash
python3 -m fiona.cli seeondesk status
```

Installed-command equivalents:

```bash
fiona seeondesk active
fiona seeondesk status
```

Current output includes:

- whether detection succeeded
- backend used, such as `kdotool` or `x11`
- active window id
- app class / inferred app name
- window title
- process id and process name when available
- session type and current desktop in `status`

This is the base for future screen capture, object/window recognition, and command context. If the command is run from a restricted sandbox or service without access to the desktop session bus, it may report `backend: unavailable`; running it as the active desktop user should return the focused app.

## EyeControl

EyeControl is Fiona's optional eye-controlled mouse tracker integration. The tracker now lives at `EyeControl/Eye_Controlled_Mouse_Tracker.py`, and the umbrella CLI imports it through the `EyeControl` package so opening Fiona help does not start the camera loop.

Check dependency readiness:

```bash
python3 -m fiona.cli eyecontrol status
```

Run against an IP camera snapshot URL:

```bash
python3 -m fiona.cli eyecontrol run --url http://192.168.0.103:8080/shot.jpg
```

Run against a local OpenCV camera index:

```bash
python3 -m fiona.cli eyecontrol run --camera-index 0
```

Move the pointer without blink-clicking while testing:

```bash
python3 -m fiona.cli eyecontrol run --camera-index 0 --no-click
```

EyeControl requires camera access and optional packages such as OpenCV, MediaPipe, and PyAutoGUI, so it may be unoperational on machines without a camera or those packages.

## QuikTieper

QuikTieper is the local access layer. It listens for simultaneous global key chords and runs configured actions.

Default config path:

```text
~/.config/fiona/bindings.json
```

Basic commands:

```bash
python3 -m fiona.cli init
python3 -m fiona.cli list
python3 -m fiona.cli import-apps --dry-run
python3 -m fiona.cli import-apps
python3 -m fiona.cli normalize-app-cmds --dry-run
python3 -m fiona.cli normalize-app-cmds
python3 -m fiona.cli assign-keys --dry-run
python3 -m fiona.cli assign-keys
python3 -m fiona.cli run
python3 -m fiona.cli edit
```

Command details:

- `python3 -m fiona.cli init`: creates `~/.config/fiona/bindings.json` if it does not exist. It is safe to run more than once because it does not overwrite an existing bindings file.
- `python3 -m fiona.cli list`: prints every configured app launch chord and shortcut command. Use this to confirm Fiona can read the active bindings file.
- `python3 -m fiona.cli import-apps --dry-run`: scans installed Linux `.desktop` launchers and reports how many app entries would be added without changing the bindings file.
- `python3 -m fiona.cli import-apps`: imports newly discovered desktop apps into the bindings file. Imported apps start with no launch keys, so they cannot trigger accidentally until keys are assigned.
- `python3 -m fiona.cli import-apps --include-all-k-apps`: imports all `K...` apps instead of using Fiona's curated K-app allowlist.
- `python3 -m fiona.cli import-apps --include-low-value-apps`: also imports entries Fiona normally skips, such as games, education apps, helpers, demos, and settings panels.
- `python3 -m fiona.cli normalize-app-cmds --dry-run`: shows which app launch commands would be normalized to Fiona's curated command presets without saving changes.
- `python3 -m fiona.cli normalize-app-cmds`: applies the curated command presets. This cleans noisy desktop launcher wrappers into direct commands where possible, while keeping installed full-path/AppImage fallbacks where needed.
- `python3 -m fiona.cli assign-keys --dry-run`: reports how many app launch entries still need generated launch keys.
- `python3 -m fiona.cli assign-keys`: assigns generated launch keys to apps missing keys. Generated launch chords use `alt` plus three safer letters and avoid duplicate pressed-key sets.
- `python3 -m fiona.cli assign-keys --reassign`: regenerates imported-app launch keys while preserving the original hand-written default app chords.
- `python3 -m fiona.cli run`: starts the global QuikTieper listener. This is a foreground process and keeps running until stopped. It requires runtime dependencies such as `pynput`, and on Wayland may need `ydotoold`.
- `python3 -m fiona.cli edit`: opens the shared Fiona GUI editor. This is a foreground GUI process and keeps running until the window is closed.

Installed-command equivalents:

```bash
fiona init
fiona list
fiona import-apps --dry-run
fiona import-apps
fiona normalize-app-cmds --dry-run
fiona normalize-app-cmds
fiona assign-keys --dry-run
fiona assign-keys
fiona run
fiona edit
```

Explicit layer commands:

```bash
python3 -m fiona.cli quiktieper list
python3 -m fiona.cli quiktieper run
python3 -m fiona.cli quiktieper edit
```

The explicit `quiktieper` form runs the same QuikTieper commands as the short form. For example, `python3 -m fiona.cli quiktieper list` and `python3 -m fiona.cli list` read the same bindings file.

Current capabilities:

- app launching from chord bindings
- installed desktop application discovery from `.desktop` launchers
- app-specific shortcuts gated by active-window matching
- shell command execution
- pointer movement and click helpers
- allowlisted remote actions for CamComs instructions
- structured macro instructions with nested steps

`import-apps` scans standard Linux desktop launcher directories such as `~/.local/share/applications`, `/usr/local/share/applications`, and `/usr/share/applications`. Imported apps are added with no launch keys by default so they are visible in the GUI but cannot accidentally trigger until chords are assigned.

The importer filters obvious low-value entries such as games, education apps, settings panels, helper launchers, demos, and uninstallers. It also skips most `K...` apps by default while keeping a curated practical allowlist such as Konsole, Kate, KWrite, KCalc, KDE Connect, KDE System Settings, Kdenlive, KDevelop, KMail, KOrganizer, KRDC, KSystemLog, and similar tools. Use these override flags only when needed:

```bash
python3 -m fiona.cli import-apps --include-all-k-apps
python3 -m fiona.cli import-apps --include-low-value-apps
```

`assign-keys` fills in missing launch chords. Generated launch chords use `alt` plus three distinct letters from a safer alphabet, avoid duplicate pressed-key sets, and preserve the original hand-written default app chords. Use `--reassign` to regenerate imported-app chords while keeping those defaults:

```bash
python3 -m fiona.cli assign-keys --reassign
```

`normalize-app-cmds` applies Fiona's curated command presets for common workstation apps after desktop import. It keeps installed fallbacks where needed, so entries such as Terminal, Files, browsers, KDE tools, Jupyter, media apps, and system utilities use direct launch commands instead of noisy desktop launcher wrappers:

```bash
python3 -m fiona.cli normalize-app-cmds --dry-run
python3 -m fiona.cli normalize-app-cmds
```

Example default bindings:

- `alt + b + r + v` opens Brave
- `alt + v + s + c` opens VS Code
- `alt + t + e + r` opens terminal

## CamComs

CamComs is the communication and encryption layer.

Current communication direction:

```text
ESP32 sender -> encoded encrypted HTTP POST -> Fiona host receiver
```

Implemented pieces:

- X25519 key agreement
- HKDF-SHA256 key derivation
- AES-GCM encrypted payloads
- Ed25519 sender signatures
- base64url JSON envelope encoding/decoding
- trusted sender public-key storage
- replay protection for duplicate/stale messages
- host receiver and host service skeleton
- audit log for accepted/rejected message processing
- strict JSON instruction validation

Default CamComs storage paths:

```text
~/.config/fiona/camcoms/host.private.json
~/.config/fiona/camcoms/host.public.json
~/.config/fiona/camcoms/esp32.private.json
~/.config/fiona/camcoms/esp32.public.json
~/.config/fiona/camcoms/trusted/
~/.config/fiona/camcoms/audit.log
```

Useful commands:

```bash
python3 -m fiona.cli camcoms smoke-test
python3 -m fiona.cli camcoms paths
python3 -m fiona.cli camcoms keygen --device-id host
python3 -m fiona.cli camcoms keygen --device-id esp32
python3 -m fiona.cli camcoms trust --public ~/.config/fiona/camcoms/esp32.public.json
python3 -m fiona.cli camcoms trust --list
python3 -m fiona.cli camcoms audit
```

Command details:

- `python3 -m fiona.cli camcoms smoke-test`: creates temporary in-memory identities, encrypts a sample `alt+s` press instruction, decrypts it, and prints the decoded JSON instruction. This does not write key files.
- `python3 -m fiona.cli camcoms paths`: prints the default visible CamComs storage paths for host keys, ESP32 keys, trusted sender keys, and audit logs.
- `python3 -m fiona.cli camcoms keygen --device-id host`: creates or overwrites the default host private/public identity files under `~/.config/fiona/camcoms/`.
- `python3 -m fiona.cli camcoms keygen --device-id esp32`: creates or overwrites the default ESP32 provisioning identity files under `~/.config/fiona/camcoms/`.
- `python3 -m fiona.cli camcoms keygen --device-id <name> --private-out <path> --public-out <path>`: writes a named identity to explicit paths instead of Fiona's default key paths.
- `python3 -m fiona.cli camcoms keygen --device-id <name> --passphrase <passphrase>`: encrypts the private identity file with a passphrase. Use a real secret outside shell history for production.
- `python3 -m fiona.cli camcoms public --private <private.json> --public-out <public.json>`: exports a public key bundle from an existing private identity file.
- `python3 -m fiona.cli camcoms trust --public <public.json>`: stores a sender public key in the trusted sender directory. The receiver only accepts signed messages from trusted senders.
- `python3 -m fiona.cli camcoms trust --list`: lists trusted sender public keys.
- `python3 -m fiona.cli camcoms trust --remove <device-id>`: removes a trusted sender by device id, such as `esp32`.
- `python3 -m fiona.cli camcoms audit`: prints recent receiver audit events from `~/.config/fiona/camcoms/audit.log`.
- `python3 -m fiona.cli camcoms audit --limit 10`: prints only the 10 most recent audit events.

Encrypt a press instruction for the host:

```bash
python3 -m fiona.cli camcoms encrypt \
  --sender-private ~/.config/fiona/camcoms/esp32.private.json \
  --recipient-public ~/.config/fiona/camcoms/host.public.json \
  --press alt s
```

`camcoms encrypt` requires either `--press ...` or `--instruction-json ...`. Without one of those inputs it exits with a usage error.

Encrypt a structured instruction JSON object:

```bash
python3 -m fiona.cli camcoms encrypt \
  --sender-private ~/.config/fiona/camcoms/esp32.private.json \
  --recipient-public ~/.config/fiona/camcoms/host.public.json \
  --instruction-json '{"version":1,"type":"press","keys":["alt","s"]}'
```

Print the full envelope JSON instead of the compact encoded text:

```bash
python3 -m fiona.cli camcoms encrypt \
  --sender-private ~/.config/fiona/camcoms/esp32.private.json \
  --recipient-public ~/.config/fiona/camcoms/host.public.json \
  --press alt s \
  --json
```

Decrypt an encoded envelope:

```bash
python3 -m fiona.cli camcoms decrypt \
  --recipient-private ~/.config/fiona/camcoms/host.private.json \
  --sender-public ~/.config/fiona/camcoms/esp32.public.json \
  --encoded '<encoded-message>'
```

Decrypt an envelope JSON file:

```bash
python3 -m fiona.cli camcoms decrypt \
  --recipient-private ~/.config/fiona/camcoms/host.private.json \
  --sender-public ~/.config/fiona/camcoms/esp32.public.json \
  --envelope ./message-envelope.json
```

`camcoms decrypt` requires `--recipient-private` plus either `--encoded` or `--envelope`.

Send an encoded message to a host/IP endpoint:

```bash
python3 -m fiona.cli camcoms send \
  --host 192.168.1.50 \
  --port 8080 \
  --path / \
  --encoded '<encoded-message>'
```

Send an envelope JSON file:

```bash
python3 -m fiona.cli camcoms send \
  --host 192.168.1.50 \
  --port 8080 \
  --envelope ./message-envelope.json
```

`camcoms send` requires `--host` plus either `--encoded` or `--envelope`. It posts the compact encoded message to the configured HTTP endpoint.

Run the receiver directly:

```bash
python3 -m fiona.cli camcoms receive --private ~/.config/fiona/camcoms/host.private.json --port 8080
```

Receiver details:

- `python3 -m fiona.cli camcoms receive`: starts the host receiver on `0.0.0.0:8080` using the default host private key and trusted sender directory.
- `python3 -m fiona.cli camcoms receive --host 127.0.0.1 --port 8081`: binds to a specific interface and port.
- `python3 -m fiona.cli camcoms receive --execute`: executes approved QuikTieper remote actions. Without `--execute`, the receiver uses dry-run mode for safer testing.
- `python3 -m fiona.cli camcoms receive --trusted-dir <dir>`: reads trusted sender public keys from a custom directory.

`camcoms receive` is a foreground server process. Leave it running while ESP32 or other senders post messages to the host.

Host service commands:

```bash
python3 -m fiona.cli host init
python3 -m fiona.cli host status
python3 -m fiona.cli host run
python3 -m fiona.cli host install-service --print
```

Host service command details:

- `python3 -m fiona.cli host init`: writes the default unified Fiona host service config to `~/.config/fiona/config.json`. If the file already exists, it refuses to overwrite it.
- `python3 -m fiona.cli host init --force`: overwrites the host service config with defaults.
- `python3 -m fiona.cli host status`: prints config, key paths, trusted sender status, QuikTieper summary, dependency checks, and system/session details.
- `python3 -m fiona.cli host status --check-port`: also checks whether the configured receiver port can bind.
- `python3 -m fiona.cli host run`: starts the unified host service in the foreground. It can own the CamComs receiver and, depending on config, the QuikTieper listener.
- `python3 -m fiona.cli host run --passphrase <passphrase>`: starts the host service with a passphrase for an encrypted host private key.
- `python3 -m fiona.cli host install-service --print`: prints the user systemd unit without writing it.
- `python3 -m fiona.cli host install-service`: writes `~/.config/systemd/user/fiona-host.service`.
- `python3 -m fiona.cli host install-service --name my-fiona.service`: writes a custom user service name.
- `python3 -m fiona.cli host install-service --working-directory <repo-path> --python <python-path>`: controls the working directory and Python executable used by the generated service.

`install-service --print` previews the user systemd service. Running it without `--print` writes `~/.config/systemd/user/fiona-host.service`, after which a Linux user can run:

```bash
systemctl --user daemon-reload
systemctl --user enable --now fiona-host.service
```

The older nested service commands also exist:

```bash
python3 -m fiona.cli camcoms service init
python3 -m fiona.cli camcoms service status
python3 -m fiona.cli camcoms service run
```

These nested commands call the same host service implementation as `python3 -m fiona.cli host ...`. Prefer the shorter `host` form for normal use.

## Vsee

Vsee is the current holography software layer. It is intentionally simple right now: a point/edge model rendered as a 3D wireframe in the GUI.

Open the standalone Vsee window:

```bash
python3 -m fiona.cli vsee
```

Open Vsee with point and edge CSV files:

```bash
python3 -m fiona.cli vsee --points ./points.csv --edges ./edges.csv
```

`vsee` is a foreground GUI process. It stays open until the window is closed.

Vsee input format:

```csv
id,x,y,z
A,-1,-1,-1
B,1,-1,-1
```

Edge format:

```csv
source,target
A,B
```

Current capabilities:

- load/edit point and edge tables in the GUI
- validate duplicate point IDs and missing edge references
- project 3D coordinates into a 2D canvas using `numpy`
- parse editable table data using `pandas`
- render connected wireframe shapes with rotation and scale controls

## PhiConnect

PhiConnect is the computer-to-computer communication app. It is separate from `fiona edit`, like `Vsee Holography`, and uses the existing CamComs encryption primitives for chat instead of remote-control instructions.

Open PhiConnect:

```bash
python3 -m fiona.cli phiconnect
```

Current capabilities:

- creates a local PhiConnect identity under `~/.config/fiona/phiconnect/`
- shows your public key in the Settings tab
- lets you trust another computer's public key
- starts a local encrypted chat receiver on port `5000` by default
- sends chat messages to a peer host/port
- encrypts every sent message with the peer public key
- decrypts received messages with the local private key
- records inbound/outbound chat events in `~/.config/fiona/phiconnect/chat.log`
- displays messages from the last 3 minutes, refreshing every 5 seconds

Two computers can communicate by exchanging public key JSON files, trusting each other's keys, then pointing each PhiConnect instance at the other machine's IP and port.

For local Fiona loopback testing, open PhiConnect, use `Use Local Public Key` in Settings, start the receiver, then send to `127.0.0.1` port `5000`. A send error saying the peer public key is missing means the outbound encryption key has not been set yet. A connection-refused error means no receiver is listening on the target host/port.

## DataClient

DataClient is a standalone research and data collection app. It is separate from `fiona edit`, like Vsee and PhiConnect.

Open the DataClient GUI:

```bash
python3 -m fiona.cli dataclient
```

The GUI has two tabs:

- `Research`: quick topic mining and bounded deep research.
- `MiniExcel`: lightweight CSV/JSON/SQLite table viewer and editor.

The app menu includes a `Miner` menu for starting quick mining, starting deep research, and clearing the miner log without digging through the tab controls.

Quick mode searches DuckDuckGo HTML results, scrapes the selected number of pages, summarizes page text, and saves a CSV. Deep mode starts from search results, follows same-domain links up to a controlled depth/page limit, and records each page's depth and parent URL.

CLI quick mining:

```bash
python3 -m fiona.cli dataclient mine "local desktop automation" --out ./research.csv --max-links 30
```

CLI deep research:

```bash
python3 -m fiona.cli dataclient deep "local desktop automation" --out ./deep-research.csv --seed-links 10 --depth 1 --page-limit 50
```

DataClient CSV columns:

- `topic`
- `url`
- `title`
- `summary`
- `depth`
- `parent_url`

Deep mode is intentionally bounded. By default it stays on the same domain as each seed page and only crawls one level deep. Use `--cross-domain` only when you intentionally want broader crawling.

MiniExcel can open CSV, JSON, and SQLite files, show them as rows/columns, edit a selected cell, add rows, add columns, delete rows, and save/export the table. It also has a formula bar for selected cells. Formulas start with `=` and support cell references such as `A1`, ranges such as `B1:B5`, arithmetic, and safe functions including `SUM`, `AVG`, `MIN`, `MAX`, `COUNT`, `LEN`, `LOWER`, and `UPPER`.

Convert between table formats:

```bash
python3 -m fiona.cli dataclient convert ./research.csv --out ./research.json
python3 -m fiona.cli dataclient convert ./research.json --out ./research.db --table research
```

Preview a table from the terminal:

```bash
python3 -m fiona.cli dataclient view ./research.csv --limit 5
```

## Agent And LM Studio

Agent is the first bridge toward the future AI agent. It talks to LM Studio as a local inference server, using LM Studio's OpenAI-compatible API.

Start LM Studio's local server from LM Studio's Developer tab, or with:

```bash
lms server start
```

Then test the connection:

```bash
python3 -m fiona.cli agent status
```

`agent status` checks LM Studio's local OpenAI-compatible API endpoint and prints the health response or connection error.

Ask the local model a question:

```bash
python3 -m fiona.cli agent ask --model <model-id> "Summarize Fiona status."
```

Agent command options:

- `python3 -m fiona.cli agent status --base-url http://localhost:1234/v1`: checks a custom LM Studio endpoint.
- `python3 -m fiona.cli agent ask --model <model-id> "Prompt text"`: sends a prompt to the selected local model.
- `python3 -m fiona.cli agent ask --system "System prompt" --temperature 0.3 --max-tokens 512 --model <model-id> "Prompt text"`: customizes the system prompt and sampling/output limits.

Default LM Studio endpoint:

```text
http://localhost:1234/v1
```

Important: this is inference, not model training. Fine-tuning/training with GPU acceleration, large CPU thread counts, dataset preparation, and memory controls is a separate future system. Fiona should first use LM Studio for local reasoning and tool planning, then add training/fine-tuning infrastructure only after the agent workflow and datasets are defined.

## Debug Mode

The GUI Debug tab is a restricted project editor. It can view and edit text/code files only under:

```text
tests/
scripts/
QuikTieper/
CamComs/
```

It intentionally does not expose the whole filesystem or every project directory. It also skips generated cache directories such as `__pycache__`.

## Wrapper Scripts

Local scripts are available:

```bash
./scripts/fiona-edit
./scripts/fiona-run
```

They are intended to activate the project environment, enter the repo, and launch Fiona.

## Current State

Working today:

- installable Fiona umbrella CLI
- shared Tkinter GUI
- standalone `Vsee Holography` GUI
- standalone `PhiConnect` encrypted chat GUI
- standalone DataClient research GUI
- SeeOnDesk desktop-awareness CLI
- EyeControl optional camera tracker CLI
- QuikTieper binding editor/listener/action runner
- CamComs encryption/decryption/transport/receiver
- trusted sender lifecycle and audit logging
- host service config/status/run commands
- user systemd service unit generation for the host service
- LM Studio local inference bridge
- DataClient quick mining and bounded deep research CSV export
- encrypted computer-to-computer chat through PhiConnect
- Vsee point/edge hologram viewer
- project-restricted GUI debug editor
- curated app command presets through `normalize-app-cmds`
- Python tests for the core model/crypto/transport/service/GUI handler paths

Still incomplete:

- no full AI agent planner/tool loop yet
- no screen-recording or ML classifier layer for SeeOnDesk yet
- no Fiona training/fine-tuning pipeline yet
- ESP32 firmware crypto adapter is still a template, not hardware-verified
- no ESP32 pairing flow yet
- no desktop tray/background autostart install yet
- no voice/speech layer yet
- no rich notification or spoken feedback layer yet
- Vsee is currently a wireframe coordinate viewer, not true optical holography

## Validation

Run all current tests:

```bash
python -m unittest discover -s tests -v
```

Compile the main packages:

```bash
python -m compileall Agent CamComs DataClient EyeControl PhiConnect QuikTieper SeeOnDesk Vsee fiona
```

Current latest known result:

```text
83 tests OK
compileall OK
```
