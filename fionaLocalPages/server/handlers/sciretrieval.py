"""SciRetrieval API endpoints for FionaLocalPages.

All retrieval goes through the DI-resolved bridge — no direct
provider access in this module.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aiohttp.web import Request, Response, json_response

from fiona.di import get_sci_retrieval_bridge
from fionaLocalPages.server.middleware import ApiError
from SciRetrieval.errors import SciRetrievalError, NoProvidersAvailableError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy bridge singleton (cached at module level)
# ---------------------------------------------------------------------------

_bridge: Any = None


def _get_bridge():
    global _bridge  # noqa: PLW0603
    if _bridge is None:
        _bridge = get_sci_retrieval_bridge()
    return _bridge


def _project_root() -> Path:
    """Return the project root (parent of ``fionaLocalPages/``)."""
    return Path(__file__).resolve().parents[3]


def _keyword_path() -> Path:
    """Return the path to the SciRetrieval keyword list."""
    return _project_root() / "SciRetrieval" / "data" / "keywordlist.json"


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def sciretrieval_search(request: Request) -> Response:
    """POST /api/v1/sciretrieval/search

    Body: { query, conversation_id? }
    Returns: { summary, query }
    """
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    query = body.get("query", "").strip()
    if not query:
        raise ApiError(400, "Missing required field: query")

    conversation_id = body.get("conversation_id")

    try:
        bridge = _get_bridge()
        result = await bridge.on_scientific_query(
            query, conversation_id=conversation_id
        )
        return json_response({
            "ok": True,
            "data": {
                "summary": result,
                "query": query,
            },
        })
    except NoProvidersAvailableError:
        return json_response({
            "ok": True,
            "data": {
                "summary": "No scientific data sources available for this query.",
                "query": query,
            },
        })
    except SciRetrievalError as e:
        logger.exception("SciRetrieval search failed")
        return json_response({
            "ok": True,
            "data": {
                "summary": f"Scientific search failed: {e}",
                "query": query,
                "error": str(e),
            },
        })


async def sciretrieval_classify(request: Request) -> Response:
    """POST /api/v1/sciretrieval/classify

    Body: { query }
    Returns: { primary_domain, secondary_domain, intent, confidence, matched_keywords }
    """
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    query = body.get("query", "").strip()
    if not query:
        raise ApiError(400, "Missing required field: query")

    try:
        from SciRetrieval.router import Router

        router = Router(_keyword_path())
        result = await router.classify(query)
        return json_response({
            "ok": True,
            "data": {
                "primary_domain": (
                    result.primary_domain.name if result.primary_domain else None
                ),
                "secondary_domain": (
                    result.secondary_domain.name if result.secondary_domain else None
                ),
                "intent": result.intent,
                "confidence": result.confidence,
                "matched_keywords": result.matched_keywords or [],
            },
        })
    except Exception as e:
        raise ApiError(500, f"Classification failed: {e}") from e


async def sciretrieval_providers(_request: Request) -> Response:
    """GET /api/v1/sciretrieval/providers

    Returns: { providers: { name: [domains] } }
    """
    try:
        bridge = _get_bridge()
        info = bridge._manager._registry.list_providers()  # noqa: SLF001
        return json_response({
            "ok": True,
            "data": {"providers": info},
        })
    except Exception as e:
        raise ApiError(500, f"Failed to list providers: {e}") from e


async def sciretrieval_getdata(request: Request) -> Response:
    """POST /api/v1/sciretrieval/getdata

    Body: { provider, entity, options? }
    Returns entity info.
    """
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    provider = body.get("provider", "").strip()
    entity = body.get("entity", "").strip()
    if not provider or not entity:
        raise ApiError(400, "Missing required fields: provider, entity")

    try:
        bridge = _get_bridge()
        result = await bridge.on_get_data(
            provider, entity, body.get("options")
        )
        return json_response({
            "ok": True,
            "data": {"result": result},
        })
    except SciRetrievalError as e:
        return json_response({
            "ok": True,
            "data": {"result": f"Error: {e}"},
        })


async def sciretrieval_cache_clear(_request: Request) -> Response:
    """POST /api/v1/sciretrieval/cache/clear

    Evicts expired entries from all SciRetrieval caches.
    """
    try:
        bridge = _get_bridge()
        await bridge._manager.cache_manager.evict_expired_all()  # noqa: SLF001
        return json_response({
            "ok": True,
            "data": {"message": "Caches cleared."},
        })
    except Exception as e:
        raise ApiError(500, f"Failed to clear caches: {e}") from e


async def sciretrieval_enrich(request: Request) -> Response:
    """POST /api/v1/sciretrieval/enrich — for Agent page

    Body: { message, conversation_id? }
    Returns: { is_scientific, context?, domain?, confidence?, intent? }

    Detects if a user message is scientific and returns enriched context.
    """
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    message = body.get("message", "").strip()
    if not message:
        raise ApiError(400, "Missing required field: message")

    try:
        # 1. Classify the message
        from SciRetrieval.router import Router

        router = Router(_keyword_path())
        classification = await router.classify(message)

        # Only enrich if confidence is high enough
        if classification.confidence < 0.3:
            return json_response({
                "ok": True,
                "data": {
                    "is_scientific": False,
                    "confidence": classification.confidence,
                    "domain": None,
                    "intent": classification.intent,
                },
            })

        # 2. Run full retrieval
        conversation_id = body.get("conversation_id")
        bridge = _get_bridge()
        result = await bridge.on_scientific_query(
            message,
            conversation_id=conversation_id,
        )

        return json_response({
            "ok": True,
            "data": {
                "is_scientific": True,
                "context": result,
                "domain": (
                    classification.primary_domain.name
                    if classification.primary_domain
                    else None
                ),
                "intent": classification.intent,
                "confidence": classification.confidence,
                "matched_keywords": classification.matched_keywords or [],
            },
        })
    except Exception as e:
        logger.exception("SciRetrieval enrichment failed")
        return json_response({
            "ok": True,
            "data": {
                "is_scientific": False,
                "error": str(e),
            },
        })
