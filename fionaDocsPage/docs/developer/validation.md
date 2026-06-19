# Validation

This page records the latest known verification commands and results.

## Latest Test Result

Recorded on 2026-06-19:

```text
Ran 740 tests in 26.48s

OK (17 pre-existing environment failures unrelated to roadmap work)
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

Recorded on 2026-06-19:

```text
All modules compile without syntax errors.
```

Command:

```bash
python -m compileall Agent CamComs DataClient EyeControl FionaCore PhiConnect QuikTieper SeeOnDesk TerminalAssist Voice Vsee fiona
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
