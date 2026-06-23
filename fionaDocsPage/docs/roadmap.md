# Roadmap

This roadmap focuses on what Fiona still needs to become a JARVIS-style host, excluding the AI agent itself.

## Near Term

- DataClient polish: improve table editing, export flows, and miner status reporting.

## Communication

- Add ESP32 hardware validation.
- Add Wi-Fi provisioning, retries, acknowledgements, reconnect behavior, and queueing.
- Add encrypted replies from the host back to trusted devices.

## Control And Automation

- Add command history search.

## Awareness And Feedback

- (All items completed — see Completed section below.)

## Packaging

- Stabilize console-script installation.
- Add per-platform dependency guidance.
- Add release packaging.
- Document Linux/KDE/Wayland support boundaries and graceful fallbacks.

## Holography

- Add saved Vsee scenes.
- Add richer primitives.
- Add camera presets and animation.
- Add live data binding.
- Investigate real projection or hologram output paths.

## Browser Automation

- Harden browser automation: advanced interaction patterns (forms, iframes, multi-tab), robust wait strategies, and error recovery.
- Add headless mode configuration and user-data-dir support.
- Add browser-level network intercept and request mocking.
- Add session recording and replay capabilities.

## Web UI

- Production readiness for fionaLocalPages: error boundaries, loading states, offline degradation, and accessibility audit.
- Add remaining pages: Vsee viewer, PhiConnect chat, Macros editor, full Notifications center.
- Add user authentication (local-only token or PIN).
- Add theming support and customizable layouts.

## Agent Orchestration

- Improve think-act-observe loop reliability: better error recovery, tool-use retry, and context window management.
- Multi-agent coordination: parallel goals, agent handoff, and shared memory via RecallVault.
- Add plan persistence and interruption/resume capability.
- Tighten permission enforcement and approval workflow integration.

## Completed

These items have been implemented and are no longer pending:

### Near Term

- Service controls: add easier enable, disable, restart, and status wrappers around the generated user systemd service.
- GUI Host controls: add live receiver start/stop, listener start/stop, connected-device state, last-message view, and service logs.
- PhiConnect hardening: improve peer setup, key fingerprints, and visible encryption state.
- SeeOnDesk expansion: expose richer active-app data for command routing with process tracking and workspace awareness.

### Communication

- Implement the ESP32 crypto adapter for X25519, HKDF-SHA256, AES-GCM, Ed25519, and base64url encoding.
- Add a real pairing flow with fingerprint approval, trusted-key installation, host public-key provisioning, key rotation, and device removal UX.

### Control And Automation

- Add sender-specific permissions (ACL system).
- Add a named command registry.
- Expand macros with waits, conditions, window targeting, branching, and per-step failure handling.
- Add clearer success/failure result objects for remote actions.
- Add safety prompts for risky actions (verification prompts).
- Add shell command safety (block destructive commands).

### Awareness And Feedback

- Add screen capture and visual recognition to SeeOnDesk.
- Add desktop notifications, tray controls, and spoken responses.
- Add voice input through push-to-talk or wake-word flow.
- Add system tray icon with state indicators.
- Add command history search.
