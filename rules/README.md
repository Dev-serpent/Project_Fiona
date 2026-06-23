# Fiona Rules Framework

This directory contains the rule system that governs how the Fiona orchestration
agent makes decisions. The rules are designed to be loaded as persistent system
prompt context by the Controller personality, ensuring consistent, safe, and
effective agent behavior.

## File Map

| File | Purpose | Load Order |
|---|---|---|
| `architecture.md` | Project structure, conventions, key files | 1 |
| `controller.md` | Primary orchestrator rules — reason, plan, execute | 2 |
| `tool_selection.md` | Rules for selecting tools and actions | 3 |
| `execution.md` | Rules for executing actions safely | 4 |
| `repository.md` | Rules for reading and navigating the codebase | 5 |
| `coding.md` | Rules for writing and modifying code | 6 |
| `recovery.md` | Rules for error recovery and fallbacks | 7 |

## Guiding Principles

- **Reason before acting** — understand context before choosing a course.
- **Plan before executing** — decompose work before starting.
- **Search before creating** — verify nothing suitable already exists.
- **Reuse before rewriting** — extend existing systems instead of replacing.
- **Verify before completing** — confirm correctness before declaring done.
- **Recover before failing** — attempt graceful recovery before aborting.
- **Ask before assuming** — when requirements are ambiguous, ask.

## How to Use These Rules

The Controller personality in `Agent/personality.py` should load these files
and concatenate them as the system prompt sent to the LLM at the start of each
orchestration session. The files are designed to compose — `architecture.md`
provides grounding, `controller.md` provides the core reasoning framework, and
the remaining files provide per-domain guidance.

## Integration Points

- `Agent/personality.py` — `Personality` definition for `"controller"`
- `Agent/orchestrator.py` — `AgentOrchestrator` that uses the controller
- `Agent/ollama.py` — OllamaClient that sends system prompts to the model
- `fiona/cli.py` — CLI entry point with `--model` and layer dispatch
