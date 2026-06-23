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

## Agent Bridge

PhiConnect provides two optional agent integration modules under `PhiConnect/`:

### ForemanChatHandler

`foreman_handler.py` defines `ForemanChatHandler`, a GUI-facing handler that wraps `ForemanAgent` for multi-agent orchestration. It provides a toggle (`foreman_enabled`) to switch between simple single-agent chat (`AgentChatHandler`) and full orchestration via `ForemanAgent`.

When the **Agent bridge** checkbox in the PhiConnect GUI is enabled, chat messages sent through the GUI are forwarded to the local Ollama agent for processing. The `ForemanChatHandler` class handles the orchestration pipeline:

- Simple queries (greetings, chit-chat) are routed through the lightweight `AgentChatHandler` to avoid unnecessary token usage.
- Complex tasks are decomposed and executed by `ForemanAgent` using a multi-step orchestration pipeline with planning, sub-agent delegation, and result synthesis.
- A `CancellationToken` is passed throughout to support cancellation.

```python
from PhiConnect.foreman_handler import ForemanChatHandler

handler = ForemanChatHandler(chat_store=store)
handler.foreman_enabled = True
handler.send_message(
    session_id="...",
    message="What is the capital of France?",
    token=CancellationToken(),
    on_message=lambda role, content: print(role, content),
    on_error=lambda err: print("Error:", err),
    on_complete=lambda: print("Done"),
)
```

### PhiConnectAgentBridge

`bridge.py` defines `PhiConnectAgentBridge`, a lightweight bridge that intercepts inbound chat messages and automatically replies via the local Ollama agent. When the bridge is active, every inbound message (that does not already start with `[Fiona]`) is forwarded to the Ollama client, and the agent's response is sent back as a chat reply.

```python
from PhiConnect.bridge import PhiConnectAgentBridge

bridge = PhiConnectAgentBridge(config)
bridge.handle_message(event)  # forwards to Ollama and sends reply
```

Both modules require the Agent subsystem and an active Ollama instance on `http://localhost:11434`.
