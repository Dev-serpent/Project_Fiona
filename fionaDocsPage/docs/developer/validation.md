# Validation

This page records the latest known verification commands and results.

## Latest Test Result

Recorded on 2026-06-23:

```text
1598 tests across Python and JavaScript:
  Python:   1413 passed, 14 env-failures (pytest)
  CAD JS:    87 passed (vitest)
  CAD Srv:   98 passed (pytest)
  compileall OK

OK (14 pre-existing environment failures unrelated to roadmap work)
```

Command:

```bash
python -m pytest tests/ -v
```

Or with unittest:

```bash
python -m unittest discover -s tests -v
```

## Latest Compile Result

Recorded on 2026-06-23:

```text
All modules compile without syntax errors.
```

Command:

```bash
python -m compileall Agent BrowserAutomation CamComs DataClient EyeControl FionaCore PhiConnect QuikTieper SeeOnDesk TerminalAssist Voice Vsee fiona
```

## Latest CamComs Smoke Result

Command:

```bash
fiona camcoms smoke-test
```

Output:

```text
{"keys":["alt","s"],"type":"press","version":1}
```

## Latest Host Service CLI Smoke Result

The direct host-service smoke checks returned:

```text
host init wrote /tmp/fiona-host-test.json
host status returned config, checks, system summary, and QuikTieper app/binding summary
camcoms audit returned an empty event list for a missing audit log
camcoms trust --list returned an empty sender list for a missing trusted directory
```

## Latest PhiConnect Loopback Result

Local loopback on `127.0.0.1:5000` succeeded with device id `fiona`, and inbound/outbound chat events were logged.

## Latest Shell Safety Test Result

Command:

```bash
python -m pytest tests/test_shell_safety.py -v
```

Result: 20 tests pass. All destructive command patterns (rm -rf /, mkfs, dd, etc.) are correctly blocked, and safe commands pass through.

## Latest Macro Engine Test Result

Command:

```bash
python -m pytest tests/test_macro_engine.py tests/test_macro_engine_runner.py -v
```

Result: 105 tests pass. Covers MacroStep serialization, wait execution, condition evaluation, branching runner, GOTO with circular detection, and variable interpolation.

## Latest Pairing Test Result

Command:

```bash
python -m pytest tests/test_pairing.py -v
```

Result: 28 tests pass. Covers PairingManager lifecycle, fingerprint computation, HTTP server handling, and stale request pruning.

## Latest Voice Test Result

Command:

```bash
python -m pytest tests/test_voice.py -v
```

Result: 36 tests pass. Covers wake word engine, push-to-talk, and feedback engine with graceful degradation.

## Latest Browser Automation Test Result

Command:

```bash
python -m pytest tests/browser/ -v
```

Result: 52 tests pass. Covers BrowserManager state machine (STOPPED → STARTING → RUNNING → DEGRADED → ERROR), auto-restart on crash, thread safety, Playwright provider navigation, element interaction, script execution, and all error types.

## Latest Agent Orchestration Test Result

Command:

```bash
python -m pytest tests/test_agent_orchestrator.py tests/test_agent_orchestration.py tests/test_agent_foreman_handler.py tests/test_agent_stress.py -v
```

Result: 128 tests pass. Covers the think-act-observe loop (AgentOrchestrator), ForemanAgent task decomposition, SubAgent ReAct loops, ComplexityAssessor classification, TaskPlan validation with cycle detection, cancellation tokens, and concurrency/stress edge cases.

## Latest Interface Contract Test Result

Command:

```bash
python -m pytest tests/contracts/ -v
```

Result: 68 tests pass. Validates every ABC in `fiona/interfaces.py` — method signatures, parameter types, return values, error conditions, and data type invariants for IBrowserProvider, IBrowserContext, IAgentBackend, IEventBus, and all supporting types.

## Latest Agent Chat & Personality Test Result

Command:

```bash
python -m pytest tests/test_agent_chat_handler.py tests/test_agent_chat_store.py tests/test_agent_personalities.py tests/test_agent_query_detector.py tests/test_agent_command_registry.py -v
```

Result: 86 tests pass. Covers ChatStore CRUD with token estimation, AgentChatHandler session management, Personality registry with 6 built-in personalities, QueryDetector classification, and CommandSpec registration for 20+ actions.
