# Security

Fiona's security-sensitive code spans CamComs, PhiConnect, FionaCore, and the shell execution layer.

## Existing Protections

### Transport Security

- X25519 public/private key agreement
- HKDF-SHA256 message key derivation
- AES-GCM authenticated encryption
- Ed25519 sender signatures
- public bundles for sharing only public identity data
- trusted sender public-key storage
- replay protection for duplicate or stale envelopes
- strict JSON instruction validation
- host receiver dry-run mode by default
- allowlisted remote actions
- optional passphrase encryption for private key JSON
- audit log for accepted and rejected receiver events

### Access Control (ACL)

The `FionaCore.acl` module provides sender-scoped permission rules:

- `SenderACLRule`: maps sender identity patterns to scope levels
- `resolve_sender_profile()`: classifies senders as `local`, `ssh`, `websocket`, or `ble`
- `resolve_sender_scope()`: checks whether a sender has permission for a given action
- Built-in default rules: local full access → agent limited → any other denied
- Integration with `ActionRouter.run()` for automatic checking

Actions can declare required `sender_scope` (e.g., `"safe"`, `"full"`) and `requires_confirmation`.

### Shell Command Safety

The `FionaCore.shell_safety` module blocks destructive shell commands at **all 5 shell execution points**:

Protected patterns include:

| Pattern | Example Blocked |
|---------|----------------|
| `rm -rf /` | `rm -rf /` and variants (`rm -rf /*`, `rm -rf / --no-preserve-root`) |
| Disk wipe | `mkfs`, `dd if=/dev/zero`, `wipefs`, `mkfs`, `fdisk`, `parted` |
| Raw block writes | `dd` + `/dev/sd`, `/dev/nvme`, `/dev/mmcblk` |
| Dangerous redirects | `> /dev/sd`, `> /dev/nvme` |
| Permission escalation | `chmod 777 /etc/shadow`, `chmod 777 /etc/sudoers` |
| System destruction | `shutdown -h now`, `poweroff`, `halt` |
| Package destruction | `apt remove essential`, `dpkg --purge`, `pacman -Rsc` |
| Remote pipe-to-shell | `curl .+ \| bash`, `wget .+ \| sh` |
| Fork bombs | `:(){ :\|:& };:` |
| Reset/format | `reset`, `dd if=/dev/urandom` |

Wrapped execution points:

- `fiona/cli.py` (`run-shell` command → `safe_os_system`)
- `TerminalAssist/gui.py` (shell action execution → `safe_os_system` + error dialog)
- `TerminalAssist/tui.py` (shell action execution → `safe_os_system`)
- `QuikTieper/launcher.py` (app launch shell → `safe_popen_shell`)
- `QuikTieper/remote.py` (remote action shell → `safe_popen_shell`)

### File Permission Hardening

The `CamComs.paths` module enforces private permissions on key material:

- `ensure_private_permissions(path, mode=0o600)`: sets file permissions
- `ensure_private_directory_permissions(path, mode=0o700)`: sets directory permissions
- `check_private_permissions(path)`: audits current permissions
- Integrated into `trust.py` (trusted key saves) and `service.py` (health checks)

### Trust Expiry

Trusted sender records support optional expiration:

- `TrustedSender` dataclass with `expires_at` timestamp
- Auto-prune of expired entries via `prune_expired()`
- Backward-compatible with old trust file format (no version key)
- Expiry enforced in `CamComs/receiver.py` and `PhiConnect/chat.py`
- CLI `--expires-in <days>` flag, GUI expiry display with "EXPIRED" in red

### Key Rotation

- `rotate_keys()` in `CamComs/identity.py` generates new identity atomically
- Atomic write via temp file + rename for both private and public keys
- Old key fingerprint captured before rotation
- Confirmation prompt required before rotation (`--yes` to skip)
- CLI: `fiona camcoms rotate-keys`
- GUI: Rotate Keys button in CamComs tab with confirmation dialog

### Verification Prompts

The `FionaCore.verification` module requires user confirmation for high-risk actions:

- `VerificationPrompt` ABC with two implementations
- `StdoutVerificationPrompt`: terminal-based Y/n prompt with timeout
- `DesktopVerificationPrompt`: Tkinter dialog + `notify-send` fallback
- Falls back from desktop → terminal → automatic denial on EOF/Ctrl+C

### Thread Safety

- `ActionRouter` uses `threading.RLock` (reentrant lock)
- Protects `specs` dict access and trace writes
- Prevents deadlocks if `run()` calls itself

### Pairing Protocol Security

The `CamComs/pairing` module implements secure device pairing:

- Pairing requests contain a visual fingerprint computed from the device's public key bundle
- User must explicitly approve each request (Approve/Deny in GUI or API)
- Pending requests expire after 120 seconds
- Approved devices are stored in the trusted sender directory
- Optional expiry on trusted device records
- Dedicated pairing HTTP server on port 8090 (separate from main receiver)

### Pairing Listener

The pairing HTTP server (`PairingHttpServer`) runs on a dedicated port (8090) and accepts POST requests on `/pair` or `/pairing`. It only handles pairing operations, not general message processing.

## Sensitive Paths

```text
~/.config/fiona/identity.json          # Host private identity
~/.config/fiona/identity.pub           # Host public key bundle
~/.config/fiona/camcoms/               # Legacy CamComs key paths
~/.config/fiona/camcoms/trusted/       # Trusted sender directory
~/.config/fiona/camcoms/audit.log      # Receiver audit events
~/.config/fiona/phiconnect/            # PhiConnect identity and chat logs
```

## Development Rules

- Do not accept remote actions from untrusted senders.
- Keep receiver execution in dry-run mode until testing is complete.
- Treat private key JSON files as secrets (permissions enforced to 0o600).
- Prefer explicit trusted public key exchange over automatic trust.
- Use audit logs to diagnose rejected messages before loosening validation.
- Never add a new shell execution point without wrapping it in `safe_os_system` or `safe_popen_shell`.
- Key rotation must use atomic writes (temp file + rename).

## Remaining Security Work

- replay cache cleanup policy
- encrypted replies from host back to trusted devices
- threat-oriented validation tests
- safer passphrase handling outside shell history
- ESP32 firmware crypto hardware verification
