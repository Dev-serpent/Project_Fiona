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

## Module-Specific Test Commands

### Browser Automation

```bash
python -m pytest tests/browser/ -v
```

This covers the `BrowserManager` state machine and the `PlaywrightBrowserProvider` with fully mocked Playwright imports.

### Agent Orchestration

```bash
python -m pytest tests/test_agent_orchestration.py tests/test_agent_orchestrator.py tests/test_agent_foreman_handler.py -v
```

This covers the think-act-observe loop, ForemanAgent task decomposition, sub-agent management, and plan synthesis.

### Contract Tests

```bash
python -m pytest tests/contracts/ -v
```

Validates every abstract interface defined in `fiona/interfaces.py` against contract test suites that verify method signatures, error conditions, and data type invariants.

### Additional Agent Tests

```bash
python -m pytest tests/test_agent_chat_handler.py tests/test_agent_chat_store.py tests/test_agent_personalities.py tests/test_agent_query_detector.py tests/test_agent_command_registry.py tests/test_agent_stress.py tests/test_agent_backward_compat.py -v
```

Covers chat session management, token estimation, personality detection, query classification, command discovery, stress/edge cases, and backward compatibility.

## Compile Check

```bash
python -m compileall Agent BrowserAutomation CamComs DataClient EyeControl FionaCore PhiConnect QuikTieper SeeOnDesk TerminalAssist Voice Vsee fiona
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
