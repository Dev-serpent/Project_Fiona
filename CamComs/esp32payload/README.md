# CamComs ESP32 Payload

This folder is the ESP32-side sender payload.

Current direction:

- ESP32 is the sender.
- Host is the receiver.
- ESP32 encrypts an instruction/event for the host public key.
- ESP32 POSTs the encoded envelope to the host IP endpoint.
- Host decodes and decrypts with its CamComs private identity.

The envelope must match `CamComs.encryption`:

- X25519 ephemeral key agreement against the host encryption public key
- HKDF-SHA256 message key derivation
- AES-GCM encrypted payload
- Ed25519 signature from the ESP32 signing key
- base64url JSON envelope encoded as ASCII for transport

## Host Setup

Generate the host receiver identity:

```bash
fiona camcoms keygen --device-id host --private-out host.private.json --public-out host.public.json
```

Generate the ESP32 sender identity on the host for provisioning:

```bash
fiona camcoms keygen --device-id esp32 --private-out esp32.private.json --public-out esp32.public.json
```

Copy these values into `esp32payload.ino`:

- `HOST_DEVICE_ID` from `host.public.json`
- `HOST_ENCRYPTION_PUBLIC_KEY_B64` from `host.public.json`
- `ESP32_DEVICE_ID` from `esp32.private.json`
- `ESP32_SIGNING_PRIVATE_KEY_B64` from `esp32.private.json`

The host should use `esp32.public.json` as the expected sender when decrypting.

## Notes

`esp32payload.ino` is intentionally a firmware template. The Wi-Fi/HTTP and envelope construction are concrete, while the tiny crypto adapter section is isolated because the exact ESP32 crypto library choice may change.

For the current one-way direction, the ESP32 only needs the host encryption public key and its own signing private key. The ESP32 static encryption private key is not needed until the host also needs to encrypt responses back to the ESP32.
