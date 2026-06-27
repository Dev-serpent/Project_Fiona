"""Intent and domain classifier for scientific queries.

Uses a keyword-list approach — no ML dependency — to map free-text
user queries to a :class:`ScientificDomain` and an intent category.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from SciRetrieval.errors import ClassificationError
from SciRetrieval.interfaces import IIntentDomainClassifier
from SciRetrieval.models import IntentDomainResult
from SciPhi.interfaces.model import ScientificDomain

logger = logging.getLogger(__name__)

# Mapping from keyword-list domain names to ScientificDomain enum values
_DOMAIN_MAP: dict[str, ScientificDomain] = {
    "biology": ScientificDomain.BIOLOGY,
    "chemistry": ScientificDomain.CHEMISTRY,
    "physics": ScientificDomain.PHYSICS,
}


class Router(IIntentDomainClassifier):
    """Keyword-based domain + intent classifier.

    Loads a ``keywordlist.json`` file on initialisation and uses it to
    score each domain based on keyword overlap with the query.
    """

    def __init__(self, keyword_path: str | Path | None = None) -> None:
        """Initialise the router.

        Args:
            keyword_path: Path to ``keywordlist.json``.  If *None* the
                built-in data file is used.
        """
        if keyword_path is None:
            keyword_path = Path(__file__).resolve().parent / "data" / "keywordlist.json"
        self._keyword_path = Path(keyword_path)
        self._data: dict[str, Any] = self._load_keywords(self._keyword_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def classify(self, query: str) -> IntentDomainResult:
        """Classify the query into a domain and intent.

        Args:
            query: Free-text user query.

        Returns:
            An :class:`IntentDomainResult` with the best-guess domain
            and intent.

        Raises:
            ClassificationError: If the keyword data is malformed.
        """
        try:
            query_lower = query.lower().strip()
            tokens = self._tokenize(query_lower)

            # Score each domain
            domain_scores: dict[str, float] = {}
            domain_keywords: dict[str, list[str]] = {}
            for domain_name, cfg in self._data.items():
                if domain_name == "intent":
                    continue
                keywords = cfg.get("keywords", [])
                weight = cfg.get("weight", 1.0)
                matched = [kw for kw in keywords if kw in query_lower]
                score = len(matched) * weight
                if score > 0:
                    domain_scores[domain_name] = score
                    domain_keywords[domain_name] = matched

            if not domain_scores:
                # Fall back to generic / unknown
                return IntentDomainResult(
                    primary_domain=ScientificDomain.BIOLOGY,
                    intent="generic",
                    confidence=0.0,
                )

            # Pick primary and secondary
            sorted_domains = sorted(domain_scores.items(), key=lambda x: -x[1])
            primary_name = sorted_domains[0][0]
            primary = _DOMAIN_MAP.get(primary_name, ScientificDomain.BIOLOGY)

            secondary: ScientificDomain | None = None
            if len(sorted_domains) > 1:
                secondary_name = sorted_domains[1][0]
                secondary = _DOMAIN_MAP.get(secondary_name)

            # Normalise confidence
            total_score = sum(domain_scores.values())
            max_score = max(domain_scores.values())
            # Scale confidence based on token coverage
            token_ratio = max_score / max(len(tokens), 1)
            confidence = min(token_ratio / 3.0, 1.0)  # cap at 1.0

            # Detect intent
            intent = self._detect_intent(query_lower)

            all_matched = list(
                set(
                    kw
                    for matched_list in domain_keywords.values()
                    for kw in matched_list
                )
            )

            return IntentDomainResult(
                primary_domain=primary,
                secondary_domain=secondary,
                intent=intent,
                confidence=confidence,
                matched_keywords=all_matched,
            )
        except Exception as exc:
            raise ClassificationError(f"Failed to classify query: {exc}") from exc

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _tokenize(self, text: str) -> list[str]:
        """Split *text* into lowercase tokens."""
        return re.findall(r"[a-z0-9]+", text)

    def _detect_intent(self, query_lower: str) -> str:
        """Detect intent category by checking intent keyword patterns."""
        intent_data = self._data.get("intent", {})
        scores: dict[str, int] = {}
        for intent_name, patterns in intent_data.items():
            score = 0
            for pattern in patterns:
                if pattern in query_lower:
                    # Longer pattern matches are stronger signals
                    score += len(pattern.split())
                    # Also check as a phrase boundary match
                    if query_lower.startswith(pattern):
                        score += 2
            if score > 0:
                scores[intent_name] = score

        if not scores:
            return "generic"

        return max(scores, key=scores.get)

    @staticmethod
    def _load_keywords(path: Path) -> dict[str, Any]:
        """Load the keyword list JSON file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return dict(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            logger.warning("Could not load keyword list at %s: %s", path, exc)
            # Return minimal fallback so the system can still function
            return {
                "biology": {"keywords": [], "weight": 1.0},
                "chemistry": {"keywords": [], "weight": 1.0},
                "physics": {"keywords": [], "weight": 1.0},
                "intent": {},
            }
