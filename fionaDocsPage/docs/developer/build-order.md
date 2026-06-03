# Build Order

This is the current implementation order from the developer notes.

1. Done: unified Fiona config at `~/.config/fiona/config.json` for QuikTieper path, CamComs key paths, trusted directory, receiver host/port, dry-run mode, allowed actions, replay path, and audit log.
2. Done: host service skeleton through `fiona host init/status/run`.
3. Done: service health checks verify config, key files, trusted dir, `ydotool`, `kdotool`, listener import, audit/replay dirs, and receiver port binding when requested.
4. Done: CamComs receiver integration is owned by `HostService.run`.
5. Done: QuikTieper listener can be owned by the host service through `start_quiktieper_listener`.
6. Done: remote action router connects decrypted CamComs instructions to configured QuikTieper actions with `execute_remote_actions` and `allowed_remote_actions`.
7. Done: standalone encrypted computer-to-computer chat exists through PhiConnect.
8. Partial: GUI Host tab shows config, health status, trusted keys, logs, and paths; live receiver process controls still need expansion.
9. Done: command history and audit log record accepted/rejected host message processing and are visible through CLI/GUI.
10. Done: trusted device manager can list, add, remove, and inspect stored sender public key JSON.
11. Partial: configurable macro layer supports structured multi-step remote actions; waits, conditions, window targeting, named macros, and per-step failure handling remain.
12. Partial: local structured success/failure result objects exist; response messages to sender and local notifications still remain.
13. Not started: desktop tray and background status.
14. Blocked by ESP32 work: real crypto adapter for X25519, HKDF-SHA256, AES-GCM, Ed25519, and base64url decode in firmware.
15. Not started: ESP32 pairing flow.
16. Not started: voice and speech interface.
17. Partial: desktop awareness through SeeOnDesk active-window snapshots; screen recording and ML recognition remain.
