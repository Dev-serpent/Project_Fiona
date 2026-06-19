# CLI Mechanics

Fiona's command line is the operational spine of the project. The installed command is `fiona`; from a source checkout the equivalent form is:

```bash
python3 -m fiona.cli <command>
```

The CLI is implemented in `fiona/cli.py` with `argparse`. It is an umbrella dispatcher: the top-level parser owns cross-subsystem command groups, while QuikTieper shortcuts are delegated into `QuikTieper.cli`.

## Dispatch Model

Startup flow:

1. `main()` receives `sys.argv[1:]`.
2. `_normalize_help_args()` converts `fiona help` and `fiona <group> help` into `--help`.
3. `_should_delegate_to_quiktieper()` sends legacy direct commands such as `edit`, `run`, `list`, `init`, `import-apps`, `assign-keys`, and `normalize-app-cmds` into QuikTieper.
4. Explicit `fiona quiktieper ...` and `fiona qt ...` also delegate into QuikTieper.
5. Other groups are parsed by Fiona's umbrella parser and routed by `args.layer`.

This preserves backward compatibility with the original launcher commands while allowing newer subsystems to live under dedicated groups.

## Top-Level Command Grid

| Command | Owner | Purpose | Runtime Type |
| --- | --- | --- | --- |
| `fiona edit` | QuikTieper GUI | Opens the shared Fiona editor | foreground GUI |
| `fiona run` | QuikTieper listener | Starts global chord listener | foreground service |
| `fiona list` | QuikTieper config | Prints configured bindings | one-shot |
| `fiona quiktieper ...` / `fiona qt ...` | QuikTieper | Explicit launcher layer commands | mixed |
| `fiona camcoms ...` / `fiona cc ...` | CamComs | Crypto, transport, receiver, trust, audit, pairing, key rotation | mixed |
| `fiona host ...` | CamComs HostService | Unified service config/lifecycle/logs | mixed |
| `fiona agent ...` | Agent | Ollama bridge and command registry | one-shot |
| `fiona dataclient ...` / `fiona data ...` | DataClient | Research mining, conversion, GUI | mixed |
| `fiona eyecontrol ...` / `fiona eye ...` | EyeControl | Optional camera-based eye-controlled mouse tracker | mixed |
| `fiona fat ...` / `fiona terminal-assist ...` | TerminalAssist | btop-style dashboard and Zellij layout helper | mixed |
| `fiona cli` | TerminalAssist | sliding terminal command center | foreground TUI |
| `fiona api` | TerminalAssist | Short for 'fiona fat api' | one-shot JSON |
| `fiona recall ...` | RecallVault | Small persistent remembrance store | one-shot |
| `fiona action ...` | CmdTrace | Action trace logging and observability | one-shot |
| `fiona run-shell ...` | fiona | Internal helper to run shell commands (with safety checks) | one-shot |
| `fiona seeondesk ...` / `fiona sod ...` | SeeOnDesk | Active desktop/window identification, process tracking, workspace awareness | one-shot |
| `fiona vsee` | Vsee | Standalone holography viewer | foreground GUI |
| `fiona phiconnect` | PhiConnect | Standalone encrypted chat | foreground GUI |
| `fiona --run-macro <name>` | FionaCore | Execute a named macro with the extended engine | one-shot |
| `fiona --list-macros` | FionaCore | List all macros and step counts | one-shot |
| `fiona --discover-actions` | SeeOnDesk | Discover available actions from system state | one-shot |
| `fiona --tray-only` | QuikTieper | Run system tray icon only (no GUI window) | foreground service |
| `fiona voice wake-test` | Voice | Test wake word detection | one-shot |
| `fiona voice feedback-test` | Voice | Test audio/notification feedback | one-shot |

## QuikTieper Delegated Commands

These commands are parsed by `QuikTieper.cli` after Fiona rewrites `sys.argv`:

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

Operational mechanics:

- `init` creates the default bindings file if missing.
- `list` loads the JSON config, parses apps and shortcuts, and prints the effective binding list.
- `import-apps` scans Linux desktop launcher locations and adds discovered apps with no launch keys unless configured otherwise.
- `normalize-app-cmds` rewrites known app commands to curated direct launch commands while keeping viable local fallbacks.
- `assign-keys` fills missing app launch chords using `alt` plus generated safe letters, avoiding duplicate key sets.
- `run` starts the chord listener and remains active until interrupted.
- `edit` launches the shared Tkinter editor.

Default bindings path:

```text
~/.config/fiona/bindings.json
```

## CamComs Commands

CamComs commands operate on identities, encrypted envelopes, HTTP transport, trust state, receiver processing, pairing, key rotation, and audit logs.

| Command | Reads | Writes | Notes |
| --- | --- | --- | --- |
| `camcoms keygen` | none | private/public identity JSON | defaults to `~/.config/fiona/camcoms/` |
| `camcoms public` | private identity JSON | public bundle JSON | extracts shareable public keys |
| `camcoms paths` | constants | stdout | prints visible key/trust paths |
| `camcoms trust --public` | public bundle JSON | trusted sender directory | sender must be trusted before receiver accepts it |
| `camcoms trust --list` | trusted sender directory | stdout | lists trusted public bundles |
| `camcoms trust --remove` | trusted sender directory | trusted sender directory | removes by device id |
| `camcoms trust --expires-in <days>` | public bundle JSON | trusted sender directory | adds sender with automatic expiry |
| `camcoms encrypt` | sender private, recipient public | stdout | prints encoded envelope or JSON envelope |
| `camcoms decrypt` | recipient private, optional sender public | stdout | verifies sender when supplied |
| `camcoms send` | encoded message or envelope JSON | network POST | sends compact encoded envelope |
| `camcoms compose-send` | keys and instruction args | network POST | encrypts and sends in one operation |
| `camcoms receive` | host private, trusted dir | HTTP receiver | foreground server |
| `camcoms audit` | audit log | stdout | prints recent receiver events |
| `camcoms smoke-test` | generated in-memory keys | stdout | no persistent files |
| `camcoms rotate-keys` | existing identity | new identity + pubkey | atomic key rotation with confirmation |
| `camcoms prune` | trusted sender directory | trusted sender directory | removes expired trust entries |
| `camcoms fingerprint` | identity JSON | stdout | prints public key fingerprint |

The envelope path is:

```text
instruction JSON -> encrypted envelope dict -> base64url JSON string -> HTTP body
```

The decrypt path reverses that and optionally verifies the sender public key.

### Key Rotation

```bash
fiona camcoms rotate-keys       # Requires confirmation
fiona camcoms rotate-keys --yes # Skip confirmation
```

Prints old and new fingerprints. Existing trusted senders will need to re-pair.

### Prune Expired Trust

```bash
fiona camcoms prune              # Remove all expired trust entries
fiona camcoms prune --trusted-dir <dir>
```

### Show Fingerprint

```bash
fiona camcoms fingerprint
fiona camcoms fingerprint --identity ~/.config/fiona/identity.json
```

## Host Service Commands

`fiona host ...` and `fiona camcoms service ...` call the same service implementation.

```bash
fiona host init
fiona host status --check-port
fiona host run
fiona host install-service --print
fiona host install-service
fiona host enable
fiona host restart
fiona host logs --lines 120
fiona host stop
fiona host disable
```

Service config path:

```text
~/.config/fiona/config.json
```

Mechanics:

- `init` writes a `HostServiceConfig` JSON file.
- `status` loads the config and reports readiness checks for key files, trusted directory, audit/replay paths, listener imports, desktop tools, and optional port bindability.
- `run` constructs `HostService`, loads host identity, starts receiver ownership, and can optionally own the QuikTieper listener.
- `install-service` writes or prints a user systemd unit running `python -m fiona.cli host run`.
- `enable`, `disable`, `restart`, and `stop` call `systemctl --user`.
- `logs` calls `journalctl --user -u <service>`.

## Agent Commands

Agent currently bridges to Ollama's local API (replaced LM Studio).

```bash
fiona agent status
fiona agent ask --model <model-id> "Prompt text"
fiona agent commands
```

Mechanics:

- `status` checks the configured base URL, defaulting to `http://localhost:11434/v1`.
- `ask` constructs a chat-completions request with system prompt, temperature, max tokens, and model id.
- `commands` exposes an agent-readable registry of Fiona actions and available QuikTieper apps.

## DataClient Commands

```bash
fiona dataclient
fiona dataclient gui
fiona dataclient mine "topic" --out ./research.csv --max-links 30
fiona dataclient deep "topic" --out ./deep.csv --seed-links 10 --depth 1 --page-limit 50
fiona dataclient convert ./research.csv --out ./research.json
fiona dataclient view ./research.csv --limit 5
```

Mechanics:

- no subcommand opens the GUI by default
- `mine` searches, scrapes, summarizes, and exports rows
- `deep` performs bounded same-domain crawling unless `--cross-domain` is set
- `convert` normalizes table data between CSV, JSON, and SQLite
- `view` loads the table and prints a JSON preview

## SeeOnDesk Commands

```bash
fiona seeondesk active
fiona seeondesk status
```

Mechanics:

- `active` returns focused window/app metadata.
- `status` wraps active-window data with session and desktop state.
- KDE/Wayland prefers `kdotool`; X11-compatible fallback uses `xdotool` and `xprop`.

### Action Discovery

```bash
fiona --discover-actions
```

Prints all discoverable actions grouped by category (process, workspace, window), showing action name, description, and whether confirmation is required.

## Voice Commands

```bash
fiona voice wake-test      # Test wake word detection availability
fiona voice feedback-test  # Test audio and notification feedback
```

## Macro Engine Commands

```bash
fiona --run-macro <name>   # Execute a named macro with the extended engine
fiona --list-macros        # Print all macros and step counts
```

The macro engine supports waits, conditions, branching, and variable interpolation. See the [FionaCore module page](../modules/fionacore.md) for details.

## System Tray

```bash
fiona --tray-only  # Start system tray icon without the GUI window
```

Useful for autostart scripts. The tray icon shows a color-coded status indicator and provides right-click access to Show Fiona and Quit Fiona.

## EyeControl Commands

```bash
fiona eyecontrol status
fiona eyecontrol run --url http://192.168.0.103:8080/shot.jpg
fiona eyecontrol run --camera-index 0
fiona eyecontrol run --camera-index 0 --no-click
```

Mechanics:

- `status` checks optional dependency availability without opening a camera.
- `run` imports OpenCV, MediaPipe, PyAutoGUI, NumPy, and Requests only at runtime.
- `--url` reads frames from an IP camera snapshot endpoint.
- `--camera-index` reads frames from a local OpenCV camera.
- `--no-click` disables blink-clicking for safer pointer-only testing.

## fAT Commands

```bash
fiona cli
fiona cli --preview
fiona fat status
fiona api
fiona fat api
fiona fat run
```

Mechanics:
- `fiona cli` opens the sliding curses command center with a non-blocking 1-second auto-refresh and live search.
- `status` prints a high-density terminal dashboard with live CPU, memory, disk, network, power, and security metrics.
- `fiona api` (or `fat api`) prints the comprehensive machine-readable system status.
- `run` writes the Zellij layout and launches the workspace.

## RecallVault Commands

```bash
fiona recall remember <key> <value> --category <cat>
fiona recall search <query>
fiona recall forget <key>
fiona recall categories
fiona recall clear
```

Mechanics:
- `remember` saves or replaces a key-value snippet.
- `search` filters stored entries by key, value, or category.
- `forget` removes a single entry by key.
- `categories` lists all unique categories in the vault.
- `clear` deletes the entire remembrance store.

## CmdTrace Commands

```bash
fiona action history --limit 50
fiona action history --name host.status
fiona action clear
```

Mechanics:
- `history` reads the append-only JSONL log of routed actions.
- `--name` filters the history to show only events for a specific action.
- `clear` deletes the command trace log file.

## Failure Modes

| Symptom | Likely Layer | First Check |
| --- | --- | --- |
| `No module named fiona` | install/import path | run from repo root with `python3 -m fiona.cli --help` or install with `pip install -e .` |
| `fiona: command not found` | shell PATH | use module form or activate the environment where Fiona was installed |
| GUI does not open | Tk/display/session | verify `tkinter` and active desktop session |
| listener does not press/click | QuikTieper runtime backend | verify `pynput`, `ydotoold`, `kdotool`, and Wayland permissions |
| receiver rejects message | CamComs trust/crypto/replay | inspect `camcoms audit`, sender trust, timestamps, and duplicate message id |
| PhiConnect send fails | peer setup or listener | verify peer public key and receiver on host/port |
| DataClient search fails | network/search target | verify network access and output path permissions |
| EyeControl cannot start | optional dependency/camera feed | run `fiona eyecontrol status`, then verify camera URL or local camera index |
| fAT cannot launch Zellij | missing terminal multiplexer | run `fiona fat json` and verify `zellij_path` |
| Shell command blocked | FionaCore shell safety | check if the command matches a destructive pattern; use safe alternatives |
| Pairing server won't start | port conflict | verify port 8090 is available or stop the existing pairing server |
| Macro not found | macro config | run `fiona --list-macros` to verify the macro name |
