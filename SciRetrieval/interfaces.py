"""Re-export of SciRetrieval ABCs from the single source of truth.

All abstract interface contracts live in ``fiona.interfaces``.
This module is a convenience re-export for SciRetrieval-internal imports.
"""

from fiona.interfaces import (
    ICacheBackend,
    IEntityResolver,
    IIntentDomainClassifier,
    INormalizer,
    IProvider,
    IRetrievalManager,
    ISciLabProcessor,
)

__all__ = [
    "IIntentDomainClassifier",
    "IProvider",
    "INormalizer",
    "IEntityResolver",
    "ISciLabProcessor",
    "ICacheBackend",
    "IRetrievalManager",
]
