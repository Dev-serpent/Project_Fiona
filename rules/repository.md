# Repository Navigation Rules

Rules for reading, understanding, and navigating the Fiona codebase.

## Before Making Changes

### Analyze First
Before editing any code:
1. Read the file you intend to modify.
2. Understand its role in the architecture.
3. Identify existing patterns and conventions.
4. Check if there are related tests.

### Search Before Create
Before creating a new file:
1. Search for existing files with similar purpose (`glob`, `grep`).
2. Check if the functionality can be added to an existing file.
3. Check if another sibling package already handles this concern.
4. Verify the naming convention matches the project style.

### Understand Dependencies
- Check `pyproject.toml` for package discovery and dependency declarations.
- If adding a new package, add it to `[tool.setuptools.packages]`.
- If adding a new CLI layer, add it to the dispatch in `fiona/cli.py`.
- If adding new public symbols, add them to the relevant `__init__.py` and `__all__`.

## Navigation Patterns

### Finding Entry Points
- CLI: `fiona/cli.py` → `main()` → `_build_parser()` → layer dispatch.
- Agent: `Agent/orchestrator.py` → `run_agent_goal()`.
- CAD server: `cad/server/_server.py` → `CadServer`.
- Tests: mirror source structure under `tests/`.

### Finding Interface Contracts
- Formal ABCs: `fiona/interfaces.py`.
- Contract tests: `tests/contracts/test_interface_contracts.py`.
- Each ABC has a corresponding contract test suite.

### Finding Configuration
- Build config: `pyproject.toml`.
- Git config: `.gitignore`.
- Agent instructions: `AGENTS.md` (repo root) and `.config/opencode/AGENTS.md`.

## Conventions to Follow

### Naming
- Python: `snake_case` for functions/variables, `PascalCase` for classes,
  `UPPER_CASE` for constants.
- Private module members: prefix with `_` (e.g., `_manager.py`, `_default_manager`).
- Test files: `test_<module_name>.py`.
- Test classes: `Test<ClassName>`.
- Test methods: `test_<behavior>`.

### Package Structure
- Each package has `__init__.py` with explicit `__all__`.
- Public API is explicitly exported; internals are prefixed with `_`.
- Relative imports preferred within a package.

### Error Handling
- Custom exceptions defined in `_errors.py` within each package.
- Error hierarchy matching `fiona.interfaces` error base classes.
- Thread safety via `threading.Lock` or `threading.RLock`.

## Verification Before Completion

Before declaring a task complete:
1. Run `git diff --stat` to verify changed files.
2. Run `pytest tests/` or the relevant test subset.
3. Check for any remaining `TODO`, `FIXME`, or `XXX` markers in changed code.
4. Verify no lint errors with `ruff` or `flake8` if configured.
