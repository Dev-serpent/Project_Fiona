# Testing

Fiona uses Python `unittest` with pytest runner support.

## Run All Tests

From the repository root:

```bash
python -m unittest discover -s tests -v
```

Or with pytest for better output:

```bash
python -m pytest tests/ -v
```

Important: `python -m unittest discover -v` from the repository root currently discovers 0 tests in this layout. Use `-s tests`.

## Run Roadmap Tests

Tests specific to the Fiona Enhancement Roadmap (740+ total):

```bash
# ACL system
python -m pytest tests/test_acl.py -v

# Shell safety
python -m pytest tests/test_shell_safety.py -v

# Verification prompts
python -m pytest tests/test_verification.py -v

# Pairing protocol
python -m pytest tests/test_pairing.py -v

# Key rotation & identity
python -m pytest tests/test_identity.py -v

# Trust store extended
python -m pytest tests/test_trust_extended.py -v

# Macro engine
python -m pytest tests/test_macro_engine.py tests/test_macro_engine_runner.py -v

# Process tracker
python -m pytest tests/test_process_tracker.py -v

# Workspace watcher
python -m pytest tests/test_workspace_watcher.py -v

# Action discovery
python -m pytest tests/test_action_discovery.py -v

# Voice subsystem
python -m pytest tests/test_voice.py -v

# System tray
python -m pytest tests/test_system_tray.py -v
```

## Compile Check

```bash
python -m compileall Agent CamComs DataClient EyeControl FionaCore PhiConnect QuikTieper SeeOnDesk TerminalAssist Voice Vsee fiona
```

## CamComs Focused Tests

```bash
python -m unittest tests.test_camcoms_encryption tests.test_camcoms_transport
```

## Direct Smoke Commands

CamComs encryption smoke test:

```bash
python -m fiona.cli camcoms smoke-test
```

Expected payload:

```text
{"keys":["alt","s"],"type":"press","version":1}
```

Host service smoke checks:

```bash
python -m fiona.cli host init --config /tmp/fiona-host-test.json --force
python -m fiona.cli host status --config /tmp/fiona-host-test.json
python -m fiona.cli camcoms audit --path /tmp/fiona-audit-missing.log --limit 5
python -m fiona.cli camcoms trust --list --trusted-dir /tmp/fiona-trusted-missing
```

PhiConnect local loopback:

```text
Open PhiConnect, use the local public key as the peer key, start the receiver, and send to 127.0.0.1:5000.
```

Voice smoke test:

```bash
python -m fiona.cli voice feedback-test
```

Macro smoke test:

```bash
python -m fiona.cli --list-macros
```
