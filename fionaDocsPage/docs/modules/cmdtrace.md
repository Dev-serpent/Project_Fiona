# CmdTrace

CmdTrace provides a high-performance observability layer for Fiona. It records every action routed through the central `ActionRouter` into an append-only JSONL log.

## Purpose

- **Audit Trail**: Perfect record of every command executed via Fiona CLI, GUI, or remote ESP32 instructions.
- **Performance Monitoring**: Records the execution time (`elapsed_ms`) of every action.
- **Failure Analysis**: Logs the success/failure status and error messages for every routed task.

## Commands

### View recent history
```bash
fiona action history --limit 20
```

### Filter history by action name
```bash
fiona action history --name host.status
```

### Clear the trace log
```bash
fiona action clear
```

## TUI Integration

The **History** page in the `fiona cli` TUI provides a real-time sliding view of the latest system activity. It updates every second to reflect new actions.

## Storage

Data is stored as a series of JSON objects (one per line) in:
`~/.config/fiona/cmdtrace.jsonl`
