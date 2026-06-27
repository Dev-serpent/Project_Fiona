"""Bridge between Agent chat system and SciRetrieval pipeline."""

import asyncio
import logging
from typing import Any

from SciRetrieval.retrieval_manager import RetrievalManager
from SciRetrieval.models import SciLabResult, GetDataRequest, GetDataResponse
from SciRetrieval.errors import SciRetrievalError, NoProvidersAvailableError

logger = logging.getLogger(__name__)


class MainTextBridge:
    """Integration point between Agent chat loop and SciRetrieval.
    
    MainText is the user input in the chat UI. When a scientific query
    is detected, this bridge routes it through the retrieval pipeline
    and returns a user-facing response.
    """

    def __init__(self, retrieval_manager: RetrievalManager) -> None:
        self._manager = retrieval_manager

    async def on_scientific_query(
        self,
        query: str,
        *,
        conversation_id: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        """Handle a scientific query from MainText.
        
        Returns a user-facing response string.
        """
        try:
            result = await self._manager.retrieve(
                query,
                conversation_id=conversation_id,
                options=options,
            )
            return result.summary
        except NoProvidersAvailableError:
            return (
                "I couldn't find any scientific data sources for your query. "
                "Try rephrasing or asking about a different topic."
            )
        except SciRetrievalError as e:
            logger.exception("Scientific retrieval failed")
            return f"Sorry, I encountered an error while searching: {e}"

    async def on_get_data(
        self,
        provider: str,
        entity: str,
        options: dict[str, Any] | None = None,
    ) -> str:
        """Handle a direct GetData request (e.g. from CLI)."""
        request = GetDataRequest(
            provider=provider,
            entity=entity,
            options=options or {},
        )
        response = await self._manager.get_data(request)
        if response.error:
            return f"Error: {response.error}"
        if response.entity:
            props = "; ".join(
                f"{k}={v}" for k, v in response.entity.properties.items()
            )
            return (
                f"Entity: {response.entity.name}\n"
                f"Type: {response.entity.entity_type.value}\n"
                f"Source: {response.provider} (ID: {response.entity.source_id})\n"
                f"Properties: {props}"
            )
        return f"No entity found for '{entity}' in {provider}."

    def on_conversation_end(self, conversation_id: str) -> None:
        """Called when a chat conversation ends — clears conversation cache."""
        asyncio.ensure_future(
            self._manager.cache_manager.clear_conversation(conversation_id)
        )
