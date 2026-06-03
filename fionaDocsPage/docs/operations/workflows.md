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
  -> trust store lookup
  -> ReplayGuard
  -> strict instruction validation
  -> RemoteActionRunner
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
- tampered ciphertext is rejected
- wrong-recipient envelopes are rejected
- stale or duplicate messages are rejected
- receiver defaults to dry-run unless execution is explicitly enabled

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

## PhiConnect Chat Workflow

Goal: computer-to-computer encrypted chat.

```text
sender message body
  -> chat payload JSON
  -> encrypt_message(message_type="chat")
  -> CamComsHttpClient POST
  -> peer receiver
  -> decrypt_text
  -> trusted sender verification
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

Goal: identify the current desktop context.

```text
fiona seeondesk active/status
  -> kdotool getactivewindow on KDE/Wayland
  -> xdotool/xprop fallback on X11-compatible sessions
  -> process-name lookup
  -> serializable desktop snapshot
```

The current implementation is metadata-based. Screen recording and ML classification are future work.

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
  -> LM Studio health request

fiona agent ask
  -> OpenAI-compatible chat-completions request
  -> local model response
```

The current Agent layer performs inference only. It does not train models, fine-tune models, execute actions automatically, or decide command permissions.

## Debugging Workflow

When a system operation fails, identify the failing layer before changing code:

1. CLI parse/import failure: run `python3 -m fiona.cli --help`.
2. Config failure: inspect the target JSON path and run list/status commands.
3. Crypto failure: use `camcoms smoke-test`, then verify key paths and trust.
4. Transport failure: verify receiver host/port, firewall, and connection-refused errors.
5. Execution failure: keep receiver dry-run first, then inspect allowed actions.
6. GUI failure: verify Tkinter/display availability and reproduce through CLI where possible.
7. Service failure: inspect `fiona host status` and `fiona host logs`.
