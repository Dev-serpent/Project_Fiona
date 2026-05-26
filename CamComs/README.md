# CamComs

CamComs is Fiona's communications layer.

Intended responsibility:
- encrypted communications
- decryption/encryption
- remote device connectivity
- command/session transport

Current direction:
- ESP32 is the sender.
- The host running Fiona is the receiver.
- The ESP32 sends encoded encrypted envelopes to the host IP endpoint.
- The host decodes and decrypts with its CamComs private identity.

## Current Implementation

CamComs currently provides:

- `CamComsIdentity.generate()` creates an encryption keypair and a signing keypair.
- `identity.public_bundle` is safe to share with another device.
- `encrypt_message(...)` encrypts a payload to the recipient public key.
- `decrypt_message(...)` decrypts with the recipient private key and verifies the sender signature.
- `ReplayGuard` rejects stale or duplicate envelopes.
- `HostMessageProcessor` decrypts trusted sender messages and routes strict instructions into QuikTieper.
- `RemoteActionRunner` execution defaults to dry-run in the receiver unless `--execute` is passed.
- Private key JSON can be stored raw or passphrase-encrypted.

The envelope uses X25519 for key agreement, HKDF-SHA256 for message key derivation,
AES-GCM for authenticated encryption, and Ed25519 signatures for sender verification.

See `esp32payload/` for the ESP32 sender payload template.
