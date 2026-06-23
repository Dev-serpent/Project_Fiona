# Agent

Agent is Fiona's local AI orchestration layer. It connects to a running Ollama instance for local inference, manages conversational chat sessions, exposes a command registry for autonomous tool use, and provides a multi-agent orchestration pipeline for complex task decomposition.

## Migration: LM Studio → Ollama

The Agent was originally built against LM Studio's OpenAI-compatible endpoint. It has been fully migrated to Ollama's native API.

| Legacy | Current |
|--------|---------|
| `LMStudioClient` | `OllamaClient` |
| `LMStudioError` | `OllamaError` |
| `http://localhost:1234/v1` | `http://localhost:11434/api` |

Backward-compatibility aliases exist at the package level:

```python
from Agent import LMStudioClient, LMStudioError
# LMStudioClient is OllamaClient, LMStudioError is OllamaError
```

## Ollama Client

The `OllamaClient` class communicates with a local Ollama instance via its JSON API. It supports text generation, system prompts, and optional image attachment.

**Default configuration:**

| Parameter | Default |
|-----------|---------|
| `base_url` | `http://localhost:11434/api` |
| `model` | `qwen3:8b-en` |
| `timeout_seconds` | `120.0` |

**Key method:** `ask(prompt, *, system_prompt, image_path, temperature, max_tokens) -> str`

The `ask` method sends a message to the model and returns the text response. When a `Personality` is attached to the client, its `system_prompt` is used by default if the caller does not explicitly pass one.

```python
from Agent import OllamaClient

client = OllamaClient()
response = client.ask("What is the current system time?")
print(response)
```

Custom model and endpoint:

```python
client = OllamaClient(
    base_url="http://localhost:11434/api",
    model="llama3.2:3b",
    timeout_seconds=60.0,
)
client.ask("Hello!", system_prompt="You are a helpful assistant.", temperature=0.7)
```

## Chat System

### AgentChatHandler

`AgentChatHandler` bridges a GUI or CLI frontend to the LLM for interactive chat sessions. All LLM calls run in daemon threads so they never block the caller. UI updates are delegated to callbacks that the caller can marshal onto the correct thread (e.g. via `widget.after()` in Tkinter).

**Session management:**

- `create_session(personality="general")` — create a new session, returns a UUID4 string
- `list_sessions()` — list all sessions, newest-active first
- `delete_session(session_id)` — delete a session and all its messages

**Message sending:**

`send_message(session_id, message, token, on_message, on_error, on_complete, system_prompt_override=None)` launches a daemon thread that:

1. Checks the `CancellationToken`
2. Stores the user message in the `ChatStore`
3. Calls `on_message("user", message)`
4. Builds a token-aware context window from the `ChatStore`
5. Looks up the session's `Personality`
6. Calls `OllamaClient.ask()` with the effective system prompt
7. Stores the agent response
8. Calls `on_message("agent", response)`
9. Calls `on_complete()`

On cancellation or error, the error is stored in the chat history with role `"cancelled"` or `"error"` and the `on_error` callback is invoked.

```python
from Agent import AgentChatHandler, ChatStore, CancellationToken

store = ChatStore("chats.db")
handler = AgentChatHandler(store)
session_id = handler.create_session(personality="general")

token = CancellationToken()

def on_message(role, content):
    print(f"{role}: {content}")

def on_error(msg):
    print(f"Error: {msg}")

def on_complete():
    print("Done!")

handler.send_message(session_id, "What can you do?", token, on_message, on_error, on_complete)
```

### ChatStore

`ChatStore` is a thread-safe SQLite-backed persistence layer for chat history. It uses WAL mode and a `threading.Lock` to serialise all database access.

```python
from Agent import ChatStore

with ChatStore("chats.db") as store:
    sid = store.create_session(personality="engineer")
    store.add_message(sid, "user", "Hello!")
    store.add_message(sid, "agent", "Hi! How can I help?")
    messages = store.get_context_window(sid, max_tokens=2048)
```

**Key types:**

```python
@dataclass(frozen=True)
class ChatMessage:
    id: int
    session_id: str
    role: str          # 'user' | 'agent' | 'system' | 'error' | 'cancelled'
    content: str
    personality: str
    timestamp: float
    token_count: int | None = None
    model: str | None = None
```

**Token estimation:**

`estimate_tokens(text)` provides a rough estimate (1 token ≈ 4 characters, `len(text) // 4 + 1`). Used by `get_context_window()` to build token-budget-aware context when `token_count` is `NULL`.

**Additional methods:**

| Method | Description |
|--------|-------------|
| `get_messages(session_id, limit, offset)` | Retrieve messages oldest-first |
| `count_messages(session_id)` | Number of messages in a session |
| `search_messages(query, session_id, limit)` | Substring search across message content |
| `prune_sessions(older_than_days)` | Delete sessions inactive for N days |
| `import_jsonl(path)` | Import messages from a JSONL file |
| `vacuum()` | Reclaim unused SQLite space |

## Command Registry

The command registry defines the set of tools an agent can invoke. Commands are categorised by function domain, each with an input schema that the LLM can use to construct valid calls.

```python
@dataclass(frozen=True)
class CommandSpec:
    name: str
    category: str
    description: str
    input_schema: dict[str, Any]
    requires_confirmation: bool = False
```

### DEFAULT_COMMANDS

The full set of built-in commands, grouped by category:

| Category | Commands |
|----------|----------|
| **input** | `press`, `text` |
| **pointer** | `click`, `move` |
| **app** | `launch_binding` |
| **automation** | `macro` |
| **awareness** | `seeondesk_list`, `seeondesk_active` |
| **vision** | `seeondesk_analyze` |
| **research** | `dataclient_mine` |
| **memory** | `recall_remember`, `recall_search` |
| **system** | `fiona_status` |
| **browser** | `browser_status`, `browser_navigate`, `browser_click`, `browser_type`, `browser_screenshot` |

### command_registry() function

`command_registry(config_path, enforcer=None)` returns a dictionary with two keys:

- `"commands"` — list of command specs (filtered by `DEFAULT_ALLOWED_ACTIONS` and optionally by the `PermissionEnforcer`)
- `"apps"` — available application bindings from the QuikTieper config file

```python
from Agent import command_registry

registry = command_registry()
print(registry["commands"])  # list of command dicts
print(registry["apps"])      # list of app bindings
```

## Agent Orchestrator

`AgentOrchestrator` manages the autonomous execution loop for Fiona's workstation assistant. It uses an LLM to generate a multi-step plan, submits that plan for human approval, then executes the approved steps.

**Pipeline:**

1. **Plan generation** — iterates up to `max_turns`, asking the LLM to produce `{thought, action, input}` JSON at each step
2. **Human approval** — submits the plan to an `ApprovalManager` and waits for user sign-off
3. **Execution** — executes each approved step, collecting observations

```python
from Agent import AgentOrchestrator

orchestrator = AgentOrchestrator()
result = orchestrator.run_goal("Open the terminal and check disk space")
print(result)
```

Each turn produces an `AgentTurn` dataclass:

```python
@dataclass
class AgentTurn:
    thought: str
    action_name: str | None = None
    action_input: dict[str, Any] | None = None
    observation: str | None = None
```

**Helper function:** `run_agent_goal(goal, personality="controller")` creates an `AgentOrchestrator` and runs the goal in one call.

### Available tools in the orchestrator

The orchestrator has hardcoded tool execution for:

| Tool | Function |
|------|----------|
| `seeondesk_list` | List open windows |
| `seeondesk_active` | Active window details |
| `seeondesk_analyze` | Vision-based screen analysis |
| `press`, `click`, `move`, `text` | Input automation via `ActionRouter` |
| `launch_binding` | Launch app by binding name |
| `macro` | Execute a sequence of actions |
| `dataclient_mine` | Web research and CSV export |
| `recall_remember` | Store a fact in persistent memory |
| `recall_search` | Search stored memories |
| `fiona_status` | Fiona subsystem status |
| `browser_status`, `browser_navigate`, `browser_click`, `browser_type`, `browser_screenshot` | Browser automation |

## ForemanAgent (Advanced Orchestration)

`ForemanAgent` in `Agent/orchestration.py` provides a sophisticated multi-agent orchestration pipeline. It is the Milestone 4 advanced orchestration engine.

**Pipeline:**

```
Goal → ComplexityAssessor → [Simple: single SubAgent]
                           → [Moderate/Complex: TaskPlan.from_llm() → decompose
                              → topological execution (parallel/sequential layers)
                              → ForemanAgent._synthesize()]
```

### ComplexityAssessor

LLM-based classifier that sends the goal to an Ollama model and asks it to classify as `simple`, `moderate`, or `complex`.

| Classification | Behaviour |
|---------------|-----------|
| `SIMPLE` | Single `SubAgent` with the default personality |
| `MODERATE` | Decompose into sub-goals via `TaskPlan.from_llm()`, execute in dependency order |
| `COMPLEX` | Same as moderate (full decomposition and parallel execution) |

Falls back to `MODERATE` on any LLM error.

### TaskPlan & SubGoalSpec

`TaskPlan` is a decomposed plan consisting of multiple sub-goals with dependency relationships. It is generated by the LLM and validated for correctness.

```python
@dataclass(frozen=True)
class SubGoalSpec:
    id: str
    description: str
    assigned_personality: str
    depends_on: tuple[str, ...] = ()
    parallel: bool = False
```

**Validation checks:**

- Unique sub-goal IDs
- All `depends_on` references exist
- No circular dependencies (DFS cycle detection)
- All `assigned_personality` values are valid in the `PersonalityRegistry`

**Topological execution:** `plan.execution_order()` returns layers of parallel-independent tasks. Each inner list can execute in parallel; outer layers must execute sequentially.

### SubAgent

A personality-wrapped agent using `SafeActionRouter` for tool access. Executes a ReAct loop:

```
Think → Act → Observe → repeat until final answer or max_turns
```

Each turn:
1. Checks `CancellationToken`
2. Sends context + prompt to the LLM
3. Parses JSON response — expects either `{"action": "...", "input": {...}}` or `{"final": "..."}`
4. If action: executes via `SafeActionRouter.run_with_fallback()`
5. Appends observation to conversation history
6. Repeats until final answer or `max_turns`

```python
from Agent import OllamaClient
from Agent.orchestration import SubAgent, ComplexityAssessor, ForemanAgent, ForemanConfig
from Agent.personality import Personality, PersonalityRegistry
from Agent.permission import PermissionEnforcer, SafeActionRouter
from Agent.cancellation import CancellationToken

# Build a SubAgent manually
personality = PersonalityRegistry.get_instance().get("engineer")
enforcer = PermissionEnforcer(personality)
router = SafeActionRouter(enforcer)
client = OllamaClient()

agent = SubAgent(personality, client, router, max_turns=10)
token = CancellationToken()
result = agent.execute("Check the system status", token)
print(result)
```

### Parallel execution

`ForemanAgent` uses `concurrent.futures.ThreadPoolExecutor` for parallel sub-agent execution. Sub-goals flagged with `parallel: true` at the same dependency level run concurrently.

### Result synthesis

After all sub-goals complete, `ForemanAgent._synthesize()` sends the collected results to the LLM with a synthesis prompt that produces a coherent final response for the user.

### ForemanConfig

```python
@dataclass(frozen=True)
class ForemanConfig:
    parallel_by_default: bool = False
    max_sub_agents: int = 5
    max_turns_per_sub_agent: int = 10
    max_plan_retries: int = 2
    context_max_tokens: int = 2048
    default_personality: str = "general"
```

## Personality System

`Personality` is an immutable dataclass that defines the behaviour and constraints of an agent persona.

```python
@dataclass(frozen=True)
class Personality:
    name: str
    description: str
    system_prompt: str
    conversational_system_prompt: str | None = None
    allowed_tools: frozenset[str] | None = None
    model_override: str | None = None
```

| Attribute | Purpose |
|-----------|---------|
| `name` | Unique identifier |
| `description` | Human-readable role summary |
| `system_prompt` | System prompt sent to the LLM for ReAct-style interaction |
| `conversational_system_prompt` | Alternate prompt used when `QueryDetector` classifies input as a conversational query |
| `allowed_tools` | `frozenset` of permitted tool names; `None` means all tools allowed |
| `model_override` | Forces a specific Ollama model when this personality is active |

### Built-in Personalities

| Name | Role | Tools | Model |
|------|------|-------|-------|
| `general` | General-purpose assistant with full tool access | All | default |
| `planner` | Strategic planner — reads state, does not execute | `seeondesk_*`, `fiona_status`, `recall_*` | `qwen3:8b-en` |
| `engineer` | Execution specialist — automation & input | Input, pointer, awareness tools | default |
| `analyst` | Research & memory analyst | `dataclient_mine`, `recall_*`, `seeondesk_analyze` | `qwen3:8b-en` |
| `security` | Read-only audit personality | `seeondesk_list`, `seeondesk_active`, `fiona_status`, `recall_search` | `qwen3:8b-en` |
| `controller` | Orchestration agent — plans, delegates, verifies | All | `qwen3:8b-en` |

The `controller` personality's system prompt is loaded from the `rules/` directory (architecture, controller, tool_selection, execution, repository, coding, and recovery rule files). If the directory is missing, it falls back to the general system prompt.

### PersonalityRegistry

Thread-safe singleton registry for built-in and custom personalities.

```python
from Agent import Personality, PersonalityRegistry

registry = PersonalityRegistry.get_instance()

# Look up a built-in
p = registry.get("engineer")

# Register a custom personality
custom = Personality(
    name="coder",
    description="Software development specialist",
    system_prompt="You are a coding assistant. Generate Python code.",
    allowed_tools=frozenset({"fiona_status", "recall_search"}),
)
registry.register(custom)

# List all registered personalities
for p in registry.list():
    print(p.name, p.description)
```

## Permission System

### PermissionEnforcer

Runtime gate that checks tool access against a personality's restrictions. Completely optional — existing code never touches it, preserving full backward compatibility.

```python
from Agent import PermissionEnforcer
from Agent.personality import PersonalityRegistry

personality = PersonalityRegistry.get_instance().get("security")
enforcer = PermissionEnforcer(personality)

enforcer.check_tool("press")         # False (security has no input tools)
enforcer.assert_tool_allowed("press") # raises AgentPermissionError
```

### SafeActionRouter

Wraps `FionaCore.ActionRouter` with personality-based permission checks. Provides `run()` and `run_with_fallback()` methods.

`run_with_fallback()` attempts the action through the normal router first. If the action is not recognised (`ValueError`), it falls back to invoking `fiona.cli` as a subprocess — this guarantees the agent can attempt any registered command even if `ActionRouter` does not have a dedicated handler.

```python
from Agent import SafeActionRouter, PermissionEnforcer
from Agent.personality import PersonalityRegistry

personality = PersonalityRegistry.get_instance().get("general")
enforcer = PermissionEnforcer(personality)
router = SafeActionRouter(enforcer)

result = router.run("press", source="agent")
print(result.ok, result.detail)
```

## Query Detection

`QueryDetector` classifies user input as either a conversational query (greeting, simple question, chit-chat) or an actionable task — **with zero LLM calls**. All classification is done via compiled regex patterns and heuristics.

```python
from Agent import QueryDetector, QueryOrTask

QueryDetector.classify("hello")
# QueryOrTask.QUERY

QueryDetector.classify("create a new Python module for data processing")
# QueryOrTask.TASK
```

**Classification rules (applied in order):**

1. Empty/whitespace → `QUERY`
2. Greeting pattern → `QUERY`
3. Chit-chat pattern → `QUERY`
4. Very long message (>300 chars) → `TASK`
5. Action verb present → `TASK`
6. Simple question starter → `QUERY`
7. Technical reference present → `TASK`
8. Short message (<15 chars) → `QUERY`
9. Default → `QUERY` (conservative)

This classifier is used by the chat handler to decide whether to use the personality's conversational system prompt (QueryDetector.QUERY) or the full ReAct-style prompt (QueryDetector.TASK), avoiding wasted tokens on small talk.

## Cancellation

`CancellationToken` is a thread-safe cancellation primitive used throughout the Agent module. All methods are safe to call from any thread.

```python
from Agent import CancellationToken, CancelledError

token = CancellationToken()

# In a worker thread:
token.raise_if_cancelled()  # raises CancelledError if cancelled

# In the UI/main thread:
token.cancel()  # signal cancellation

# Reuse after reset:
token.reset()
```

The `SubAgent`, `AgentChatHandler`, `ForemanAgent`, and `ComplexityAssessor` all check the cancellation token at each turn, ensuring long-running operations can be interrupted cleanly.

## CLI Commands

All agent commands are available via `fiona agent <subcommand>`.

### agent status

Check whether the Ollama server is reachable:

```bash
fiona agent status
```

Returns the server's tag list as JSON if available, or an error report:

```json
{"available": false, "error": "...", "base_url": "http://localhost:11434/api"}
```

Custom endpoint:

```bash
fiona agent status --base-url http://localhost:11434/api
```

### agent ask

Send a one-shot prompt to Ollama:

```bash
fiona agent ask "What is the capital of France?"
```

Custom generation settings:

```bash
fiona agent ask \
  --model "llama3.2:3b" \
  --system "You are a terse assistant." \
  --temperature 0.7 \
  --max-tokens 512 \
  "Explain quantum computing in one sentence."
```

### agent run

Initiate the autonomous agent to solve a goal. Uses `AgentOrchestrator` to plan, get human approval, and execute:

```bash
fiona agent run "Check the system status and report any issues"
```

Limit the number of planning turns:

```bash
fiona agent run --turns 8 "Research the weather and save it to a file"
```

### agent commands

List the Fiona commands available to the agent:

```bash
fiona agent commands
```

With a custom QuikTieper config for app bindings:

```bash
fiona agent commands --config /path/to/config.yaml
```

### Shared CLI options

The `status`, `ask`, and `run` subcommands all accept:

| Option | Default | Description |
|--------|---------|-------------|
| `--base-url` | `http://localhost:11434/api` | Ollama API base URL |
| `--model` | `qwen3:8b-en` | Ollama model name |
| `--timeout` | `60.0` | Request timeout in seconds |

## Architecture Overview

```
┌──────────────────────────────────────────────────┐
│                    CLI / GUI                       │
└──────────┬──────────┬───────────┬────────────────┘
           │          │           │
     ┌─────▼──┐  ┌───▼────┐  ┌──▼──────────┐
     │ Chat   │  │ Agent  │  │ ForemanAgent │
     │Handler │  │Orchestr│  │ (advanced)   │
     └───┬────┘  │  ator  │  └──┬──┬──┬─────┘
         │       └───┬────┘     │  │  │
    ┌────▼───┐  ┌────▼────┐    │  │  │
    │ChatStore│  │Approval │    │  │  │
    │(SQLite) │  │Manager  │    │  │  │
    └────────┘  └─────────┘    │  │  │
                               │  │  │
                    ┌──────────▼──▼──▼──────┐
                    │    SubAgent (ReAct)     │
                    │  ┌──────────────────┐  │
                    │  │ LLM (Ollama)      │  │
                    │  └────────┬─────────┘  │
                    │           │            │
                    │  ┌────────▼─────────┐  │
                    │  │ PermissionEnforcer │  │
                    │  └────────┬─────────┘  │
                    │           │            │
                    │  ┌────────▼─────────┐  │
                    │  │ SafeActionRouter  │  │
                    │  └────────┬─────────┘  │
                    └───────────┼────────────┘
                                │
                    ┌───────────▼────────────┐
                    │   ActionRouter         │
                    │ (FionaCore)            │
                    └────────────────────────┘
```

## Package Exports

```python
from Agent import (
    # Ollama client
    OllamaClient, OllamaError,
    LMStudioClient, LMStudioError,     # backward compat aliases
    DEFAULT_OLLAMA_BASE_URL,

    # Chat
    AgentChatHandler,
    ChatStore, ChatStoreError,
    ChatMessage,
    estimate_tokens,

    # Command registry
    CommandSpec,
    command_registry,

    # Orchestration
    AgentOrchestrator, AgentTurn,
    run_agent_goal,
    ForemanAgent, ForemanConfig,
    ComplexityAssessor, Complexity,
    TaskPlan, SubGoalSpec, SubAgent, SubAgentResult,
    PlanValidationError,

    # Personality
    Personality, PersonalityRegistry,

    # Permission
    PermissionEnforcer, SafeActionRouter,
    AgentPermissionError,

    # Detection
    QueryDetector, QueryOrTask,

    # Cancellation
    CancellationToken, CancelledError,
)
```
