"""Tests for MainTextBridge — Agent chat / SciRetrieval integration.

Uses a mocked RetrievalManager to test the bridge in isolation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio

from SciRetrieval.maintext_bridge import MainTextBridge
from SciRetrieval.models import (
    GetDataRequest,
    GetDataResponse,
    SciLabResult,
    ScientificEntity,
)
from SciRetrieval.errors import SciRetrievalError, NoProvidersAvailableError
from SciPhi.interfaces.model import ScientificDomain


@pytest.fixture()
def mock_manager() -> MagicMock:
    """Mock RetrievalManager for bridge tests."""
    m = MagicMock()
    m.retrieve = AsyncMock(
        return_value=SciLabResult(
            summary="Found aspirin: a chemical compound with formula C9H8O4.",
            entities=[ScientificEntity(name="Aspirin")],
        )
    )
    m.get_data = AsyncMock(
        return_value=GetDataResponse(
            provider="pubchem",
            entity_key="aspirin",
            entity=ScientificEntity(
                name="Aspirin",
                source="pubchem",
                source_id="2244",
                properties={"mw": 180.16, "mf": "C9H8O4"},
            ),
        )
    )
    m.cache_manager = MagicMock()
    m.cache_manager.clear_conversation = AsyncMock(return_value=3)
    return m


@pytest.fixture()
def bridge(mock_manager: MagicMock) -> MainTextBridge:
    return MainTextBridge(mock_manager)


class TestOnScientificQuery:
    """MainTextBridge.on_scientific_query()"""

    async def test_returns_summary(self, bridge: MainTextBridge) -> None:
        result = await bridge.on_scientific_query("What is aspirin?")
        assert isinstance(result, str)
        assert "aspirin" in result.lower() or "Aspirin" in result

    async def test_passes_conversation_id(self, mock_manager: MagicMock) -> None:
        bridge = MainTextBridge(mock_manager)
        await bridge.on_scientific_query(
            "test", conversation_id="conv_123", options={"foo": "bar"}
        )
        mock_manager.retrieve.assert_awaited_once_with(
            "test",
            conversation_id="conv_123",
            options={"foo": "bar"},
        )

    async def test_no_providers_available_error(self, bridge: MainTextBridge, mock_manager: MagicMock) -> None:
        mock_manager.retrieve.side_effect = NoProvidersAvailableError("No providers")
        result = await bridge.on_scientific_query("test")
        assert "couldn't find" in result.lower() or "scientific data sources" in result

    async def test_generic_error_returns_message(self, bridge: MainTextBridge, mock_manager: MagicMock) -> None:
        mock_manager.retrieve.side_effect = SciRetrievalError("Something broke")
        result = await bridge.on_scientific_query("test")
        assert "error" in result.lower()

    async def test_unexpected_exception_still_handled(self, bridge: MainTextBridge, mock_manager: MagicMock) -> None:
        """Unexpected non-SciRetrieval exceptions propagate."""
        mock_manager.retrieve.side_effect = RuntimeError("Unexpected")
        with pytest.raises(RuntimeError):
            await bridge.on_scientific_query("test")


class TestOnGetData:
    """MainTextBridge.on_get_data()"""

    async def test_returns_formatted_entity(self, bridge: MainTextBridge) -> None:
        result = await bridge.on_get_data("pubchem", "aspirin")
        assert isinstance(result, str)
        assert "Entity:" in result
        assert "Aspirin" in result
        assert "Source:" in result

    async def test_error_response(self, bridge: MainTextBridge, mock_manager: MagicMock) -> None:
        mock_manager.get_data.return_value = GetDataResponse(
            provider="pubchem",
            entity_key="aspirin",
            error="Provider not found",
        )
        result = await bridge.on_get_data("pubchem", "aspirin")
        assert "Error:" in result

    async def test_no_entity_found(self, bridge: MainTextBridge, mock_manager: MagicMock) -> None:
        mock_manager.get_data.return_value = GetDataResponse(
            provider="pubchem",
            entity_key="unknown",
            entity=None,
        )
        result = await bridge.on_get_data("pubchem", "unknown")
        assert "No entity found" in result

    async def test_passes_options(self, mock_manager: MagicMock) -> None:
        bridge = MainTextBridge(mock_manager)
        await bridge.on_get_data("pubchem", "aspirin", options={"fields": ["mw"]})
        mock_manager.get_data.assert_awaited_once()
        request = mock_manager.get_data.await_args[0][0]
        assert isinstance(request, GetDataRequest)
        assert request.options == {"fields": ["mw"]}


class TestOnConversationEnd:
    """MainTextBridge.on_conversation_end()"""

    async def test_delegates_to_cache_manager(self, bridge: MainTextBridge, mock_manager: MagicMock) -> None:
        bridge.on_conversation_end("conv_123")
        # Since on_conversation_end uses asyncio.ensure_future, we need to
        # give the event loop a chance to run
        import asyncio
        await asyncio.sleep(0.01)
        mock_manager.cache_manager.clear_conversation.assert_called_with("conv_123")
