# CamComs

CamComs is Fiona's communications layer.

## Responsibility

- encrypted communications
- decryption/encryption
- remote device connectivity
- command/session transport
- host receiver and service behavior

## Current Direction

```text
ESP32 sender -> encoded encrypted HTTP POST -> Fiona host receiver
```

The host decodes and decrypts messages with its CamComs private identity.

## Current Implementation

CamComs provides:

- `CamComsIdentity.generate()` for encryption and signing keypairs
- public key bundles that are safe to share
- X25519 key agreement
- HKDF-SHA256 key derivation
- AES-GCM encrypted payloads
- Ed25519 sender signatures
- base64url JSON envelope encoding/decoding
- trusted sender public-key storage
- replay protection for duplicate/stale messages
- host receiver and host service skeleton
- audit log for accepted/rejected message processing
- strict JSON instruction validation
- optional passphrase encryption for private key JSON

## Default Storage Paths

```text
~/.config/fiona/camcoms/host.private.json
~/.config/fiona/camcoms/host.public.json
~/.config/fiona/camcoms/esp32.private.json
~/.config/fiona/camcoms/esp32.public.json
~/.config/fiona/camcoms/trusted/
~/.config/fiona/camcoms/audit.log
```

## Useful Commands

```bash
python3 -m fiona.cli camcoms smoke-test
python3 -m fiona.cli camcoms paths
python3 -m fiona.cli camcoms keygen --device-id host
python3 -m fiona.cli camcoms keygen --device-id esp32
python3 -m fiona.cli camcoms trust --public ~/.config/fiona/camcoms/esp32.public.json
python3 -m fiona.cli camcoms trust --list
python3 -m fiona.cli camcoms audit
```

## Key Lifecycle

Generate host keys:

```bash
python3 -m fiona.cli camcoms keygen --device-id host
```

Generate ESP32 provisioning keys:

```bash
python3 -m fiona.cli camcoms keygen --device-id esp32
```

Trust a sender:

```bash
python3 -m fiona.cli camcoms trust --public ~/.config/fiona/camcoms/esp32.public.json
```

List trusted senders:

```bash
python3 -m fiona.cli camcoms trust --list
```

Remove a sender:

```bash
python3 -m fiona.cli camcoms trust --remove esp32
```

## Encrypt / Decrypt

Encrypt a press instruction:

```bash
python3 -m fiona.cli camcoms encrypt \
  --sender-private ~/.config/fiona/camcoms/esp32.private.json \
  --recipient-public ~/.config/fiona/camcoms/host.public.json \
  --press alt s
```

Encrypt structured instruction JSON:

```bash
python3 -m fiona.cli camcoms encrypt \
  --sender-private ~/.config/fiona/camcoms/esp32.private.json \
  --recipient-public ~/.config/fiona/camcoms/host.public.json \
  --instruction-json '{"version":1,"type":"press","keys":["alt","s"]}'
```

Decrypt an encoded envelope:

```bash
python3 -m fiona.cli camcoms decrypt \
  --recipient-private ~/.config/fiona/camcoms/host.private.json \
  --sender-public ~/.config/fiona/camcoms/esp32.public.json \
  --encoded '<encoded-message>'
```

## Transport

Send an encoded message to a host/IP endpoint:

```bash
python3 -m fiona.cli camcoms send \
  --host 192.168.1.50 \
  --port 8080 \
  --path / \
  --encoded '<encoded-message>'
```

## Receiver

Run the receiver directly:

```bash
python3 -m fiona.cli camcoms receive --private ~/.config/fiona/camcoms/host.private.json --port 8080
```

Receiver options:

- `--host 127.0.0.1`
- `--port 8081`
- `--execute` to execute approved QuikTieper remote actions instead of dry-run
- `--trusted-dir <dir>` to use a custom trusted sender directory

## Host Service

```bash
python3 -m fiona.cli host init
python3 -m fiona.cli host status
python3 -m fiona.cli host run
python3 -m fiona.cli host install-service --print
```

Nested service commands also exist:

```bash
python3 -m fiona.cli camcoms service init
python3 -m fiona.cli camcoms service status
python3 -m fiona.cli camcoms service run
```
