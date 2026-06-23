# Coding Rules

Rules for writing and modifying code in the Fiona project. These apply to
specialist agents performing implementation work.

## General Principles

### Extend, Don't Rewrite
- Never remove functionality unless strictly required.
- Always extend existing systems instead of replacing them.
- Preserve backward compatibility whenever practical.
- Prefer incremental improvements over large rewrites.

### Minimal Changes
- Change the smallest possible amount of code.
- Preserve existing naming conventions and patterns.
- Do not refactor unrelated code in the same change.
- One logical change per commit.

### Readability
- Code should be readable and maintainable.
- Prefer clarity over cleverness.
- Include proper error handling.
- Follow language best practices.
- Use type hints for all function signatures.

## Fiona-Specific Conventions

### Imports
- Standard library imports first, then third-party, then local.
- Within a package, prefer relative imports.
- Public API exposed via `__init__.py` with explicit `__all__`.

### Thread Safety
- Use `threading.Lock` for simple mutual exclusion.
- Use `threading.RLock` for reentrant locks (e.g., recursive calls).
- Use `threading.Event` for blocking waits.
- Document thread safety guarantees in docstrings.

### Error Handling
- Define custom exceptions in `_errors.py` within each package.
- Derive from `FionaError` or appropriate base in `fiona/interfaces.py`.
- Use specific exception types, not generic `Exception`.
- Log errors with `get_logger(__name__).error()` before raising.

### Logging
- Use `fiona.logging.get_logger(__name__)` to obtain a logger.
- Log levels: DEBUG for details, INFO for milestones, WARNING for
  recoverable issues, ERROR for failures.
- Include relevant context in log messages (IDs, states, etc.).

### Testing
- Every new function/method should have a corresponding test.
- Tests mirror source structure under `tests/`.
- Use descriptive test names: `test_<behavior>_<condition>`.
- Prefer `pytest` assertions over `unittest.TestCase` methods.
- Contract tests for ABC implementations in `tests/contracts/`.

## What NOT to Do

- Do NOT use `bash` with `sed`, `awk`, `echo >`, or `cat <<EOF` for file
  modifications — use `edit` or `write` tools instead.
- Do NOT create documentation files (*.md) unless explicitly requested.
- Do NOT add emojis to code or documentation unless the user requests them.
- Do NOT rewrite git history unless explicitly requested.
- Do NOT make changes outside the scope of the current task.
- Do NOT introduce new dependencies without verifying they are necessary
  and compatible with the project's Python version.

## Code Review Checklist

Before submitting code for review:
- [ ] Does the code follow existing patterns in the project?
- [ ] Are there type hints on all function signatures?
- [ ] Is error handling appropriate?
- [ ] Are there tests for the new/changed code?
- [ ] Do existing tests still pass?
- [ ] Is the change minimal and focused?
- [ ] Are imports organized correctly?
- [ ] Is thread safety handled where needed?
