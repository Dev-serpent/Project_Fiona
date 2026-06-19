# Build Order

This is the current implementation order from the developer notes.

1. Done: unified Fiona config at `~/.config/fiona/config.json` for QuikTieper path, CamComs key paths, trusted directory, receiver host/port, dry-run mode, allowed actions, replay path, and audit log.
2. Done: host service skeleton through `fiona host init/status/run`.
3. Done: service health checks verify config, key files, trusted dir, `ydotool`, `kdotool`, listener import, audit/replay dirs, and receiver port binding when requested.
4. Done: CamComs receiver integration is owned by `HostService.run`.
5. Done: QuikTieper listener can be owned by the host service through `start_quiktieper_listener`.
6. Done: remote action router connects decrypted CamComs instructions to configured QuikTieper actions with `execute_remote_actions` and `allowed_remote_actions`.
7. Done: standalone encrypted computer-to-computer chat exists through PhiConnect.
8. Done: GUI Host tab shows config, health status, trusted keys, logs, paths, live systemd state, and SeeOnDesk workspace/process info.
9. Done: command history and audit log record accepted/rejected host message processing and are visible through CLI/GUI.
10. Done: trusted device manager can list, add, remove, inspect stored sender public key JSON, and enforce expiry.
11. Done: configurable macro layer supports structured multi-step remote actions with waits, conditions, branching, fallback actions, variable interpolation, and GOTO support.
12. Done: local structured success/failure result objects exist; ACL checks and verification prompts protect sensitive actions.
13. Done: desktop tray icon with state indicators and `--tray-only` mode.
14. Blocked by ESP32 work: real crypto adapter for X25519, HKDF-SHA256, AES-GCM, Ed25519, and base64url decode in firmware.
15. Done: ESP32 pairing flow with fingerprint approval, trusted-key installation, key rotation, and device removal UX.
16. Done: voice subsystem with wake word detection, push-to-talk, and feedback engine.
17. Done: desktop awareness through SeeOnDesk with active-window snapshots, process tracking, and workspace awareness; screen recording and ML recognition remain.
18. Done: ACL sender-scoped permission system.
19. Done: shell command safety (30+ destructive patterns blocked at all 5 shell execution points).
20. Done: private file permission enforcement for key material.
21. Done: trust store expiry with auto-prune and backward-compatible format.
22. Done: key rotation with atomic writes and confirmation prompt.
23. Done: system tray icon with color-coded state and right-click menu.
