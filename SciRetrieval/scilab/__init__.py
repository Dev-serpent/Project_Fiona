"""SciLab — post-retrieval processing pipeline.

Transforms normalised entity lists through parse, rank, deduplicate,
summarise, and context-generation stages.
"""

from SciRetrieval.scilab.engine import SciLabEngine
from SciRetrieval.scilab.parser import SciLabParser
from SciRetrieval.scilab.ranker import Ranker
from SciRetrieval.scilab.deduplicator import Deduplicator
from SciRetrieval.scilab.summarizer import Summarizer
from SciRetrieval.scilab.context_generator import ContextGenerator

__all__ = [
    "SciLabEngine",
    "SciLabParser",
    "Ranker",
    "Deduplicator",
    "Summarizer",
    "ContextGenerator",
]
