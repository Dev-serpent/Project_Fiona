# Test Suites

Fiona's tests are organized by subsystem and risk boundary. They are intentionally mostly unit tests with mocked external services where possible, because the project touches desktop automation, local HTTP transport, crypto, systemd, and network scraping.

Run all tests from the repository root:

```bash
python -m unittest discover -s tests -v
```

## Suite Map

| Test file | Purpose | Boundary Protected |
| --- | --- | --- |
| `test_package_structure.py` | Verifies Fiona exposes all sibling subsystems and that direct imports work | packaging/import contract |
| `test_cli_help.py` | Verifies top-level and group help grids stay available | public CLI contract |
| `test_app_command_presets.py` | Verifies curated app command normalization | QuikTieper app launcher quality |
| `test_desktop_apps.py` | Verifies desktop app import behavior and filtering | Linux `.desktop` importer |
| `test_key_assignment.py` | Verifies generated launch keys are unique and preserve defaults | binding safety |
| `test_gui_handlers.py` | Verifies GUI handlers that can run headlessly | GUI callback behavior and debug path restrictions |
| `test_quiktieper_remote.py` | Verifies remote action allowlist/dry-run/macro behavior | remote execution safety |
| `test_camcoms_encryption.py` | Verifies encrypt/decrypt, wrong-recipient rejection, tamper rejection, passphrase keys | cryptographic correctness |
| `test_camcoms_instructions.py` | Verifies strict instruction JSON and macro validation | remote instruction schema |
| `test_camcoms_transport.py` | Verifies envelope codec, HTTP POST shape, compose-send behavior | encoded transport contract |
| `test_camcoms_trust.py` | Verifies trusted sender persistence/list/remove behavior | trust store lifecycle |
| `test_camcoms_receiver.py` | Verifies trusted receiver processing, replay rejection, untrusted rejection, audit/chat views | host receiver safety |
| `test_camcoms_service.py` | Verifies host config round-trip, status checks, systemd unit rendering, user service commands, logs | service lifecycle |
| `test_phiconnect_chat.py` | Verifies encrypted chat send/receive, identity reuse, trust, replay failure, blank message rejection | computer-to-computer communication |
| `test_dataclient_miner.py` | Verifies search/scrape/summarize/mining behavior with controlled inputs | data gathering pipeline |
| `test_dataclient_cli.py` | Verifies CLI wrappers for DataClient operations | DataClient public CLI |
| `test_dataclient_table.py` | Verifies table load/save/convert/formula behavior | MiniExcel data correctness |
| `test_vsee_model.py` | Verifies point/edge parsing, projection, and validation failures | holography model correctness |
| `test_seeondesk.py` | Verifies active-window detection backends and serializable snapshots | desktop-awareness logic |
| `test_eyecontrol.py` | Verifies EyeControl dependency status and CLI config construction without starting the camera loop | optional camera integration |
| `test_terminal_assist.py` | Verifies fAT dashboard rendering, readiness state, CLI defaults, and Zellij layout generation | terminal assistance |
| `test_agent_lmstudio.py` | Verifies LM Studio chat-completions payload and response parsing | local model bridge |
| `test_agent_command_registry.py` | Verifies agent-visible command registry and app list | future agent tool surface |

## Why The Tests Exist

The suite protects the parts of Fiona that can become dangerous or confusing if they regress:

- **Crypto and trust**: encrypted messages must not decrypt for the wrong recipient, tampered messages must fail, and untrusted senders must be rejected.
- **Remote actions**: decrypted instructions must pass schema validation and allowlist checks before any local action can execute.
- **Desktop automation**: generated launch keys must not collide and app import must not flood the config with low-value entries.
- **Service lifecycle**: host configs and generated systemd units must remain predictable.
- **GUI handlers**: non-display logic must stay testable without opening windows.
- **Data workflows**: research/table tools must preserve structured output and avoid unsafe formula execution.
- **Agent bridge**: local model requests must remain explicit and separate from action execution.

## What Is Mocked

The tests avoid relying on machine-specific state:

- LM Studio HTTP calls are mocked.
- CamComs HTTP transport is mocked where possible.
- systemd calls are mocked.
- desktop tool calls such as `kdotool`, `xdotool`, and `xprop` are mocked.
- temporary directories replace real config/key/trust paths.

This makes the suite suitable for regular development runs even when no ESP32, LM Studio server, or active desktop automation stack is available.

## What Is Not Fully Tested Yet

- real ESP32 firmware crypto
- real networked ESP32-to-host messages
- live systemd service enablement on the user's machine
- full GUI rendering and manual workflows
- global keyboard listener behavior under every desktop/session type
- real DataClient internet searches in deterministic CI
- true screen-recording or ML behavior for SeeOnDesk

## Validation Commands

Full test suite:

```bash
python -m unittest discover -s tests -v
```

Compile check:

```bash
python -m compileall Agent CamComs DataClient EyeControl PhiConnect QuikTieper SeeOnDesk TerminalAssist Vsee fiona
```

Docs build:

```bash
cd fionaDocsPage
python -m mkdocs build --strict
```
