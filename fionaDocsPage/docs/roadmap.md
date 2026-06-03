# Roadmap

This roadmap focuses on what Fiona still needs to become a JARVIS-style host, excluding the AI agent itself.

## Near Term

- Service controls: add easier enable, disable, restart, and status wrappers around the generated user systemd service.
- GUI Host controls: add live receiver start/stop, listener start/stop, connected-device state, last-message view, and service logs.
- PhiConnect hardening: improve peer setup, key fingerprints, and visible encryption state.
- DataClient polish: improve table editing, export flows, and miner status reporting.
- SeeOnDesk expansion: expose richer active-app data for command routing.

## Communication

- Implement the ESP32 crypto adapter for X25519, HKDF-SHA256, AES-GCM, Ed25519, and base64url encoding.
- Add ESP32 hardware validation.
- Add Wi-Fi provisioning, retries, acknowledgements, reconnect behavior, and queueing.
- Add a real pairing flow with fingerprint approval, trusted-key installation, host public-key provisioning, key rotation, and device removal UX.
- Add encrypted replies from the host back to trusted devices.

## Control And Automation

- Add sender-specific permissions.
- Add a named command registry.
- Expand macros with waits, conditions, window targeting, branching, and per-step failure handling.
- Add clearer success/failure result objects for remote actions.
- Add safety prompts for risky actions.

## Awareness And Feedback

- Add screen capture and visual recognition to SeeOnDesk.
- Add command history search.
- Add desktop notifications, status overlay, tray controls, and spoken responses.
- Add voice input through push-to-talk or wake-word flow.

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
