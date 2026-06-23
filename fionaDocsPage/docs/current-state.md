# Current State

Fiona is currently a working local-control foundation, not a full JARVIS-style assistant.

## Working Today

- installable Fiona umbrella CLI
- shared Tkinter GUI with 7 tabs: CamComs, Vsee, Bindings, Raw Json, Debug, Host, Pairing, Voice
- standalone `Vsee Holography` GUI
- standalone `PhiConnect` encrypted chat GUI
- standalone DataClient research GUI
- SeeOnDesk desktop-awareness CLI with process tracking, workspace awareness, and screen capture
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
- Agent orchestration with think-act-observe loop, chat, command registry, permissions, personality, and query detection
- FionaCore approval system for agent action plans (pending/approve/deny with reason)
- PhiConnect foreman_handler integration for multi-agent orchestration
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
- BrowserAutomation module with Playwright lifecycle manager (start, stop, navigate, click, type, screenshot)
- fionaLocalPages SPA web frontend with REST API + WebSocket + SSE real-time updates
- Python tests for core model, crypto, transport, service, GUI, ACL, shell safety, macro engine, pairing, voice, system tray, and browser automation paths

## Still Incomplete

- no full AI planner/tool loop yet (Agent has think-act-observe but no long-term planning)
- no screen-recording or ML classifier layer for SeeOnDesk yet
- no Fiona training/fine-tuning pipeline yet
- ESP32 firmware crypto adapter is still a template, not hardware-verified
- Vsee is currently a wireframe coordinate viewer, not true optical holography
- Web UI still evolving — some pages and workflows are partial
- BrowserAutomation has basic lifecycle but no advanced interaction patterns (forms, frames, wait strategies)
- Agent orchestration maturity — multi-agent coordination, tool-use reliability, and error recovery still being hardened

## Latest Known Validation

The latest recorded project validation is:

```text
1598 tests across Python and JavaScript:
  Python:   1413 passed (pytest)
  CAD JS:    87 passed (vitest)
  CAD Srv:   98 passed (pytest)
  compileall OK

14 pre-existing environment failures unrelated to roadmap
```

Use the Validation page for the exact commands.
