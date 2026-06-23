# Architecture

Fiona is the umbrella package. It exposes 14 sibling subsystems and one web frontend.

## Subsystems

- `FionaCore`: shared primitives — action routing, ACL enforcement, shell safety (30+ destructive patterns blocked), macro engine with branching/conditions/variable interpolation, verification prompts, desktop notifications, and speech/voice engine integration.
- `QuikTieper`: local access layer for keyboard chords, app launching, shortcuts, pointer movement, clicks, and remote action execution.
- `CamComs`: communication layer for encoded/encrypted messages, trusted sender lifecycle, host receiver behavior, pairing flow, key rotation, and audit logging.
- `Voice`: wake-word detection (pvporcupine, snowboy, mycroft_precise), push-to-talk, and audio/visual feedback engine.
- `Vsee`: 3D coordinate hologram viewer for point/edge wireframe shapes.
- `Agent`: Ollama bridge with orchestration, chat, permissions, personality, query detection, and think-act-observe agent loop. Replaced the previous LM Studio bridge.
- `PhiConnect`: standalone encrypted computer-to-computer chat using CamComs crypto.
- `SeeOnDesk`: desktop-awareness layer for identifying the current session, focused app/window, process tracking, workspace awareness, and screen capture.
- `DataClient`: standalone research/data collection app, MiniExcel, conversion tools, and CSV export.
- `EyeControl`: optional camera-based eye-controlled mouse tracker.
- `TerminalAssist`: btop-style terminal dashboard (fAT), sliding TUI command center, and Zellij workspace helper.
- `CmdTrace`: JSONL-based observability and audit logging for routed actions, with action filtering and high-performance trace reads.
- `RecallVault`: persistent key-value remembrance store for categorized memory — search, categories, and lifecycle management.
- `BrowserAutomation`: browser automation via Playwright with session management, state machine, navigation, clicking, typing, and screenshot capture.

## Web Frontend (fionaLocalPages)

The `fionaLocalPages/` directory contains a standalone aiohttp-based single-page application (SPA) that serves as a modern web dashboard for Fiona. It replaces the need for Tkinter GUIs for most operations.

**Architecture highlights:**

- **Backend**: aiohttp Python server (`server/app.py`) that imports existing Fiona modules directly — no microservices, no containerization.
- **Frontend**: vanilla HTML/CSS/JS (no build step, no framework) with hash-based SPA routing, pub/sub state management, and component-based UI.
- **Real-time communication**: WebSocket endpoint at `/ws` and SSE at `/api/v1/stream` for live metrics, agent streaming, and event notifications.
- **REST API**: routes under `/api/v1/` covering all major subsystems — agent, actions, browser, voice, terminal, files, config, desktop, recall, macros, camcoms.
- **Port**: defaults to `8765` on `127.0.0.1`.

**What it provides:**
- Agent chat with streaming responses and personality selection
- Action runner with search, filter, permissions, and dry-run
- Browser automation controls (start, stop, navigate, click, screenshot)
- File explorer (browse, read, write, info)
- Terminal command execution and system status
- Performance monitoring dashboard (CPU, memory, disk, network)
- Settings panels (ACL, shell safety, voice, macros, general)
- RecallVault search and management
- Desktop awareness and CamComs status views

## Project Layout

```text
fiona/                 umbrella package and CLI entrypoint
QuikTieper/            local access/action layer
CamComs/               communication/encryption/host service layer
CamComs/esp32payload/  ESP32 sender payload template
Vsee/                  3D point/edge hologram model
Agent/                 local Ollama client and agent orchestrator
PhiConnect/            encrypted computer-to-computer chat app
SeeOnDesk/             desktop awareness and active-window identification
DataClient/            research/data collection app
EyeControl/            optional eye-controlled mouse tracker
TerminalAssist/        terminal dashboard and Zellij layout helper
FionaCore/             shared primitives: action routing, ACL, shell safety, macros, etc.
CmdTrace/              JSONL observability and audit trace for actions
RecallVault/           persistent key-value remembrance store
Voice/                 wake-word detection, push-to-talk, and feedback engine
BrowserAutomation/     Playwright-based browser automation with state machine
fionaLocalPages/       aiohttp SPA web frontend (REST + WebSocket + SSE)
scripts/               local launch wrappers
tests/                 Python tests
DEVELOPERNOTE.md       detailed project notes and verification log
pyproject.toml         package metadata and Python dependencies
```

## Communication Shape

CamComs currently focuses on:

```text
ESP32 sender -> encoded encrypted HTTP POST -> Fiona host receiver
```

PhiConnect uses the same cryptographic primitives for computer-to-computer chat:

```text
Fiona peer -> encrypted chat envelope -> PhiConnect receiver
```

## CLI Shape

```text
fiona quiktieper ...
fiona host ...
fiona camcoms ...
fiona agent ...
fiona seeondesk ...
fiona dataclient ...
fiona action ...
fiona voice ...
fiona macro ...
fiona recall ...
fiona eyecontrol ...
fiona fat ...
fiona vsee
fiona phiconnect
fiona browser ...
fiona approval ...
```

Shortcuts also exist for QuikTieper:

```text
fiona edit
fiona run
fiona list
```
