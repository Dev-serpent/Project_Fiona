# FionaCore

FionaCore provides shared primitives used across all Fiona subsystems: action routing, security policies, macro execution, shell safety, verification prompts, notifications, speech synthesis, approval management, permissions, and voice integration.

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

## ApprovalManager

Human-in-the-loop plan approval system used by the Agent orchestrator. Agent threads submit plans and block on `wait_for_approval()` while server threads call `approve_plan()` / `deny_plan()` in response to human action.

### PlanStatus

```python
from FionaCore.approval import PlanStatus
```

| Status | Description |
|--------|-------------|
| `PENDING` | Awaiting human approval |
| `APPROVED` | Human approved, ready to execute |
| `DENIED` | Human denied |
| `EXECUTING` | Currently being executed by agent |
| `COMPLETED` | All steps done |
| `FAILED` | Execution failed |
| `CANCELLED` | Human cancelled during execution |

### PlannedStep

```python
from FionaCore.approval import PlannedStep

step = PlannedStep(
    step_number=1,
    action="browser_navigate",
    params={"url": "https://example.com"},
    reasoning="Navigate to the target URL",
    risk="medium",
    requires_approval=False,
)
```

### ApprovalManager API

```python
from FionaCore.approval import ApprovalManager, get_approval_manager

manager = get_approval_manager()  # Module-level singleton

# Agent side: submit a plan and wait for human decision
plan_id = manager.submit_plan(
    goal="Open the browser to example.com",
    steps=[step],
    agent_id="fiona-agent",
)
status = manager.wait_for_approval(plan_id, timeout=300)  # 'approved' | 'denied' | 'timeout'

# Server/GUI side: approve or deny
manager.approve_plan(plan_id)
manager.deny_plan(plan_id, reason="Not now")

# Lifecycle management
manager.mark_executing(plan_id)
manager.mark_completed(plan_id, summary="All steps done")
manager.mark_failed(plan_id, error="Navigation timed out")
manager.cancel_plan(plan_id, reason="User interrupted")
```

The `on_change` callback notifies subscribers when any plan status changes:

```python
def on_plan_change(plan_id: str) -> None:
    plan = manager.get_plan(plan_id)
    print(f"Plan {plan_id} is now {plan['status']}")

manager.on_change(on_plan_change)
```

## Permissions

Two permission systems work together to control what agents and senders can do.

### PermissionProfile

`FionaCore.permissions` defines risk-gated permission profiles.

```python
from FionaCore.permissions import PermissionProfile, permission_allows, permission_profile
```

Built-in profiles:

| Profile | Max Risk | Permissions |
|---------|----------|-------------|
| `local` | high | read, control, service, network, gui |
| `agent` | medium | read, control, network |
| `remote_safe` | low | read |

```python
# Check if a given profile allows an operation
allowed = permission_allows(
    profile="agent",
    risk="medium",
    permission="network",
)
```

### PermissionEnforcer

`Agent.permission` provides `PermissionEnforcer` and `SafeActionRouter` for runtime tool-access gating within the Agent subsystem. The enforcer checks whether a specific tool name is permitted by the active personality, and `SafeActionRouter` wraps `FionaCore.ActionRouter` with these checks.

```python
from Agent.permission import PermissionEnforcer, SafeActionRouter

enforcer = PermissionEnforcer(personality)
enforcer.assert_tool_allowed("browser_navigate")  # Raises AgentPermissionError if denied

safe_router = SafeActionRouter(enforcer=enforcer, router=action_router)
result = safe_router.run("browser_navigate", url="https://example.com")
```

Key points:

- `PermissionEnforcer` is optional — backward compatibility is preserved.
- `SafeActionRouter.run()` checks permission before delegating to `ActionRouter.run()`.
- `SafeActionRouter.run_with_fallback()` attempts CLI fallback if the action is not registered.
- `list_allowed_actions()` returns the intersection of registered actions and the personality's allowed tools.

## Voice Integration

Voice command parsing and speech-to-text transcription.

### VoiceCommand

```python
from FionaCore.voice import VoiceCommand, parse_voice_command
```

`parse_voice_command()` matches spoken text against registered patterns and returns a `VoiceCommand` with the recognized action:

```python
cmd = parse_voice_command("Show host status")
# VoiceCommand(text="Show host status", action="host.status", confidence=0.9)

cmd = parse_voice_command("What is open on the desktop?")
# VoiceCommand(text="What is open on the desktop?", action="seeondesk.status", confidence=0.9)
```

Supported voice commands:

| Speech Pattern | Mapped Action |
|----------------|---------------|
| "show/open the host status" | `host.status` |
| "show/open the fat" / "terminal dashboard" | `fat.status` |
| "camcoms smoke/test" / "encryption test" | `camcoms.smoke` |
| "show/open camcoms paths" | `camcoms.paths` |
| "show/list bindings/shortcuts" | `quiktieper.list` |
| "desktop status" / "what is open" | `seeondesk.status` |
| "eye control status" | `eyecontrol.status` |
| "agent status" / "lm studio status" | `agent.status` |

### WhisperEngine

```python
from FionaCore.voice_engine import WhisperEngine, quick_transcribe
```

`WhisperEngine` wraps `faster-whisper` for local speech-to-text transcription:

```python
engine = WhisperEngine(model_size="tiny", device="cpu", compute_type="int8")

# Transcribe from a numpy audio buffer
text = engine.transcribe_audio_buffer(audio_data, sample_rate=16000)

# Record and transcribe in one call
text = engine.listen_and_transcribe(duration_seconds=5.0)
```

`quick_transcribe()` provides a one-shot convenience wrapper:

```python
from FionaCore.voice_engine import quick_transcribe

text = quick_transcribe(phrase_seconds=3.0)  # Records and returns transcribed text
```

Optional dependencies: `faster-whisper`, `sounddevice`, `numpy`.
