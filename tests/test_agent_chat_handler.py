"""Tests for Agent.chat_handler — AgentChatHandler (Milestone 3)."""

from __future__ import annotations

import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from Agent import (
    AgentChatHandler,
    CancellationToken,
    CancelledError,
    ChatMessage,
    ChatStore,
    OllamaClient,
    OllamaError,
    Personality,
    PersonalityRegistry,
)


# ======================================================================
# Fixtures & helpers
# ======================================================================

def _make_chat_store() -> ChatStore:
    """Create an isolated :class:`ChatStore` backed by a temp file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    store = ChatStore(tmp.name)
    # Attach the path so the test can clean up.
    store._tmp_path = tmp.name  # type: ignore[attr-defined]
    return store


def _make_handler(
    chat_store: ChatStore | None = None,
    client: OllamaClient | None = None,
    registry: PersonalityRegistry | None = None,
) -> AgentChatHandler:
    if chat_store is None:
        chat_store = _make_chat_store()
    handler = AgentChatHandler(
        chat_store=chat_store,
        client=client,
        personality_registry=registry,
    )
    return handler


# ======================================================================
# AgentChatHandler tests
# ======================================================================

class AgentChatHandlerInitTests(unittest.TestCase):
    """Verify construction and default-dependency creation."""

    def test_requires_chat_store(self) -> None:
        store = _make_chat_store()
        handler = AgentChatHandler(chat_store=store)
        self.assertIs(handler._chat_store, store)

    def test_creates_default_client(self) -> None:
        store = _make_chat_store()
        handler = AgentChatHandler(chat_store=store)
        self.assertIsInstance(handler._client, OllamaClient)

    def test_accepts_custom_client(self) -> None:
        store = _make_chat_store()
        client = MagicMock(spec=OllamaClient)
        handler = AgentChatHandler(chat_store=store, client=client)
        self.assertIs(handler._client, client)

    def test_uses_provided_registry(self) -> None:
        store = _make_chat_store()
        registry = PersonalityRegistry.get_instance()
        handler = AgentChatHandler(chat_store=store, personality_registry=registry)
        self.assertIs(handler._registry, registry)

    def test_creates_default_registry(self) -> None:
        store = _make_chat_store()
        handler = AgentChatHandler(chat_store=store)
        self.assertIsInstance(handler._registry, PersonalityRegistry)


class AgentChatHandlerCreateSessionTests(unittest.TestCase):
    """Delegation to ChatStore.create_session."""

    def setUp(self) -> None:
        self.store = _make_chat_store()
        self.handler = _make_handler(chat_store=self.store)

    def tearDown(self) -> None:
        self.store.close()

    def test_create_session_returns_string(self) -> None:
        session_id = self.handler.create_session(personality="general")
        self.assertIsInstance(session_id, str)
        self.assertTrue(len(session_id) > 0)

    def test_create_session_persists_in_store(self) -> None:
        session_id = self.handler.create_session(personality="general")
        sessions = self.store.list_sessions()
        ids = [s["session_id"] for s in sessions]
        self.assertIn(session_id, ids)

    def test_create_session_stores_personality(self) -> None:
        session_id = self.handler.create_session(personality="planner")
        sessions = self.store.list_sessions()
        for s in sessions:
            if s["session_id"] == session_id:
                self.assertEqual(s["personality"], "planner")
                return
        self.fail("session not found")

    def test_create_session_tracks_internal_map(self) -> None:
        session_id = self.handler.create_session(personality="analyst")
        self.assertEqual(
            self.handler._session_personality.get(session_id),
            "analyst",
        )

    def test_default_personality_is_general(self) -> None:
        session_id = self.handler.create_session()
        sessions = self.store.list_sessions()
        for s in sessions:
            if s["session_id"] == session_id:
                self.assertEqual(s["personality"], "general")
                return
        self.fail("session not found")


class AgentChatHandlerListDeleteSessionsTests(unittest.TestCase):
    """Delegation to ChatStore.list_sessions / delete_session."""

    def setUp(self) -> None:
        self.store = _make_chat_store()
        self.handler = _make_handler(chat_store=self.store)

    def tearDown(self) -> None:
        self.store.close()

    def test_list_sessions_empty_initially(self) -> None:
        self.assertEqual(self.handler.list_sessions(), [])

    def test_list_sessions_returns_created(self) -> None:
        sid = self.handler.create_session()
        sessions = self.handler.list_sessions()
        self.assertIn(sid, [s["session_id"] for s in sessions])

    def test_delete_session_removes_from_list(self) -> None:
        sid = self.handler.create_session()
        self.handler.delete_session(sid)
        sessions = self.handler.list_sessions()
        self.assertNotIn(sid, [s["session_id"] for s in sessions])

    def test_delete_session_clears_internal_map(self) -> None:
        sid = self.handler.create_session(personality="engineer")
        self.handler.delete_session(sid)
        self.assertNotIn(sid, self.handler._session_personality)


class AgentChatHandlerSendMessageTests(unittest.TestCase):
    """Full send_message flow with mocked OllamaClient."""

    def setUp(self) -> None:
        self.store = _make_chat_store()
        self.mock_client = MagicMock(spec=OllamaClient)
        self.mock_client.ask.return_value = "Hello, human!"
        self.handler = _make_handler(
            chat_store=self.store,
            client=self.mock_client,
        )
        self.session_id = self.handler.create_session(personality="general")

    def tearDown(self) -> None:
        self.store.close()

    def _run_send(self, message: str = "Hi") -> tuple[list, list, bool]:
        """Helper: run send_message synchronously by waiting for the thread."""
        token = CancellationToken()
        messages: list[tuple[str, str]] = []
        errors: list[str] = []
        completed = False

        def on_msg(role: str, content: str) -> None:
            messages.append((role, content))

        def on_err(err: str) -> None:
            errors.append(err)

        def on_done() -> None:
            nonlocal completed
            completed = True

        self.handler.send_message(
            session_id=self.session_id,
            message=message,
            token=token,
            on_message=on_msg,
            on_error=on_err,
            on_complete=on_done,
        )

        # Wait for the daemon thread to finish
        deadline = time.time() + 5
        while not completed and not errors and time.time() < deadline:
            time.sleep(0.01)

        return messages, errors, completed

    def test_send_message_stores_user_message(self) -> None:
        self._run_send("Hello")
        msgs = self.store.get_messages(self.session_id)
        roles = [m.role for m in msgs]
        self.assertIn("user", roles)

    def test_send_message_stores_agent_response(self) -> None:
        self._run_send("Hello")
        msgs = self.store.get_messages(self.session_id)
        roles = [m.role for m in msgs]
        self.assertIn("agent", roles)

    def test_send_message_calls_ollama_client(self) -> None:
        self._run_send("Hello")
        self.mock_client.ask.assert_called_once()
        call_kwargs = self.mock_client.ask.call_args[1]
        self.assertIn("system_prompt", call_kwargs)

    def test_send_message_calls_on_message_for_user(self) -> None:
        messages, _, completed = self._run_send("Test message")
        self.assertTrue(completed)
        user_msgs = [r for r, c in messages if r == "user"]
        self.assertIn("Test message", [c for r, c in messages if r == "user"])

    def test_send_message_calls_on_message_for_agent(self) -> None:
        messages, _, completed = self._run_send("Hi")
        self.assertTrue(completed)
        agent_contents = [c for r, c in messages if r == "agent"]
        self.assertIn("Hello, human!", agent_contents)

    def test_send_message_calls_on_complete(self) -> None:
        _, _, completed = self._run_send("Hi")
        self.assertTrue(completed)

    def test_send_message_uses_personality_system_prompt(self) -> None:
        self._run_send("Hi")
        call_kwargs = self.mock_client.ask.call_args[1]
        # The "general" personality's system prompt should be used
        general = PersonalityRegistry.get_instance().get("general")
        self.assertEqual(call_kwargs["system_prompt"], general.system_prompt)

    def test_send_message_with_system_prompt_override(self) -> None:
        """system_prompt_override replaces the personality's system prompt."""
        token = CancellationToken()
        messages: list[tuple[str, str]] = []
        errors: list[str] = []
        completed = False

        def on_msg(role: str, content: str) -> None:
            messages.append((role, content))

        def on_err(err: str) -> None:
            errors.append(err)

        def on_done() -> None:
            nonlocal completed
            completed = True

        override = "You are a test bot. Keep responses short."
        self.handler.send_message(
            session_id=self.session_id,
            message="Hello",
            token=token,
            system_prompt_override=override,
            on_message=on_msg,
            on_error=on_err,
            on_complete=on_done,
        )

        deadline = time.time() + 5
        while not completed and not errors and time.time() < deadline:
            time.sleep(0.01)

        self.assertTrue(completed)
        call_kwargs = self.mock_client.ask.call_args[1]
        self.assertEqual(call_kwargs["system_prompt"], override)

    def test_system_prompt_override_none_uses_default(self) -> None:
        """When system_prompt_override is None, the personality prompt is used."""
        token = CancellationToken()
        completed = False

        def on_msg(role: str, content: str) -> None:
            pass

        def on_err(err: str) -> None:
            pass

        def on_done() -> None:
            nonlocal completed
            completed = True

        self.handler.send_message(
            session_id=self.session_id,
            message="Hello",
            token=token,
            on_message=on_msg,
            on_error=on_err,
            on_complete=on_done,
        )

        deadline = time.time() + 5
        while not completed and time.time() < deadline:
            time.sleep(0.01)

        call_kwargs = self.mock_client.ask.call_args[1]
        general = PersonalityRegistry.get_instance().get("general")
        self.assertEqual(call_kwargs["system_prompt"], general.system_prompt)

    def test_context_window_loaded(self) -> None:
        """Verify that get_context_window is consulted (indirectly)."""
        # Add a prior message to the session
        self.store.add_message(self.session_id, "user", "Earlier message", personality="general")
        self.store.add_message(self.session_id, "agent", "Earlier response", personality="general")

        self._run_send("Follow-up")
        # The prompt should contain both the earlier messages and the new one
        prompt = self.mock_client.ask.call_args[1]["prompt"]
        self.assertIn("Earlier message", prompt)
        self.assertIn("Earlier response", prompt)
        self.assertIn("Follow-up", prompt)


class AgentChatHandlerCancellationTests(unittest.TestCase):
    """Cancellation at pre-flight and post-LLM checkpoints."""

    def setUp(self) -> None:
        self.store = _make_chat_store()
        self.mock_client = MagicMock(spec=OllamaClient)
        self.mock_client.ask.return_value = "Should not be stored"
        self.handler = _make_handler(
            chat_store=self.store,
            client=self.mock_client,
        )
        self.session_id = self.handler.create_session()

    def tearDown(self) -> None:
        self.store.close()

    def test_cancellation_before_send_stores_cancelled_message(self) -> None:
        token = CancellationToken()
        token.cancel()  # Cancel immediately

        errors: list[str] = []
        completed = False

        def on_msg(role: str, content: str) -> None:
            pass

        def on_err(err: str) -> None:
            errors.append(err)

        def on_done() -> None:
            nonlocal completed
            completed = True

        self.handler.send_message(
            session_id=self.session_id,
            message="This should be cancelled",
            token=token,
            on_message=on_msg,
            on_error=on_err,
            on_complete=on_done,
        )

        deadline = time.time() + 5
        while not errors and time.time() < deadline:
            time.sleep(0.01)

        self.assertIn("Operation cancelled", errors)
        self.assertFalse(completed)
        # The cancelled message should be in the store
        msgs = self.store.get_messages(self.session_id)
        roles = [m.role for m in msgs]
        self.assertIn("cancelled", roles)
        # The user message should NOT be stored (cancelled before add_message)
        self.assertNotIn("user", roles)

    def test_cancellation_does_not_call_ollama(self) -> None:
        token = CancellationToken()
        token.cancel()

        errors: list[str] = []
        completed = False

        def on_msg(role: str, content: str) -> None:
            pass

        def on_err(err: str) -> None:
            errors.append(err)

        def on_done() -> None:
            nonlocal completed
            completed = True

        self.handler.send_message(
            session_id=self.session_id,
            message="Cancelled",
            token=token,
            on_message=on_msg,
            on_error=on_err,
            on_complete=on_done,
        )

        deadline = time.time() + 5
        while not errors and time.time() < deadline:
            time.sleep(0.01)

        self.mock_client.ask.assert_not_called()


class AgentChatHandlerOllamaErrorTests(unittest.TestCase):
    """Error handling when OllamaClient raises OllamaError."""

    def setUp(self) -> None:
        self.store = _make_chat_store()
        self.mock_client = MagicMock(spec=OllamaClient)
        self.mock_client.ask.side_effect = OllamaError("Ollama is down")
        self.handler = _make_handler(
            chat_store=self.store,
            client=self.mock_client,
        )
        self.session_id = self.handler.create_session()

    def tearDown(self) -> None:
        self.store.close()

    def test_ollama_error_stores_error_message(self) -> None:
        errors: list[str] = []

        def on_msg(role: str, content: str) -> None:
            pass

        def on_err(err: str) -> None:
            errors.append(err)

        def on_done() -> None:
            pass

        self.handler.send_message(
            session_id=self.session_id,
            message="Test",
            token=CancellationToken(),
            on_message=on_msg,
            on_error=on_err,
            on_complete=on_done,
        )

        deadline = time.time() + 5
        while not errors and time.time() < deadline:
            time.sleep(0.01)

        self.assertIn("Ollama is down", errors)
        msgs = self.store.get_messages(self.session_id)
        roles = [m.role for m in msgs]
        self.assertIn("error", roles)


class AgentChatHandlerThreadSafetyTests(unittest.TestCase):
    """Verify send_message runs in a daemon thread."""

    def setUp(self) -> None:
        self.store = _make_chat_store()
        self.mock_client = MagicMock(spec=OllamaClient)
        self.mock_client.ask.return_value = "Response"
        self.handler = _make_handler(
            chat_store=self.store,
            client=self.mock_client,
        )
        self.session_id = self.handler.create_session()

    def tearDown(self) -> None:
        self.store.close()

    def test_send_message_is_daemon(self) -> None:
        """The worker thread should be a daemon thread."""
        main_thread = threading.current_thread()
        thread_ref = [None]

        original = self.mock_client.ask

        def ask_side_effect(*args: object, **kwargs: object) -> str:
            thread_ref[0] = threading.current_thread()
            return original(*args, **kwargs)

        self.mock_client.ask.side_effect = ask_side_effect

        token = CancellationToken()
        errors: list = []
        completed = False

        def on_msg(r: str, c: str) -> None:
            pass

        def on_err(e: str) -> None:
            errors.append(e)

        def on_done() -> None:
            nonlocal completed
            completed = True

        self.handler.send_message(
            session_id=self.session_id,
            message="Test daemon",
            token=token,
            on_message=on_msg,
            on_error=on_err,
            on_complete=on_done,
        )

        deadline = time.time() + 5
        while (thread_ref[0] is None or not completed) and time.time() < deadline:
            time.sleep(0.01)

        self.assertIsNotNone(thread_ref[0])
        self.assertTrue(thread_ref[0].daemon)
        self.assertNotEqual(thread_ref[0], main_thread)


class AgentChatHandlerContextWindowTests(unittest.TestCase):
    """Test that context window is built from stored messages."""

    def setUp(self) -> None:
        self.store = _make_chat_store()
        self.mock_client = MagicMock(spec=OllamaClient)
        self.mock_client.ask.return_value = "Context-aware response"
        self.handler = _make_handler(
            chat_store=self.store,
            client=self.mock_client,
        )
        self.session_id = self.handler.create_session()

        # Pre-populate with some history
        self.store.add_message(self.session_id, "user", "First message", personality="general")
        self.store.add_message(self.session_id, "agent", "First response", personality="general")
        self.store.add_message(self.session_id, "user", "Second message", personality="general")
        self.store.add_message(self.session_id, "agent", "Second response", personality="general")

    def tearDown(self) -> None:
        self.store.close()

    def test_context_includes_prior_messages(self) -> None:
        errors: list[str] = []
        completed = False

        def on_msg(r: str, c: str) -> None:
            pass

        def on_err(e: str) -> None:
            errors.append(e)

        def on_done() -> None:
            nonlocal completed
            completed = True

        self.handler.send_message(
            session_id=self.session_id,
            message="Current message",
            token=CancellationToken(),
            on_message=on_msg,
            on_error=on_err,
            on_complete=on_done,
        )

        deadline = time.time() + 5
        while not completed and time.time() < deadline:
            time.sleep(0.01)

        self.assertTrue(completed)
        prompt = self.mock_client.ask.call_args[1]["prompt"]
        self.assertIn("First message", prompt)
        self.assertIn("First response", prompt)
        self.assertIn("Second message", prompt)
        self.assertIn("Second response", prompt)
        self.assertIn("Current message", prompt)

    def test_context_uses_format_context_static_method(self) -> None:
        """Verify _format_context produces expected output."""
        msgs = [
            ChatMessage(id=1, session_id="s", role="user", content="Hi",
                        personality="general", timestamp=100.0),
            ChatMessage(id=2, session_id="s", role="agent", content="Hello",
                        personality="general", timestamp=101.0),
        ]
        result = AgentChatHandler._format_context(msgs)
        self.assertIn("User: Hi", result)
        self.assertIn("Assistant: Hello", result)

    def test_context_handles_empty_list(self) -> None:
        result = AgentChatHandler._format_context([])
        self.assertEqual(result, "")


class AgentChatHandlerBackwardCompatTests(unittest.TestCase):
    """Existing Agent imports still work after adding AgentChatHandler."""

    def test_agent_module_exports_chat_handler(self) -> None:
        from Agent import AgentChatHandler
        self.assertTrue(hasattr(AgentChatHandler, "send_message"))
        self.assertTrue(hasattr(AgentChatHandler, "create_session"))
        self.assertTrue(hasattr(AgentChatHandler, "list_sessions"))
        self.assertTrue(hasattr(AgentChatHandler, "delete_session"))

    def test_existing_exports_unchanged(self) -> None:
        from Agent import (
            AgentOrchestrator,
            CancellationToken,
            CancelledError,
            ChatMessage,
            ChatStore,
            ChatStoreError,
            DEFAULT_OLLAMA_BASE_URL,
            OllamaClient,
            OllamaError,
            PermissionEnforcer,
            Personality,
            PersonalityRegistry,
            SafeActionRouter,
            estimate_tokens,
        )
        # Just verifying imports don't raise
        self.assertTrue(CancellationToken is not None)

    def test_package_structure_unchanged(self) -> None:
        import Agent
        self.assertIn("AgentChatHandler", Agent.__all__)
        self.assertIn("ChatMessage", Agent.__all__)
        self.assertIn("ChatStore", Agent.__all__)
        self.assertIn("OllamaClient", Agent.__all__)
        self.assertIn("Personality", Agent.__all__)
        self.assertIn("PersonalityRegistry", Agent.__all__)


# ======================================================================
# Smoke test: PhiConnect.gui can still be imported
# ======================================================================

class PhiConnectGuiSmokeTests(unittest.TestCase):
    """Smoke tests that PhiConnect.gui still imports correctly."""

    def test_phiconnect_app_can_be_imported(self) -> None:
        from PhiConnect.gui import PhiConnectApp
        self.assertTrue(callable(PhiConnectApp))

    def test_launch_phiconnect_exported(self) -> None:
        from PhiConnect.gui import launch_phiconnect
        self.assertTrue(callable(launch_phiconnect))


if __name__ == "__main__":
    unittest.main()
