"""Small structured remembrance store for Fiona."""

from __future__ import annotations

from .semantic import SemanticIndex
from .vault import (
    DEFAULT_RECALL_PATH,
    RecallEntry,
    backup_recall,
    clear_recall,
    export_recall,
    forget,
    import_recall,
    list_categories,
    load_recall,
    recall_stats,
    remember,
    search_recall,
)

__all__ = [
    "DEFAULT_RECALL_PATH",
    "RecallEntry",
    "SemanticIndex",
    "backup_recall",
    "clear_recall",
    "export_recall",
    "forget",
    "import_recall",
    "list_categories",
    "load_recall",
    "recall_stats",
    "remember",
    "search_recall",
]
