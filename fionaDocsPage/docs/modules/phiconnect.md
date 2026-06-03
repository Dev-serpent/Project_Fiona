# PhiConnect

PhiConnect is Fiona's standalone encrypted computer-to-computer chat app. It is separate from `fiona edit`, like Vsee, and uses CamComs crypto for chat messages instead of remote-control instructions.

## Open The App

```bash
python3 -m fiona.cli phiconnect
```

If Fiona is installed into the active environment:

```bash
fiona phiconnect
```

## What It Does

- creates a local PhiConnect identity under `~/.config/fiona/phiconnect/`
- shows your public key in the Settings tab
- lets you trust another computer's public key
- starts a local encrypted chat receiver on port `5000` by default
- sends chat messages to a peer host and port
- encrypts every sent message with the peer public key
- decrypts received messages with the local private key
- records inbound and outbound chat events in `~/.config/fiona/phiconnect/chat.log`
- displays messages from the last 3 minutes and refreshes the view every 5 seconds

## Local Loopback

For same-machine testing:

1. Open PhiConnect.
2. In Settings, use `Use Local Public Key`.
3. Start the receiver.
4. Send to `127.0.0.1` on port `5000`.

This tests the real encryption/decryption path without needing a second computer.

## Two Computer Setup

On each computer:

1. Open PhiConnect.
2. Export or copy the local public key from Settings.
3. Trust the other computer's public key.
4. Set the peer host to the other computer's LAN IP.
5. Use port `5000`, unless the peer is listening on a different port.
6. Start both receivers, then send messages.

## Common Send Errors

- Missing peer public key: outbound encryption has no recipient key yet.
- Connection refused: no PhiConnect receiver is listening on the target host/port.
- Signature/trust failure: the inbound sender public key is not trusted or does not match the sender identity.
