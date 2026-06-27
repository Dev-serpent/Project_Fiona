"""Exception hierarchy for the SciPhi framework.

All SciPhi-specific exceptions inherit from :exc:`SciPhiError`, allowing
callers to catch a single base type when desired.
"""


class SciPhiError(Exception):
    """Base exception for all SciPhi errors.

    All custom exceptions in the framework derive from this class so that
    top-level handlers can catch ``SciPhiError`` without needing to know
    about every concrete subtype.
    """


# ---------------------------------------------------------------------------
# Model errors
# ---------------------------------------------------------------------------

class ModelNotFoundError(SciPhiError):
    """Raised when a requested model cannot be found in the registry.

    Args:
        model_id: The identifier that was looked up.
        message: Optional human-readable description.
    """

    def __init__(self, model_id: str, message: str | None = None) -> None:
        self.model_id = model_id
        self.message = message or f"Model '{model_id}' not found in registry"
        super().__init__(self.message)


# ---------------------------------------------------------------------------
# Solver errors
# ---------------------------------------------------------------------------

class SolverNotFoundError(SciPhiError):
    """Raised when a requested solver cannot be found in the registry.

    Args:
        solver_id: The identifier that was looked up.
        message: Optional human-readable description.
    """

    def __init__(self, solver_id: str, message: str | None = None) -> None:
        self.solver_id = solver_id
        self.message = message or f"Solver '{solver_id}' not found in registry"
        super().__init__(self.message)


class NoSuitableSolverError(SciPhiError):
    """Raised when no registered solver can handle a computational problem.

    Args:
        form: The mathematical form that could not be matched.
        message: Optional human-readable description.
    """

    def __init__(self, form: str, message: str | None = None) -> None:
        self.form = form
        self.message = message or f"No solver available for form '{form}'"
        super().__init__(self.message)


class SimulationFailedError(SciPhiError):
    """Raised when a solver fails to produce a valid result.

    Args:
        solver_id: The solver that failed.
        reason: Optional description of the failure.
    """

    def __init__(self, solver_id: str, reason: str | None = None) -> None:
        self.solver_id = solver_id
        self.reason = reason or "Simulation failed without a specific reason"
        super().__init__(f"Solver '{solver_id}' failed: {self.reason}")


# ---------------------------------------------------------------------------
# Validation & compilation errors
# ---------------------------------------------------------------------------

class ValidationFailedError(SciPhiError):
    """Raised when validation checks are not satisfied.

    Args:
        summary: A summary of what failed.
        details: Optional list of individual check descriptions.
    """

    def __init__(self, summary: str, details: list[str] | None = None) -> None:
        self.summary = summary
        self.details = details or []
        super().__init__(f"Validation failed: {summary}")


class CompilationError(SciPhiError):
    """Raised when a scientific model cannot be compiled into a computational problem.

    Args:
        model_id: The model that could not be compiled.
        reason: Description of why compilation failed.
    """

    def __init__(self, model_id: str, reason: str) -> None:
        self.model_id = model_id
        self.reason = reason
        super().__init__(f"Compilation failed for model '{model_id}': {reason}")


# ---------------------------------------------------------------------------
# Query / input errors
# ---------------------------------------------------------------------------

class InvalidQueryError(SciPhiError):
    """Raised when a user query cannot be parsed or interpreted.

    Args:
        query: The original query string.
        reason: Description of why the query is invalid.
    """

    def __init__(self, query: str, reason: str) -> None:
        self.query = query
        self.reason = reason
        super().__init__(f"Invalid query '{query}': {reason}")
