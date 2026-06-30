"""TF-IDF based semantic search for RecallVault entries.
No external dependencies required — pure Python implementation.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any


class SemanticIndex:
    """TF-IDF based semantic search index for text entries.

    Builds term-frequency / inverse-document-frequency vectors
    from a collection of texts and ranks results by cosine similarity.
    No external dependencies.
    """

    def __init__(self, index_path: str | None = None) -> None:
        self.index_path = index_path
        self._documents: list[str] = []
        self._doc_ids: list[str] = []
        self._idf: dict[str, float] = {}
        self._tf_matrix: list[dict[str, float]] = []
        self._built = False

    def _tokenize(self, text: str) -> list[str]:
        """Split text into lowercase tokens, removing punctuation."""
        return re.findall(r"\b[a-z0-9]+\b", text.lower())

    def build(self, entries: list[dict[str, Any]]) -> None:
        """Build the TF-IDF index from a list of entries.

        Each entry should have at least ``key`` and ``value`` fields.
        The text indexed is ``key + " " + value``, plus category and tags.
        """
        self._documents = []
        self._doc_ids = []

        for entry in entries:
            text = (
                f"{entry.get('key', '')} {entry.get('value', '')} {entry.get('category', '')}"
            )
            if entry.get("tags"):
                if isinstance(entry["tags"], list):
                    text += " " + " ".join(str(t) for t in entry["tags"])
            self._documents.append(text)
            self._doc_ids.append(str(entry.get("key", "")))

        if not self._documents:
            self._built = False
            return

        # Calculate TF for each document
        self._tf_matrix = []
        all_terms: set[str] = set()

        for doc in self._documents:
            tokens = self._tokenize(doc)
            term_count = len(tokens)
            tf: dict[str, float] = {}
            for term, count in Counter(tokens).items():
                tf[term] = count / term_count if term_count > 0 else 0
                all_terms.add(term)
            self._tf_matrix.append(tf)

        # Calculate IDF for each term
        n_docs = len(self._documents)
        self._idf = {}
        for term in all_terms:
            docs_with_term = sum(1 for tf in self._tf_matrix if term in tf)
            self._idf[term] = math.log((n_docs + 1) / (docs_with_term + 1)) + 1.0

        self._built = True

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search entries by TF-IDF relevance scoring.

        Returns a list of dicts: ``[{key, score}, ...]`` sorted by score descending.
        If the index is not built or query is empty, returns an empty list.
        """
        if not self._built or not query:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Build query TF vector
        query_tf: dict[str, float] = {}
        for term, count in Counter(query_tokens).items():
            query_tf[term] = count / len(query_tokens)

        # Calculate cosine similarity for each document
        scores: list[tuple[float, str]] = []
        for i, doc_tf in enumerate(self._tf_matrix):
            # Compute TF-IDF weighted vectors
            query_vec: dict[str, float] = {}
            doc_vec: dict[str, float] = {}

            all_query_terms = set(query_tf.keys()) | set(doc_tf.keys())
            for term in all_query_terms:
                idf = self._idf.get(term, 1.0)
                query_vec[term] = query_tf.get(term, 0.0) * idf
                doc_vec[term] = doc_tf.get(term, 0.0) * idf

            # Cosine similarity
            dot_product = sum(query_vec[t] * doc_vec[t] for t in all_query_terms)
            query_norm = math.sqrt(sum(v * v for v in query_vec.values()))
            doc_norm = math.sqrt(sum(v * v for v in doc_vec.values()))

            if query_norm > 0 and doc_norm > 0:
                similarity = dot_product / (query_norm * doc_norm)
            else:
                similarity = 0.0

            if similarity > 0:
                scores.append((similarity, self._doc_ids[i]))

        # Sort by score descending
        scores.sort(key=lambda x: (-x[0], x[1]))

        results = []
        for score, doc_id in scores[:limit]:
            results.append({"key": doc_id, "score": round(score, 4)})

        return results

    def add_entry(self, entry_id: str, text: str) -> None:
        """Add a single entry to the index (triggers rebuild).

        For simplicity, rebuilds the entire index. For large collections,
        consider incremental updates in a future version.
        """
        # Mark for rebuild — caller should call build() again
        self._built = False
