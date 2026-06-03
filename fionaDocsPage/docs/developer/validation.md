# Validation

This page records the latest known verification commands and results.

## Latest Test Result

Recorded on 2026-05-26:

```text
Ran 99 tests in 0.481s

OK
```

Command:

```bash
python -m unittest discover -s tests -v
```

## Latest Compile Result

Recorded on 2026-05-26:

```text
Compiled without syntax errors.
```

Command:

```bash
python -m compileall Agent CamComs DataClient EyeControl PhiConnect QuikTieper SeeOnDesk TerminalAssist Vsee fiona
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
