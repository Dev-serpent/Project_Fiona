# Security

Fiona's security-sensitive code is mainly in CamComs and PhiConnect.

## Existing Protections

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

## Sensitive Paths

```text
~/.config/fiona/camcoms/host.private.json
~/.config/fiona/camcoms/host.public.json
~/.config/fiona/camcoms/esp32.private.json
~/.config/fiona/camcoms/esp32.public.json
~/.config/fiona/camcoms/trusted/
~/.config/fiona/camcoms/audit.log
~/.config/fiona/phiconnect/
```

## Development Rules

- Do not accept remote actions from untrusted senders.
- Keep receiver execution in dry-run mode until testing is complete.
- Treat private key JSON files as secrets.
- Prefer explicit trusted public key exchange over automatic trust.
- Use audit logs to diagnose rejected messages before loosening validation.

## Remaining Security Work

- file permission checks for key material
- replay cache cleanup policy
- key rotation
- secure pairing UX
- public key fingerprint display and approval
- per-sender permissions
- threat-oriented validation tests
- safer passphrase handling outside shell history
