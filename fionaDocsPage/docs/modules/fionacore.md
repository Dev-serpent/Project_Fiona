# FionaCore

FionaCore provides shared primitives used across all Fiona subsystems: action routing, security policies, macro execution, shell safety, verification prompts, notifications, and speech synthesis.

## Action Router

The central action dispatch system. Routes named actions to registered handler functions with ACL checking, verification prompts, and trace logging.

```python
from FionaCore.actions import ActionRouter, ActionResult

router = ActionRouter()
router.register("host.status", lambda: {"ok": True})
result = router.run("host.status")
```

Key features:

- **ACL integration**: Sender-scoped permission rules checked before action execution
- **Verification prompts**: High-risk actions require user confirmation
- **Thread safety**: Uses `threading.RLock` for concurrent access
- **Trace logging**: Every action result is recorded in the trace

## ACL (Access Control)

Sender-scoped permission system. See the [Security page](../developer/security.md) for full details.

```python
from FionaCore.acl import SenderACLRule, resolve_sender_profile, resolve_sender_scope
```

- Rules match sender IDs using `fnmatch` patterns
- Built-in profiles: `local`, `ssh`, `websocket`, `ble`
- Default tiers: local → agent:* → any other sender
- Unknown senders are denied by default

## Shell Safety

Blocks destructive shell commands across all 5 shell execution points in Fiona.

See the [Security page](../developer/security.md) for the full pattern list.

```python
from FionaCore.shell_safety import safe_os_system, safe_popen_shell, check_command_safety
```

Protected commands: `rm -rf /`, `mkfs`, `dd`, `wipefs`, `chmod 777 /etc/shadow`, `curl | bash`, and 25+ other destructive patterns.

Wrapped execution points:

- `fiona/cli.py` (`run-shell` command)
- `TerminalAssist/gui.py` (shell action execution)
- `TerminalAssist/tui.py` (shell action execution)
- `QuikTieper/launcher.py` (app launch shell)
- `QuikTieper/remote.py` (remote action shell)

## Macro Engine

Extended macro execution engine with waits, conditions, branching, and variable interpolation.

### MacroStep

```python
from FionaCore.macros import MacroStep

step = MacroStep(
    action="launch:brave",
    wait_type="wait_for_window",
    wait_value="Brave",
    condition_type="process_running",
    condition_value="brave",
    fallback_action="notify:Brave is running",
)
```

### Wait Types

| Type | Behavior |
|------|----------|
| `sleep` | Pause for N milliseconds |
| `wait_for_window` | Poll active window title/class up to 30s |
| `wait_for_process` | Poll `/proc` for process name up to 30s |

### Condition Types

| Type | Behavior |
|------|----------|
| `window_active` | Check if window title/class matches |
| `process_running` | Check if process name found in `/proc` |
| `action_result` | Check previous step result (`action_name:ok` / `action_name:failed`) |

### Variable Interpolation

String fields support `${variable_name}` placeholders:

```python
step = MacroStep(action="notify:Hello ${user_name}")
```

Available variables: all entries in the execution context, plus `step_index`, `last_result`, and `last_ok`.

### GOTO

Steps with action `GOTO:<macro_name>` branch to another macro's steps (max depth 10 to prevent circular references).

### CLI

```bash
fiona --run-macro my_macro   # Execute a named macro
fiona --list-macros          # List all macros and step counts
```

## Verification Prompts

Requires user confirmation for high-risk actions before execution.

```python
from FionaCore.verification import StdoutVerificationPrompt, DesktopVerificationPrompt
```

- **Desktop prompt**: Tkinter dialog with Yes/No buttons
- **Stdout prompt**: Terminal-based prompt with timeout
- Falls back from desktop → terminal → automatic denial

## Notifications

Desktop notification builder with optional speech output.

```python
from FionaCore.notifications import build_notification

build_notification("Fiona", "Task complete", urgency="normal")
```

- Uses `notify-send` for desktop notifications
- Truncates long bodies automatically
- Optional speech integration via `FionaCore.speech`

## Speech

Minimal speech synthesis via system TTS engines.

```python
from FionaCore.speech import speak

speak("Task complete")  # Uses espeak or festival
```

- Prefers `espeak` (fast, widely available)
- Falls back to `festival`
- Silent if no TTS engine is installed
