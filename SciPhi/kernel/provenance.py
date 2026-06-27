"""Provenance Tracker — records every decision made during an investigation.

The :class:`ProvenanceTracker` maintains a structured record of the full
scientific decision chain: the original query, the model selected, the
equations and constants used, the solver configuration, assumptions,
approximations, validation results, and uncertainty estimates.

This module also defines the :class:`ProvenanceEntry` dataclass that
represents a single provenance record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from SciPhi.kernel.evaluator import ValidationCheck
    from SciPhi.kernel.uncertainty import UncertaintyEstimate


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProvenanceEntry:
    """A complete provenance record for a single investigation.

    Attributes:
        record_id: A unique identifier for this provenance record.
        query: The original user query that initiated the investigation.
        model_id: The identifier of the scientific model used, or ``None``
            if no simulation was performed.
        model_version: The version identifier of the model, or ``None``.
        equations_used: A list of equation names or expressions that were
            part of the computation.
        constants_used: A list of dictionaries describing the physical
            constants used (each with keys like ``"name"``, ``"symbol"``,
            ``"value"``, ``"unit"``).
        data_sources: A list of references to external data sources used.
        solver_id: The identifier of the solver used, or ``None``.
        solver_config: The configuration or parameters passed to the solver.
        assumptions: A list of assumption statements that were in effect.
        approximations: A list of approximations made during compilation
            or solving.
        validation_results: The :class:`ValidationCheck` instances produced
            during validation.
        uncertainty: The :class:`UncertaintyEstimate` from uncertainty
            analysis, or ``None``.
        timestamp: An ISO-8601 formatted timestamp string.
    """

    record_id: str
    query: str
    model_id: str | None = None
    model_version: str | None = None
    equations_used: list[str] = field(default_factory=list)
    constants_used: list[dict] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)
    solver_id: str | None = None
    solver_config: dict = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    approximations: list[str] = field(default_factory=list)
    validation_results: list[ValidationCheck] = field(default_factory=list)
    uncertainty: UncertaintyEstimate | None = None
    timestamp: str = ""


# ---------------------------------------------------------------------------
# Simple in-memory provenance store
# ---------------------------------------------------------------------------

class ProvenanceTracker:
    """Records and retrieves provenance entries for scientific investigations.

    This implementation uses an in-memory dictionary as its backing store.
    A production deployment would replace this with a persistent database.
    """

    def __init__(self) -> None:
        self._store: dict[str, ProvenanceEntry] = {}
        self._next_id: int = 0

    async def record(self, entry: ProvenanceEntry) -> str:
        """Store a provenance record and return its record ID.

        Args:
            entry: The :class:`ProvenanceEntry` to record. If the entry does
                not have a ``record_id`` set, one will be auto-generated. If
                the entry has no ``timestamp``, the current UTC time will be
                used.

        Returns:
            The ``record_id`` assigned to the stored entry.
        """
        record_id = entry.record_id or self._generate_id()
        timestamp = entry.timestamp or self._now()

        finalized = ProvenanceEntry(
            record_id=record_id,
            query=entry.query,
            model_id=entry.model_id,
            model_version=entry.model_version,
            equations_used=list(entry.equations_used),
            constants_used=list(entry.constants_used),
            data_sources=list(entry.data_sources),
            solver_id=entry.solver_id,
            solver_config=dict(entry.solver_config),
            assumptions=list(entry.assumptions),
            approximations=list(entry.approximations),
            validation_results=list(entry.validation_results),
            uncertainty=entry.uncertainty,
            timestamp=timestamp,
        )

        self._store[record_id] = finalized
        return record_id

    async def get(self, record_id: str) -> ProvenanceEntry | None:
        """Retrieve a provenance record by its ID.

        Args:
            record_id: The unique identifier of the record to retrieve.

        Returns:
            The :class:`ProvenanceEntry` if found, or ``None``.
        """
        return self._store.get(record_id)

    async def get_by_query(self, query: str) -> list[ProvenanceEntry]:
        """Find all provenance records whose query contains the given string.

        Args:
            query: A substring to search for in stored queries.

        Returns:
            A list of matching :class:`ProvenanceEntry` instances (empty if
            none match).
        """
        query_lower = query.lower()
        return [
            entry
            for entry in self._store.values()
            if query_lower in entry.query.lower()
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_id(self) -> str:
        """Generate a unique provenance record ID."""
        self._next_id += 1
        return f"prov-{self._next_id:06d}"

    @staticmethod
    def _now() -> str:
        """Return the current UTC time as an ISO-8601 string."""
        return datetime.now(timezone.utc).isoformat()
