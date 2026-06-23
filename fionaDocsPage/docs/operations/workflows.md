# System Workflows

This page describes how Fiona's subsystems cooperate during real operations.

## Local Launch Workflow

Goal: press a configured chord and launch or control a local app.

```text
user key event
  -> QuikTieper listener
  -> chord state matcher
  -> active-window gate for app shortcuts
  -> binding action
  -> command / instruction / pointer action
```

State involved:

- `~/.config/fiona/bindings.json`
- active window metadata from desktop tools
- listener runtime state and cooldowns
- configured command strings and Fiona command helpers

Failure handling:

- malformed config fails at parse/load time
- missing app command fails at shell launch time
- unavailable desktop automation backend prevents pointer/keyboard execution
- active-window mismatch prevents app-specific shortcuts from firing
- destructive shell commands are blocked by `FionaCore.shell_safety`

## Installed App Import Workflow

Goal: make system applications available as QuikTieper launch entries.

```text
desktop launcher directories
  -> .desktop parser
  -> low-value/K-app filters
  -> imported app entries without keys
  -> assign-keys
  -> normalize-app-cmds
  -> GUI/listener usable config
```

The importer scans common Linux launcher paths such as:

```text
~/.local/share/applications
/usr/local/share/applications
/usr/share/applications
```

Imported apps start unassigned so new applications cannot fire accidentally. `assign-keys` gives them generated launch chords, and `normalize-app-cmds` rewrites known commands to cleaner launch commands.

## ESP32 To Host CamComs Workflow

Goal: receive an encrypted instruction from a device and route it into Fiona safely.

```text
ESP32 instruction/event
  -> instruction JSON
  -> CamComs encrypted envelope
  -> base64url transport string
  -> HTTP POST to host receiver
  -> decode_envelope
  -> decrypt_text
  -> sender signature verification
  -> trust store lookup (with expiry check)
  -> ReplayGuard
  -> strict instruction validation
  -> RemoteActionRunner (with ACL check)
  -> audit log
```

Trust and identity files:

```text
~/.config/fiona/camcoms/host.private.json
~/.config/fiona/camcoms/host.public.json
~/.config/fiona/camcoms/esp32.public.json
~/.config/fiona/camcoms/trusted/
```

Important safety behavior:

- untrusted senders are rejected
- expired trust entries are rejected
- tampered ciphertext is rejected
- wrong-recipient envelopes are rejected
- stale or duplicate messages are rejected
- receiver defaults to dry-run unless execution is explicitly enabled
- ACL checks verify sender scope before executing actions
- destructive shell commands are blocked

## ESP32 Pairing Workflow

Goal: securely pair a new ESP32 device with the host.

```text
ESP32 broadcasts pairing request
  -> HTTP POST to host pairing server (port 8090)
  -> contains device_id + public key bundle
  -> PairingManager.submit_request()
  -> fingerprint computed from public key
  -> pending request appears in GUI Pairing tab
  
User approves:
  -> PairingManager.approve_request()
  -> device public key stored in ~/.config/fiona/trusted/
  -> optional expiry set (default 30 days)
  
User denies:
  -> PairingManager.deny_request()
  -> request removed from pending list
```

Pending requests expire automatically after 120 seconds if not acted upon.

## Host Service Workflow

Goal: run Fiona's receiver and optional listener as a longer-lived host process.

```text
fiona host init
  -> config JSON
  -> fiona host status
  -> dependency/key/trust checks
  -> fiona host run
  -> HostService
  -> CamComs receiver ownership
  -> optional QuikTieper listener ownership
```

Systemd path:

```text
fiona host install-service
  -> ~/.config/systemd/user/fiona-host.service
  -> systemctl --user daemon-reload
  -> systemctl --user enable --now fiona-host.service
  -> journalctl --user -u fiona-host.service
```

The generated service is a user service, not a system service. It should run as the desktop user so it can access the correct config, session, and GUI/automation permissions.

The Host tab in the GUI provides live systemd service state monitoring with color-coded status and Start/Stop/Restart/Journal controls.

## PhiConnect Chat Workflow

Goal: computer-to-computer encrypted chat.

```text
sender message body
  -> chat payload JSON
  -> encrypt_message(message_type="chat")
  -> CamComsHttpClient POST
  -> peer receiver
  -> decrypt_text
  -> trusted sender verification (with expiry check)
  -> replay check
  -> chat.log event
  -> recent chat display
```

Local loopback uses the same path:

```text
local identity as peer key -> receiver on 127.0.0.1:5000 -> outbound send to 127.0.0.1:5000
```

## DataClient Research Workflow

Goal: gather topic data into structured table formats.

Quick mining:

```text
topic
  -> DuckDuckGo HTML search
  -> result URL normalization/deduplication
  -> page scrape
  -> paragraph extraction
  -> frequency summarizer
  -> CSV rows
```

Deep research:

```text
seed results
  -> scrape seed pages
  -> collect same-domain links
  -> bounded crawl by depth/page limit
  -> summarize each page
  -> CSV rows with depth and parent URL
```

MiniExcel:

```text
CSV/JSON/SQLite
  -> normalized row list
  -> grid editing
  -> safe formula evaluation
  -> save/export
```

## SeeOnDesk Awareness Workflow

Goal: identify the current desktop context and discover available actions.

```text
fiona seeondesk active/status
  -> kdotool getactivewindow on KDE/Wayland
  -> xdotool/xprop fallback on X11-compatible sessions
  -> process-name lookup
  -> serializable desktop snapshot

fiona --discover-actions
  -> ProcessTracker.list_processes()
  -> WorkspaceWatcher.list_workspaces()
  -> discover_actions()
  -> categorized action list
```

**Process Tracking**:

```text
ProcessTracker
  -> iterates /proc/*/comm
  -> finds processes by name substring
  -> registers/triggers watcher callbacks
  -> no psutil dependency required
```

**Workspace Awareness**:

```text
WorkspaceWatcher
  -> polls workspace state via kdotool (or wmctrl fallback)
  -> detects active workspace changes
  -> fires change callbacks
  -> tracks current workspace ID
```

**Screen Capture**:

```text
capture_screen()
  -> spectacle on KDE (preferred)
  -> grim on generic Wayland
  -> scrot/gnome-screenshot on X11
  -> writes PNG to output path

capture_window(window_id)
  -> kdotool activate target window
  -> scrot -u / gnome-screenshot -w
  -> focused window capture

analyze_screen(prompt)
  -> capture_screen() -> Ollama vision model -> text response
```

## Macro Engine Workflow

Goal: execute multi-step automation with waits, conditions, and branching.

```text
macro steps
  -> variable interpolation (${var} -> value)
  -> wait execution (sleep, wait_for_window, wait_for_process)
  -> condition evaluation (window_active, process_running, action_result)
  -> if condition met: execute action via ActionRouter
  -> if condition not met and fallback set: execute fallback
  -> if condition not met and no fallback: skip step
  -> if action is "GOTO:<name>": branch to other macro (max depth 10)
  -> track results in context for subsequent conditions
```

CLI:

```bash
fiona --run-macro my_macro   # Execute macro
fiona --list-macros          # List all macros
```

## Voice Workflow

Goal: provide voice-based control with speech feedback.

```text
Wake word detected (or push-to-talk pressed)
  -> WakeWordEngine triggers callbacks
  -> optional audio/notification feedback
  -> voice command processing
  -> action execution
```

Wake word detection backends (auto-detected):

```text
pvporcupine (best) -> snowboy -> mycroft_precise -> manual trigger fallback
```

Feedback channels:

```text
audio (aplay/paplay) + desktop notification (notify-send) + status bar text
```

Graceful degradation:

- if no wake word library → manual trigger only (push-to-talk)
- if no pynput → no push-to-talk
- if no sound files → silent feedback
- if no notify-send → visual feedback only

## EyeControl Tracker Workflow

Goal: move the mouse pointer from eye/iris position when a camera feed is available.

```text
fiona eyecontrol run
  -> runtime dependency import
  -> IP camera URL or OpenCV camera index
  -> frame decode
  -> MediaPipe face mesh
  -> iris landmark extraction
  -> screen coordinate scaling
  -> PyAutoGUI pointer movement
  -> optional blink-click
  -> OpenCV preview
```

The subsystem is intentionally optional. `fiona eyecontrol status` can run without camera access and is the first diagnostic command.

## fAT Terminal Workflow

Goal: provide a terminal-first Fiona control surface.

```text
fiona cli
  -> curses command center
  -> sliding pages by workflow
  -> selected one-shot action executes underlying Fiona command
  -> captured stdout/stderr renders inside output panel
  -> external action launches in real terminal/session

fiona fat
  -> collect readiness checks
  -> render btop-style panels

fiona fat layout
  -> generate Zellij KDL
  -> include fAT, Host, CamComs, and SeeOnDesk panes

fiona fat run
  -> write layout file
  -> launch zellij --layout <path>
```

This is currently a sliding command center, terminal dashboard, and workspace helper. It still relies on the existing direct Fiona commands as the execution layer.

## Agent Workflow

Goal: bridge Fiona to a local model server without making the model the authority.

```text
fiona agent commands
  -> command registry and app list

fiona agent status
  -> Ollama health request

fiona agent ask
  -> OpenAI-compatible chat-completions request
  -> local model response
```

The current Agent layer performs inference only. It does not train models, fine-tune models, execute actions automatically, or decide command permissions.

## Browser Automation Workflow

Goal: control a web browser programmatically via Playwright for automation tasks.

```text
fiona browser start
  -> asyncio event loop
  -> Playwright browser launch (chromium/firefox/webkit)
  -> BrowserManager state machine: STOPPED → STARTING → RUNNING
  -> module-level default manager created via get_browser_manager()
  -> optional EventBus publishes BrowserLaunched event

fiona browser navigate <url>
  -> BrowserManager.navigate(url)
  -> default context required
  -> NavigationCompleted event published with status code and final URL

fiona browser click <selector>
  -> BrowserManager.click_element(selector)
  -> timeout-based element wait

fiona browser type <selector> <text>
  -> BrowserManager.type_text(selector, text)
  -> configurable keystroke delay

fiona browser screenshot [--output <path>]
  -> BrowserManager.capture_screenshot(path=path)
  -> returns raw bytes if no path given

fiona browser stop
  -> browser manager closes all contexts
  -> Playwright browser instance closed
  -> state returns to STOPPED
```

### State Machine

```text
                    start()
  STOPPED ──────────────────► STARTING ──────────────► RUNNING
    ▲                            │                        │
    │                            │ (failure)              │ (crash)
    │                            ▼                        ▼
    │                          ERROR ◄───────────────── DEGRADED
    │                            │
    └────────────────────────────┘
         restart() / stop()
```

Valid state transitions:

| Transition | Method | Notes |
|------------|--------|-------|
| STOPPED → STARTING → RUNNING | `start()` | Normal startup sequence |
| RUNNING → STOPPED | `stop()` | Clean shutdown, idempotent |
| RUNNING → ERROR → RUNNING | `restart()` | Auto-restart on crash |
| RUNNING → DEGRADED | (internal) | Reduced-capability state |

### Context Management

Isolated browser contexts can be created for multi-session workflows:

```text
create_context(**kwargs)
  -> IBrowserContext with unique context_id
  -> separate cookies/storage/state
  -> tracks all contexts by ID
  -> published BrowserContextCreated event

close_context(context_id)
  -> removes context from manager
  -> closes browser context
```

### Error Handling

Errors fall into typed exception classes:

| Error | Cause |
|-------|-------|
| `BrowserLaunchError` | Browser process failed to start |
| `BrowserShutdownError` | Browser failed to close cleanly |
| `BrowserNotRunning` | Operation attempted while browser is stopped |
| `BrowserCrashError` | Browser process crashed unexpectedly |
| `ElementNotFound` | CSS selector did not match any element |
| `NavigationTimeout` | Page load exceeded timeout |
| `BrowserTimeout` | Generic operation timeout |

Automatic restart: when a crash is detected during an operation, the manager attempts one auto-restart (`_AUTO_RESTART_ATTEMPTS = 1`). If the restart succeeds, the state transitions back to RUNNING. If it fails, the state stays at ERROR.

## Agent Orchestration Workflow

Goal: have the local LLM plan and execute multi-step tasks with human oversight.

### Think-Act-Observe Loop (AgentOrchestrator)

```text
user goal
  -> AgentOrchestrator.run_goal(goal)
  -> Phase 1: Think / Plan
     -> LLM generates plan steps with action + parameters
     -> each step becomes a PlannedStep with risk assessment
     -> loop until LLM signals done or max_turns reached
  -> Phase 2: Submit for Approval
     -> ApprovalManager.submit_plan() -> plan_id
     -> PlanStatus set to PENDING
     -> human must approve via GUI/API
  -> Phase 3: Wait for Decision
     -> wait_for_approval(timeout=300)
     -> returns 'approved', 'denied', 'cancelled', or 'timeout'
  -> Phase 4: Execute
     -> ApprovalManager.mark_executing(plan_id)
     -> SafeActionRouter checks personality permissions
     -> each action executed via ActionRouter
     -> observation collected for each step
     -> ApprovalManager.mark_completed(plan_id, summary)
  -> result returned to user
```

### ForemanAgent Flow (Complex Tasks)

For tasks that require decomposition into sub-goals:

```text
user goal
  -> ComplexityAssessor classifies complexity
  -> Simple query: single SubAgent directly (no planning overhead)
  -> Moderate/complex task:
     -> TaskPlan.from_llm() decomposes into sub-goals
     -> sub-goals executed in topological order
     -> parallel sub-goals run concurrently when possible
     -> each sub-goal is a self-contained unit with its own SubAgent
     -> results synthesized into a final response
```

The foreman flow is accessible via:

```bash
fiona agent ask --model <model-id> "complex multi-step request"
```

Or programmatically:

```python
from Agent.orchestration import ForemanAgent

foreman = ForemanAgent(client, registry, chat_store)
response = foreman.execute(goal="Research topic and save results")
```

### Permission Gating

Every action executed by the agent passes through `PermissionEnforcer`, which checks the action name against the active personality's `allowed_tools`. If the personality has restricted tool access, disallowed actions raise `AgentPermissionError` before execution.

```text
action name + personality
  -> PermissionEnforcer.assert_tool_allowed()
  -> SafeActionRouter.run()
  -> ActionRouter.run()
  -> result
```

## Web UI Dashboard Workflow

Goal: provide a browser-based SPA dashboard for monitoring and controlling Fiona.

### Architecture

```text
browser SPA (React/Vue/Svelte)
  -> HTTP requests to aiohttp server (port 8765)
  -> WebSocket connection at /ws
  -> SSE stream at /api/v1/stream

aiohttp server (fionaLocalPages/server/app.py)
  -> REST API at /api/v1/
  -> WebSocket manager for real-time push
  -> SSE endpoint for server-sent events
  -> static file server with SPA fallback for client-side routing
```

### REST API

```text
/api/v1/
  ├── health              GET    -> server health check
  ├── system/
  │   ├── status          GET    -> full system status
  │   └── metrics         GET    -> CPU/memory/disk metrics
  ├── agent/
  │   ├── ask             POST   -> query the LLM
  │   ├── goal            POST   -> run agent goal
  │   ├── status          GET    -> Ollama health
  │   └── commands        GET    -> agent-accessible commands
  ├── actions/
  │   ├── list            GET    -> registered actions
  │   ├── run             POST   -> execute an action
  │   └── history         GET    -> action trace log
  ├── voice/
  │   ├── parse           POST   -> parse voice command
  │   └── transcribe      POST   -> transcribe audio
  ├── terminal/
  │   ├── exec            POST   -> run terminal command
  │   └── status          GET    -> terminal availability
  ├── files/
  │   ├── list            GET    -> list files
  │   ├── read            GET    -> read file content
  │   ├── write           POST   -> write to file
  │   └── info            GET    -> file metadata
  ├── config/
  │   ├── ...             GET    -> list configs
  │   ├── {name}          GET    -> read config
  │   └── {name}          PUT    -> update config
  ├── browser/
  │   ├── start           POST   -> start browser
  │   ├── stop            POST   -> stop browser
  │   ├── status          GET    -> browser state
  │   ├── navigate        POST   -> navigate to URL
  │   ├── click           POST   -> click element
  │   └── screenshot      POST   -> capture screenshot
  ├── desktop/
  │   ├── active          GET    -> active window info
  │   └── snapshot        GET    -> full desktop snapshot
  ├── recall/
  │   ├── search          GET    -> search memory store
  │   ├── remember        POST   -> save to memory
  │   └── forget/{key}    DELETE -> remove from memory
  ├── macros/
  │   ├── ...             GET    -> list macros
  │   └── run             POST   -> execute macro
  └── camcoms/
      ├── status          GET    -> CamComs status
      └── identity        GET    -> CamComs identity
```

### WebSocket Real-Time Push

```text
SPA connects to /ws
  -> WebSocketManager.register(ws) -> peer_id
  -> periodic heartbeat (30s interval) detects stale connections
  
Server pushes:
  -> system:metrics every 2 seconds (CPU, memory, disk, load, uptime)
  -> browser events (BrowserLaunched, NavigationCompleted, BrowserCrashed)
  
Client sends:
  -> JSON-RPC 2.0 method calls
  -> ping/pong heartbeats
```

### SSE (Server-Sent Events)

```text
SPA connects to /api/v1/stream
  -> Content-Type: text/event-stream
  -> 30-second heartbeat keepalive
  -> lightweight alternative to WebSocket for one-way updates
```

### Data Flow

```text
SPA user action
  -> HTTP POST /api/v1/{resource}/{action}
  -> aiohttp handler imports Fiona Python module
  -> operation executed against real subsystem
  -> JSON response returned to SPA
  -> WebSocket push broadcasts state changes to all connected peers
  -> SPA re-renders with updated data
```

## Debugging Workflow

When a system operation fails, identify the failing layer before changing code:

1. CLI parse/import failure: run `python3 -m fiona.cli --help`.
2. Config failure: inspect the target JSON path and run list/status commands.
3. Crypto failure: use `camcoms smoke-test`, then verify key paths and trust.
4. Transport failure: verify receiver host/port, firewall, and connection-refused errors.
5. Execution failure: keep receiver dry-run first, then inspect allowed actions.
6. Shell blocked: check `FionaCore.shell_safety` — command may match a destructive pattern.
7. GUI failure: verify Tkinter/display availability and reproduce through CLI where possible.
8. Service failure: inspect `fiona host status` and `fiona host logs`.
9. Pairing failure: ensure pairing server is running on port 8090 and ESP32 can reach it.
10. Macro failure: run `fiona --list-macros` to verify macro name and step count.
