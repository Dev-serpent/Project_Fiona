"""Tests for the BrowserManager state machine.

Uses a mock IBrowserProvider so Playwright is not required.
"""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock

import pytest

from BrowserAutomation._errors import BrowserError, BrowserLaunchError, BrowserNotRunning
from BrowserAutomation._manager import BrowserManager, BrowserManagerState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MOCK_CTX_COUNTER: int = 0


class _MockBrowserProvider:
    """Fake IBrowserProvider for testing the state machine."""

    def __init__(self) -> None:
        self.name = "mock"
        self._launch_fail = False
        self._crash_on_context = False

    def capabilities(self) -> set[str]:
        return {"mock"}

    async def launch(self, config: object) -> MagicMock:
        if self._launch_fail:
            raise RuntimeError("Launch failed (configured)")

        instance = MagicMock()
        instance.is_closed = False
        instance.pid = 12345

        async def close() -> None:
            instance.is_closed = True
            instance.pid = None

        instance.close = close

        async def create_context(**kwargs: object) -> MagicMock:
            if self._crash_on_context:
                raise RuntimeError("Crash on context create")

            global _MOCK_CTX_COUNTER  # noqa: PLW0603
            _MOCK_CTX_COUNTER += 1

            ctx = MagicMock()
            ctx.is_closed = False
            ctx.context_id = f"mock-ctx-{_MOCK_CTX_COUNTER}"

            async def close_ctx() -> None:
                ctx.is_closed = True

            ctx.close = close_ctx
            return ctx

        instance.create_context = create_context
        return instance


@pytest.fixture()
def mock_provider() -> _MockBrowserProvider:
    return _MockBrowserProvider()


@pytest.fixture()
def manager(mock_provider: _MockBrowserProvider) -> BrowserManager:
    return BrowserManager(provider=mock_provider)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_starts_stopped(self, manager: BrowserManager) -> None:
        assert manager.state == BrowserManagerState.STOPPED

    def test_has_config(self, manager: BrowserManager) -> None:
        assert manager.config is not None
        assert manager.config.browser_type == "chromium"


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStateTransitions:
    async def test_start_transition(self, manager: BrowserManager) -> None:
        await manager.start()
        assert manager.state == BrowserManagerState.RUNNING

    async def test_stop_from_running(self, manager: BrowserManager) -> None:
        await manager.start()
        await manager.stop()
        assert manager.state == BrowserManagerState.STOPPED

    async def test_double_start_is_safe(self, manager: BrowserManager) -> None:
        await manager.start()
        # Second start is a no-op when already running
        await manager.start()
        assert manager.state == BrowserManagerState.RUNNING

    async def test_double_stop_is_safe(self, manager: BrowserManager) -> None:
        await manager.start()
        await manager.stop()
        await manager.stop()  # second call is a no-op
        assert manager.state == BrowserManagerState.STOPPED

    async def test_stop_when_stopped_is_safe(self, manager: BrowserManager) -> None:
        await manager.stop()  # no-op
        assert manager.state == BrowserManagerState.STOPPED

    async def test_restart_from_running(self, manager: BrowserManager) -> None:
        await manager.start()
        await manager.restart()
        assert manager.state == BrowserManagerState.RUNNING

    async def test_restart_from_stopped(self, manager: BrowserManager) -> None:
        await manager.restart()
        assert manager.state == BrowserManagerState.RUNNING

    async def test_restart_from_error(self, manager: BrowserManager, mock_provider: _MockBrowserProvider) -> None:
        await manager.start()
        mock_provider._launch_fail = True
        # Force error by failing restart — manager wraps in BrowserLaunchError
        with pytest.raises(BrowserLaunchError):
            await manager.restart()

    async def test_start_failure_goes_to_error(self, mock_provider: _MockBrowserProvider) -> None:
        mock_provider._launch_fail = True
        mgr = BrowserManager(provider=mock_provider)  # type: ignore[arg-type]
        with pytest.raises(BrowserLaunchError):
            await mgr.start()
        assert mgr.state == BrowserManagerState.ERROR


# ---------------------------------------------------------------------------
# Context management
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestContextManagement:
    async def test_create_context(self, manager: BrowserManager) -> None:
        await manager.start()
        ctx = await manager.create_context()
        assert ctx is not None
        assert ctx.context_id is not None

    async def test_create_context_fails_when_stopped(self, manager: BrowserManager) -> None:
        with pytest.raises(BrowserNotRunning):
            await manager.create_context()

    async def test_create_context_fails_when_error(self, mock_provider: _MockBrowserProvider) -> None:
        mock_provider._launch_fail = True
        mgr = BrowserManager(provider=mock_provider)  # type: ignore[arg-type]
        with pytest.raises(BrowserLaunchError):
            await mgr.start()
        with pytest.raises(BrowserNotRunning):
            await mgr.create_context()

    async def test_context_is_isolated(self, manager: BrowserManager) -> None:
        await manager.start()
        ctx1 = await manager.create_context()
        ctx2 = await manager.create_context()
        assert ctx1.context_id != ctx2.context_id

    async def test_close_context(self, manager: BrowserManager) -> None:
        await manager.start()
        ctx = await manager.create_context()
        ctx_id = ctx.context_id
        await manager.close_context(ctx_id)
        assert ctx.is_closed

    async def test_stop_closes_all_contexts(self, manager: BrowserManager) -> None:
        await manager.start()
        ctx1 = await manager.create_context()
        ctx2 = await manager.create_context()
        await manager.stop()
        assert ctx1.is_closed
        assert ctx2.is_closed
        assert manager.state == BrowserManagerState.STOPPED


# ---------------------------------------------------------------------------
# Error / crash recovery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestErrorRecovery:
    async def test_crash_during_context_attempts_restart(self, mock_provider: _MockBrowserProvider) -> None:
        mgr = BrowserManager(provider=mock_provider)  # type: ignore[arg-type]
        await mgr.start()

        # Reset counter so this test is independent
        # Trigger crash, then auto-restart
        mock_provider._crash_on_context = True
        mock_provider._launch_fail = False

        with pytest.raises(BrowserError):
            await mgr.create_context()

        # The auto-restart should have been attempted and succeeded
        # (since _crash_on_context was True during the crash, then
        #  _handle_crash launches a new instance which works)
        assert mgr.state in (BrowserManagerState.RUNNING, BrowserManagerState.ERROR)

    async def test_auto_restart_once_on_crash(self, mock_provider: _MockBrowserProvider) -> None:
        mgr = BrowserManager(provider=mock_provider)  # type: ignore[arg-type]
        await mgr.start()
        # Make subsequent launches fail so auto-restart fails
        mock_provider._launch_fail = True
        # Trigger a crash by setting crash flag
        mock_provider._crash_on_context = True
        with pytest.raises(BrowserError):
            await mgr.create_context()
        # Should be in ERROR after exhausting auto-restart
        assert mgr.state == BrowserManagerState.ERROR

    async def test_manual_restart_after_error(self, mock_provider: _MockBrowserProvider) -> None:
        mgr = BrowserManager(provider=mock_provider)  # type: ignore[arg-type]
        await mgr.start()
        mock_provider._launch_fail = True
        mock_provider._crash_on_context = True
        with pytest.raises(BrowserError):
            await mgr.create_context()

        # Reset provider and restart manually
        mock_provider._launch_fail = False
        mock_provider._crash_on_context = False
        await mgr.restart()
        assert mgr.state == BrowserManagerState.RUNNING


# ---------------------------------------------------------------------------
# Concurrent access
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestConcurrency:
    async def test_concurrent_context_creation(self, manager: BrowserManager) -> None:
        await manager.start()
        results = await asyncio.gather(
            manager.create_context(),
            manager.create_context(),
            manager.create_context(),
            return_exceptions=True,
        )
        successes = [r for r in results if not isinstance(r, Exception)]
        assert len(successes) == 3

    async def test_state_is_thread_safe(self, manager: BrowserManager) -> None:
        """Verify that state reads don't block or corrupt under concurrency."""
        await manager.start()

        def read_state() -> None:
            for _ in range(100):
                _ = manager.state

        threads = [threading.Thread(target=read_state) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert manager.state == BrowserManagerState.RUNNING


# ---------------------------------------------------------------------------
# Error recovery (start from ERROR, start when already running)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGracefulStart:
    async def test_start_from_error(self, mock_provider: _MockBrowserProvider) -> None:
        """Starting from ERROR state should restart the browser."""
        # First, force a failure to get into ERROR state
        mock_provider._launch_fail = True
        mgr = BrowserManager(provider=mock_provider)  # type: ignore[arg-type]
        with pytest.raises(BrowserLaunchError):
            await mgr.start()
        assert mgr.state == BrowserManagerState.ERROR

        # Now fix the provider and start again from ERROR
        mock_provider._launch_fail = False
        await mgr.start()
        assert mgr.state == BrowserManagerState.RUNNING

    async def test_double_start_is_noop(self, manager: BrowserManager) -> None:
        """Starting when already RUNNING is a safe no-op."""
        await manager.start()
        assert manager.state == BrowserManagerState.RUNNING
        await manager.start()  # should not raise
        assert manager.state == BrowserManagerState.RUNNING
