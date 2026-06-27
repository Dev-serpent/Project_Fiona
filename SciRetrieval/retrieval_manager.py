"""Pipeline orchestrator for scientific knowledge retrieval.

The :class:`RetrievalManager` ties together classification, provider
selection, concurrent fetching, normalisation, entity resolution, SciLab
processing, and caching into a single ``retrieve()`` call.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from SciRetrieval.cache_manager import CacheManager
from SciRetrieval.errors import (
    NoProvidersAvailableError,
    ProviderNotFoundError,
    RetrievalManagerError,
)
from SciRetrieval.interfaces import (
    IEntityResolver,
    IIntentDomainClassifier,
    INormalizer,
    IProvider,
    IRetrievalManager,
    ISciLabProcessor,
)
from SciRetrieval.models import (
    CachePolicy,
    GetDataRequest,
    GetDataResponse,
    IntentDomainResult,
    RetrievalContext,
    SciLabResult,
    ScientificEntity,
)
from SciRetrieval.provider_registry import ProviderRegistry

logger = logging.getLogger(__name__)


class RetrievalManager(IRetrievalManager):
    """Orchestrates the end-to-end scientific knowledge retrieval pipeline.

    Args:
        classifier: Domain + intent classifier.
        registry: Provider registry for selecting providers.
        normalizer: Converts raw provider data to entities.
        resolver: Resolves aliases and merges cross-provider duplicates.
        scilab: SciLab processing pipeline.
        cache_manager: Cache lifecycle manager.
        max_retries: Maximum retry attempts per provider fetch.
        base_delay: Initial backoff delay in seconds.
        max_delay: Maximum backoff delay in seconds.
        request_timeout: Per-request timeout in seconds.
        rate_limit_delay: Minimum gap between requests to the same provider.
    """

    def __init__(
        self,
        classifier: IIntentDomainClassifier,
        registry: ProviderRegistry,
        normalizer: INormalizer,
        resolver: IEntityResolver,
        scilab: ISciLabProcessor,
        cache_manager: CacheManager,
        *,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        request_timeout: float = 30.0,
        rate_limit_delay: float = 0.5,
    ) -> None:
        self._classifier = classifier
        self._registry = registry
        self._normalizer = normalizer
        self._resolver = resolver
        self._scilab = scilab
        self._cache = cache_manager

        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._request_timeout = request_timeout
        self._rate_limit_delay = rate_limit_delay

        # Per-provider rate-limit tracking
        self._last_request_time: dict[str, float] = {}

    @property
    def cache_manager(self) -> CacheManager:
        """Expose the cache manager for bridge and integration use."""
        return self._cache

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def retrieve(
        self,
        query: str,
        *,
        conversation_id: str | None = None,
        options: dict | None = None,
    ) -> SciLabResult:
        """Execute the full retrieval pipeline.

        Args:
            query: Free-text user query.
            conversation_id: Optional conversation ID for caching.
            options: Free-form options dict.

        Returns:
            A :class:`SciLabResult` with summary, entities, and context.
        """
        # 1. Check conversation cache
        if conversation_id:
            cache_key = f"conv:{conversation_id}:{_cache_key_for_query(query)}"
            cached = await self._cache.conversation.get(cache_key)
            if cached is not None:
                logger.debug("Conversation cache hit for %s", cache_key)
                result = cached.value
                if isinstance(result, SciLabResult):
                    return result

        # 2. Classify query
        intent_result: IntentDomainResult = await self._classifier.classify(query)

        # 3. Build retrieval context
        domains = [intent_result.primary_domain]
        if intent_result.secondary_domain:
            domains.append(intent_result.secondary_domain)

        context = RetrievalContext(
            query=query,
            domains=domains,
            conversation_id=conversation_id,
            options={
                "intent": intent_result.intent,
                "confidence": intent_result.confidence,
                **(options or {}),
            },
        )

        # 4. Select providers
        providers = self._select_providers(domains)
        if not providers:
            raise NoProvidersAvailableError(
                f"No providers available for domains: {[d.name for d in domains]}"
            )

        # 5. Fetch from all providers concurrently
        raw_results = await self._fetch_all(providers, context)

        if not raw_results:
            logger.warning("All providers returned no data for query: %s", query)
            return SciLabResult(
                summary=f"No scientific data found for query: '{query}'.",
                context=f"[SciRetrieval Context]\nNo results for query: {query}\n"
                f"Domains: {[d.name for d in domains]}\nIntent: {intent_result.intent}",
            )

        # 6. Normalize each result
        all_entities: list[ScientificEntity] = []
        for raw in raw_results:
            try:
                entities = await self._normalizer.normalize(raw)
                all_entities.extend(entities)
            except Exception as exc:
                logger.warning(
                    "Normalization failed for provider %s: %s", raw.provider, exc
                )

        if not all_entities:
            logger.warning("No entities extracted from any provider")
            return SciLabResult(
                summary=f"No scientific data found for query: '{query}'.",
            )

        # 7. Entity resolution (alias resolution + cross-provider merge)
        try:
            resolved_entities = await self._resolver.resolve(all_entities)
        except Exception as exc:
            logger.warning("Entity resolution failed: %s", exc)
            resolved_entities = all_entities  # graceful degradation

        # 8. SciLab processing
        result: SciLabResult = await self._scilab.process(resolved_entities, context)

        # 9. Cache the result
        if conversation_id:
            policy = CachePolicy(ttl_seconds=300)
            try:
                await self._cache.conversation.set(
                    cache_key, result, policy=policy  # type: ignore[arg-type]
                )
            except Exception as exc:
                logger.warning("Failed to cache result: %s", exc)

        return result

    async def get_data(self, request: GetDataRequest) -> GetDataResponse:
        """Fetch data for a specific entity from a specific provider.

        Args:
            request: Specifies provider, entity identifier, and options.

        Returns:
            A :class:`GetDataResponse` with the result.
        """
        # 1. Check dataset cache
        cache_key = f"dataset:{request.provider}:{_cache_key_for_query(request.entity)}"
        cached = await self._cache.dataset.get(cache_key)
        if cached is not None:
            response = cached.value
            if isinstance(response, GetDataResponse):
                return response

        # 2. Find provider
        provider = self._registry.find_by_name(request.provider)
        if provider is None:
            return GetDataResponse(
                provider=request.provider,
                entity_key=request.entity,
                error=f"Provider '{request.provider}' not found",
            )

        # 3. Build context and fetch
        context = RetrievalContext(
            query=request.entity,
            domains=list(provider.supported_domains),
            options=dict(request.options),
        )

        try:
            raw = await self._fetch_with_retry(provider, context)
        except Exception as exc:
            return GetDataResponse(
                provider=request.provider,
                entity_key=request.entity,
                raw_data={},
                error=str(exc),
            )

        if raw is None:
            return GetDataResponse(
                provider=request.provider,
                entity_key=request.entity,
                raw_data={},
                error="Provider returned no data",
            )

        # 4. Normalize and resolve
        try:
            entities = await self._normalizer.normalize(raw)
            if entities:
                entities = await self._resolver.resolve(entities)
        except Exception as exc:
            return GetDataResponse(
                provider=request.provider,
                entity_key=request.entity,
                raw_data=raw.raw_data,
                error=f"Normalization failed: {exc}",
            )

        entity = entities[0] if entities else None

        # 5. Cache
        response = GetDataResponse(
            provider=request.provider,
            entity_key=request.entity,
            entity=entity,
            raw_data=raw.raw_data,
        )
        policy = CachePolicy(ttl_seconds=86400, persistent=True)
        try:
            await self._cache.dataset.set(cache_key, response, policy=policy)  # type: ignore[arg-type]
        except Exception as exc:
            logger.warning("Failed to cache dataset response: %s", exc)

        return response

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _select_providers(self, domains: list) -> list[IProvider]:
        """Collect providers for the given domains, primary first."""
        seen: set[str] = set()
        providers: list[IProvider] = []
        for domain in domains:
            for p in self._registry.get_providers(domain):
                if p.provider_name not in seen:
                    seen.add(p.provider_name)
                    providers.append(p)
        return providers

    async def _fetch_all(
        self, providers: list[IProvider], context: RetrievalContext
    ) -> list:
        """Fetch from all providers concurrently.

        Returns a list of :class:`RawProviderResult` from successful
        fetches.  Failures are logged but do not block other providers.
        """
        tasks = [self._fetch_with_retry(p, context) for p in providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful: list = []
        for provider, result in zip(providers, results):
            if isinstance(result, Exception):
                logger.warning(
                    "Provider %s failed: %s", provider.provider_name, result
                )
            elif result is not None:
                successful.append(result)
        return successful

    async def _fetch_with_retry(
        self, provider: IProvider, context: RetrievalContext
    ) -> Any:
        """Fetch from a single provider with exponential backoff.

        Returns:
            A :class:`RawProviderResult`, or *None* if all retries failed.
        """
        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                # Rate-limit: enforce gap between calls to same provider
                await self._enforce_rate_limit(provider.provider_name)

                result = await provider.fetch(context)
                self._last_request_time[provider.provider_name] = time.monotonic()
                return result
            except NoProvidersAvailableError:
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    delay = min(
                        self._base_delay * (2 ** (attempt - 1)), self._max_delay
                    )
                    logger.debug(
                        "Retry %d/%d for %s in %.1fs: %s",
                        attempt,
                        self._max_retries,
                        provider.provider_name,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)

        logger.warning(
            "Provider %s failed after %d retries: %s",
            provider.provider_name,
            self._max_retries,
            last_exc,
        )
        return None

    async def _enforce_rate_limit(self, provider_name: str) -> None:
        """Ensure at least ``rate_limit_delay`` seconds between calls."""
        last = self._last_request_time.get(provider_name, 0.0)
        elapsed = time.monotonic() - last
        if elapsed < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - elapsed)


def _cache_key_for_query(query: str) -> str:
    """Generate a consistent cache key from a query string."""
    import hashlib

    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
