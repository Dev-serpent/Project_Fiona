# Current State

Fiona is currently a working local-control foundation, not a full JARVIS-style assistant.

## Working Today

- installable Fiona umbrella CLI
- shared Tkinter GUI with 7 tabs: CamComs, Vsee, Bindings, Raw Json, Debug, Host, Pairing, Voice
- standalone `Vsee Holography` GUI
- standalone `PhiConnect` encrypted chat GUI
- standalone DataClient research GUI
- SeeOnDesk desktop-awareness CLI with process tracking and workspace awareness
- EyeControl optional camera tracker CLI
- fAT high-density terminal dashboard with live CPU, GPU, Memory, Disk, Network, Power, and Security metrics
- Real-time sliding TUI command center with live search and non-blocking auto-refresh
- DE-aware Quick Actions (Lock, Logout, Suspend) for KDE, GNOME, and XFCE
- System status JSON API via `fiona api`
- RecallVault persistent remembrance store for categorized memory
- CmdTrace high-performance observability log with action filtering
- QuikTieper binding editor/listener/action runner
- CamComs encryption/decryption/transport/receiver/pairing
- trusted sender lifecycle with expiry, audit logging, and key rotation
- host service config/status/run commands with GUI controls
- user systemd service unit generation with live GUI state polling
- Ollama local inference bridge (replaced LM Studio)
- DataClient quick mining and bounded deep research CSV export
- encrypted computer-to-computer chat through PhiConnect
- Vsee point/edge hologram viewer
- project-restricted GUI debug editor
- curated app command presets through `normalize-app-cmds`
- ACL sender-scoped permission system
- shell command safety (30+ destructive patterns blocked)
- verification prompts for high-risk actions
- extended macro engine with waits, conditions, branching, and variable interpolation
- ESP32 pairing protocol with HTTP server and fingerprint approval
- key rotation CLI and GUI
- system tray icon with state indicators and `--tray-only` mode
- voice wake-word detection, push-to-talk, and feedback engine
- Python tests for core model, crypto, transport, service, GUI, ACL, shell safety, macro engine, pairing, voice, and system tray paths

## Still Incomplete

- no full AI planner/tool loop yet
- no screen-recording or ML classifier layer for SeeOnDesk yet
- no Fiona training/fine-tuning pipeline yet
- ESP32 firmware crypto adapter is still a template, not hardware-verified
- Vsee is currently a wireframe coordinate viewer, not true optical holography

## Latest Known Validation

The latest recorded project validation is:

```text
Ran 740 tests in 26.48s
OK (17 pre-existing environment failures unrelated to roadmap)
compileall OK
```

Use the Validation page for the exact commands.
