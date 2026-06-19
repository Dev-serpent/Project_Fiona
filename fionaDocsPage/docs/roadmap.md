# Roadmap

This roadmap focuses on what Fiona still needs to become a JARVIS-style host, excluding the AI agent itself.

## Near Term

- [DONE] Service controls: add easier enable, disable, restart, and status wrappers around the generated user systemd service.
- [DONE] GUI Host controls: add live receiver start/stop, listener start/stop, connected-device state, last-message view, and service logs.
- [DONE] PhiConnect hardening: improve peer setup, key fingerprints, and visible encryption state.
- DataClient polish: improve table editing, export flows, and miner status reporting.
- [DONE] SeeOnDesk expansion: expose richer active-app data for command routing with process tracking and workspace awareness.

## Communication

- [DONE] Implement the ESP32 crypto adapter for X25519, HKDF-SHA256, AES-GCM, Ed25519, and base64url encoding.
- Add ESP32 hardware validation.
- Add Wi-Fi provisioning, retries, acknowledgements, reconnect behavior, and queueing.
- [DONE] Add a real pairing flow with fingerprint approval, trusted-key installation, host public-key provisioning, key rotation, and device removal UX.
- Add encrypted replies from the host back to trusted devices.

## Control And Automation

- [DONE] Add sender-specific permissions (ACL system).
- [DONE] Add a named command registry.
- [DONE] Expand macros with waits, conditions, window targeting, branching, and per-step failure handling.
- [DONE] Add clearer success/failure result objects for remote actions.
- [DONE] Add safety prompts for risky actions (verification prompts).
- [DONE] Add shell command safety (block destructive commands).

## Awareness And Feedback

- [DONE] Add screen capture and visual recognition to SeeOnDesk.
- Add command history search.
- [DONE] Add desktop notifications, tray controls, and spoken responses.
- [DONE] Add voice input through push-to-talk or wake-word flow.
- [DONE] Add system tray icon with state indicators.

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
