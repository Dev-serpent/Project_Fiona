"""SciLab pipeline orchestrator.

Runs the complete post-retrieval processing pipeline:
parse → rank → deduplicate → summarise → context generation.

Implements :class:`SciRetrieval.interfaces.ISciLabProcessor`.
"""

from __future__ import annotations

import logging
import time

from SciRetrieval.interfaces import ISciLabProcessor
from SciRetrieval.models import RetrievalContext, SciLabResult, ScientificEntity
from SciRetrieval.scilab.context_generator import ContextGenerator
from SciRetrieval.scilab.deduplicator import Deduplicator
from SciRetrieval.scilab.parser import SciLabParser
from SciRetrieval.scilab.ranker import Ranker
from SciRetrieval.scilab.summarizer import Summarizer

logger = logging.getLogger(__name__)


class SciLabEngine(ISciLabProcessor):
    """Orchestrates the SciLab processing pipeline.

    Args:
        parser: Entity property parser.
        ranker: Relevance scorer.
        deduplicator: Final safety-net deduplicator.
        summarizer: Natural-language summary generator.
        context_generator: Structured context block generator.
    """

    def __init__(
        self,
        parser: SciLabParser | None = None,
        ranker: Ranker | None = None,
        deduplicator: Deduplicator | None = None,
        summarizer: Summarizer | None = None,
        context_generator: ContextGenerator | None = None,
    ) -> None:
        self._parser = parser or SciLabParser()
        self._ranker = ranker or Ranker()
        self._deduplicator = deduplicator or Deduplicator()
        self._summarizer = summarizer or Summarizer()
        self._context_generator = context_generator or ContextGenerator()

    async def process(
        self, entities: list[ScientificEntity], context: RetrievalContext
    ) -> SciLabResult:
        """Run the full SciLab pipeline.

        Args:
            entities: Normalised (and optionally resolved) entities.
            context: The original retrieval context.

        Returns:
            A :class:`SciLabResult` with summary, ranked entities,
            relationships, context, and processing time.
        """
        start = time.monotonic()

        # 1. Parse entity properties
        parsed = self._parser.parse(entities)

        # 2. Rank by relevance to query
        ranked = self._ranker.rank(parsed, context.query)

        # 3. Final deduplication safety net
        deduped = self._deduplicator.deduplicate(ranked)

        # 4. Generate summary
        summary = self._summarizer.summarize(deduped, context.query)

        # 5. Generate structured context
        ctx = self._context_generator.generate(deduped, summary)

        elapsed = (time.monotonic() - start) * 1000

        # Collect all relationships
        all_rels = list(
            {
                (r.source_id, r.target_id, r.relationship_type): r
                for e in deduped
                for r in e.relationships
            }.values()
        )

        return SciLabResult(
            summary=summary,
            entities=deduped,
            relationships=all_rels,
            context=ctx,
            processing_time_ms=elapsed,
        )
