# Testing

Fiona uses Python `unittest`.

## Run All Tests

From the repository root:

```bash
python -m unittest discover -s tests -v
```

Important: `python -m unittest discover -v` from the repository root currently discovers 0 tests in this layout. Use `-s tests`.

## Compile Check

```bash
python -m compileall Agent CamComs DataClient EyeControl PhiConnect QuikTieper SeeOnDesk TerminalAssist Vsee fiona
```

## CamComs Focused Tests

```bash
python3 -m unittest tests.test_camcoms_encryption tests.test_camcoms_transport
```

## Direct Smoke Commands

CamComs encryption smoke test:

```bash
python3 -m fiona.cli camcoms smoke-test
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
