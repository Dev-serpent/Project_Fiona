"""Tests for PhiConnect.foreman_handler — ForemanChatHandler (Milestone 5)."""

from __future__ import annotations

import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from Agent import (
    CancellationToken,
    CancelledError,
    ChatStore,
    ForemanAgent,
    ForemanConfig,
    OllamaClient,
    OllamaError,
    PersonalityRegistry,
)
from PhiConnect.foreman_handler import ForemanChatHandler


# ======================================================================
# Fixtures & helpers
# ======================================================================


def _make_chat_store() -> ChatStore:
    """Create an isolated :class:`ChatStore` backed by a temp file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    store = ChatStore(tmp.name)
    store._tmp_path = tmp.name  # type: ignore[attr-defined]
    return store


def _make_handler(
    chat_store: ChatStore | None = None,
    client: OllamaClient | None = None,
    registry: PersonalityRegistry | None = None,
    config: ForemanConfig | None = None,
) -> ForemanChatHandler:
    if chat_store is None:
        chat_store = _make_chat_store()
    handler = ForemanChatHandler(
        chat_store=chat_store,
        client=client,
        personality_registry=registry,
        config=config,
    )
    return handler


# ======================================================================
# ForemanChatHandler construction tests
# ======================================================================


class ForemanChatHandlerInitTests(unittest.TestCase):
    """Verify construction and default-dependency creation."""

    def test_requires_chat_store(self) -> None:
        store = _make_chat_store()
        handler = ForemanChatHandler(chat_store=store)
        self.assertIs(handler._chat_store, store)

    def test_creates_default_client(self) -> None:
        store = _make_chat_store()
        handler = ForemanChatHandler(chat_store=store)
        self.assertIsInstance(handler._client, OllamaClient)

    def test_accepts_custom_client(self) -> None:
        store = _make_chat_store()
        client = MagicMock(spec=OllamaClient)
        handler = ForemanChatHandler(chat_store=store, client=client)
        self.assertIs(handler._client, client)

    def test_uses_provided_registry(self) -> None:
        store = _make_chat_store()
        registry = PersonalityRegistry.get_instance()
        handler = ForemanChatHandler(
            chat_store=store, personality_registry=registry,
        )
        self.assertIs(handler._registry, registry)

    def test_creates_default_registry(self) -> None:
        store = _make_chat_store()
        handler = ForemanChatHandler(chat_store=store)
        self.assertIsInstance(handler._registry, PersonalityRegistry)

    def test_uses_provided_config(self) -> None:
        store = _make_chat_store()
        config = ForemanConfig(max_sub_agents=3, parallel_by_default=True)
        handler = ForemanChatHandler(chat_store=store, config=config)
        self.assertIs(handler._config, config)
        self.assertTrue(handler._config.parallel_by_default)
        self.assertEqual(handler._config.max_sub_agents, 3)

    def test_creates_default_config(self) -> None:
        store = _make_chat_store()
        handler = ForemanChatHandler(chat_store=store)
        self.assertIsInstance(handler._config, ForemanConfig)
        self.assertFalse(handler._config.parallel_by_default)

    def test_foreman_disabled_by_default(self) -> None:
        store = _make_chat_store()
        handler = ForemanChatHandler(chat_store=store)
        self.assertFalse(handler.foreman_enabled)

    def test_creates_internal_foreman_agent(self) -> None:
        store = _make_chat_store()
        handler = ForemanChatHandler(chat_store=store)
        self.assertIsInstance(handler._foreman, ForemanAgent)

    def test_creates_internal_simple_handler(self) -> None:
        store = _make_chat_store()
        handler = ForemanChatHandler(chat_store=store)
        # The simple_handler should be set up and usable
        from Agent.chat_handler import AgentChatHandler
        self.assertIsInstance(handler._simple_handler, AgentChatHandler)


# ======================================================================
# Foreman toggle tests
# ======================================================================


class ForemanChatHandlerToggleTests(unittest.TestCase):
    """Toggle foreman_enabled on/off."""

    def setUp(self) -> None:
        self.store = _make_chat_store()
        self.handler = _make_handler(chat_store=self.store)

    def tearDown(self) -> None:
        self.store.close()

    def test_foreman_enabled_defaults_to_false(self) -> None:
        self.assertFalse(self.handler.foreman_enabled)

    def test_set_foreman_enabled_true(self) -> None:
        self.handler.foreman_enabled = True
        self.assertTrue(self.handler.foreman_enabled)

    def test_set_foreman_enabled_false(self) -> None:
        self.handler.foreman_enabled = True
        self.handler.foreman_enabled = False
        self.assertFalse(self.handler.foreman_enabled)

    def test_foreman_enabled_coerces_to_bool(self) -> None:
        self.handler.foreman_enabled = 1
        self.assertTrue(self.handler.foreman_enabled)

        self.handler.foreman_enabled = 0
        self.assertFalse(self.handler.foreman_enabled)


# ======================================================================
# Config tests
# ======================================================================


class ForemanChatHandlerConfigTests(unittest.TestCase):
    """Config property and update_config."""

    def setUp(self) -> None:
        self.store = _make_chat_store()
        self.handler = _make_handler(chat_store=self.store)

    def tearDown(self) -> None:
        self.store.close()

    def test_config_property_read_only_access(self) -> None:
        cfg = self.handler.config
        self.assertIsInstance(cfg, ForemanConfig)

    def test_update_config_parallel(self) -> None:
        self.handler.update_config(parallel_by_default=True)
        self.assertTrue(self.handler.config.parallel_by_default)

    def test_update_config_max_sub_agents(self) -> None:
        self.handler.update_config(max_sub_agents=7)
        self.assertEqual(self.handler.config.max_sub_agents, 7)

    def test_update_config_max_turns(self) -> None:
        self.handler.update_config(max_turns_per_sub_agent=20)
        self.assertEqual(self.handler.config.max_turns_per_sub_agent, 20)

    def test_update_config_multiple_fields(self) -> None:
        self.handler.update_config(
            parallel_by_default=True,
            max_sub_agents=3,
            max_turns_per_sub_agent=15,
        )
        self.assertTrue(self.handler.config.parallel_by_default)
        self.assertEqual(self.handler.config.max_sub_agents, 3)
        self.assertEqual(self.handler.config.max_turns_per_sub_agent, 15)

    def test_update_config_unknown_kwargs_ignored(self) -> None:
        self.handler.update_config(unknown_field=42)
        # Should not raise and not change anything
        self.assertFalse(self.handler.config.parallel_by_default)

    def test_update_config_recreates_foreman_agent(self) -> None:
        old_foreman = self.handler._foreman
        self.handler.update_config(max_sub_agents=8)
        new_foreman = self.handler._foreman
        self.assertIsNot(old_foreman, new_foreman)

    def test_config_resets_after_update(self) -> None:
        """Verify that config is a new frozen instance after each update."""
        cfg_before = self.handler.config
        self.handler.update_config(max_sub_agents=4)
        cfg_after = self.handler.config
        self.assertIsNot(cfg_before, cfg_after)


# ======================================================================
# Session management tests
# ======================================================================


class ForemanChatHandlerSessionTests(unittest.TestCase):
    """Delegation to AgentChatHandler for session management."""

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
        sessions = self.handler.list_sessions()
        ids = [s["session_id"] for s in sessions]
        self.assertIn(session_id, ids)

    def test_create_session_tracks_personality(self) -> None:
        session_id = self.handler.create_session(personality="planner")
        self.assertEqual(
            self.handler._session_personality.get(session_id),
            "planner",
        )

    def test_default_personality_is_general(self) -> None:
        session_id = self.handler.create_session()
        self.assertEqual(
            self.handler._session_personality.get(session_id),
            "general",
        )

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

    def test_multiple_sessions(self) -> None:
        sid1 = self.handler.create_session(personality="general")
        sid2 = self.handler.create_session(personality="analyst")
        sessions = self.handler.list_sessions()
        ids = [s["session_id"] for s in sessions]
        self.assertIn(sid1, ids)
        self.assertIn(sid2, ids)
        self.assertEqual(
            self.handler._session_personality.get(sid2),
            "analyst",
        )


# ======================================================================
# Send message — foreman disabled (delegates to AgentChatHandler)
# ======================================================================


class ForemanChatHandlerSendSimpleTests(unittest.TestCase):
    """When foreman is disabled, send_message delegates to AgentChatHandler."""

    def setUp(self) -> None:
        self.store = _make_chat_store()
        self.mock_client = MagicMock(spec=OllamaClient)
        self.mock_client.ask.return_value = "Simple response"
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
        completed = [False]  # use list for mutable closure

        def on_msg(role: str, content: str) -> None:
            messages.append((role, content))

        def on_err(err: str) -> None:
            errors.append(err)

        def on_done() -> None:
            completed[0] = True

        self.handler.send_message(
            session_id=self.session_id,
            message=message,
            token=token,
            on_message=on_msg,
            on_error=on_err,
            on_complete=on_done,
        )

        deadline = time.time() + 5
        while not completed[0] and not errors and time.time() < deadline:
            time.sleep(0.01)

        return messages, errors, completed[0]

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

    def test_send_message_calls_on_message_for_user(self) -> None:
        messages, _, completed = self._run_send("Test message")
        self.assertTrue(completed)
        user_roles = [r for r, c in messages if r == "user"]
        self.assertIn("user", user_roles)

    def test_send_message_calls_on_complete(self) -> None:
        _, _, completed = self._run_send("Hi")
        self.assertTrue(completed)

    def test_no_system_messages_when_foreman_disabled(self) -> None:
        """When foreman is off, no 'system' messages should appear."""
        messages, _, completed = self._run_send("Hi")
        self.assertTrue(completed)
        system_msgs = [(r, c) for r, c in messages if r == "system"]
        self.assertEqual(system_msgs, [])

    def test_foreman_enabled_still_uses_simple_when_false(self) -> None:
        """With foreman_enabled=False (default), use simple chat."""
        self.assertFalse(self.handler.foreman_enabled)
        messages, _, completed = self._run_send("Hello")
        self.assertTrue(completed)
        # Verify only user and agent messages (no system)
        roles = {r for r, c in messages}
        self.assertIn("user", roles)
        self.assertIn("agent", roles)
        self.assertNotIn("system", roles)


# ======================================================================
# Send message — foreman enabled (uses ForemanAgent)
# ======================================================================


class ForemanChatHandlerSendForemanTests(unittest.TestCase):
    """When foreman is enabled, send_message uses ForemanAgent."""

    def setUp(self) -> None:
        self.store = _make_chat_store()
        self.mock_foreman = MagicMock(spec=ForemanAgent)
        self.mock_foreman.execute.return_value = "Orchestrated response"

        self.handler = _make_handler(
            chat_store=self.store,
            client=MagicMock(spec=OllamaClient),
        )
        # Replace the real foreman with our mock
        self.handler._foreman = self.mock_foreman
        self.session_id = self.handler.create_session(personality="general")
        self.handler.foreman_enabled = True

    def tearDown(self) -> None:
        self.store.close()

    def _run_send(self, message: str = "Hi") -> tuple[list, list, bool]:
        """Helper: run send_message synchronously by waiting for the thread."""
        token = CancellationToken()
        messages: list[tuple[str, str]] = []
        errors: list[str] = []
        completed = [False]

        def on_msg(role: str, content: str) -> None:
            messages.append((role, content))

        def on_err(err: str) -> None:
            errors.append(err)

        def on_done() -> None:
            completed[0] = True

        self.handler.send_message(
            session_id=self.session_id,
            message=message,
            token=token,
            on_message=on_msg,
            on_error=on_err,
            on_complete=on_done,
        )

        deadline = time.time() + 5
        while not completed[0] and not errors and time.time() < deadline:
            time.sleep(0.01)

        return messages, errors, completed[0]

    def test_send_message_calls_foreman_execute(self) -> None:
        # Use a task message (action verb) so QueryDetector routes to foreman
        self._run_send("Build a module that answers geography questions")
        self.mock_foreman.execute.assert_called_once()
        call_args = self.mock_foreman.execute.call_args[1]
        self.assertIn("goal", call_args)
        self.assertEqual(
            call_args["goal"],
            "Build a module that answers geography questions",
        )

    def test_send_message_system_status_on_enabled(self) -> None:
        """Foreman-enabled sends 'Planning...' system message."""
        # Use a task message so QueryDetector routes to foreman
        messages, _, completed = self._run_send("Build a bridge")
        self.assertTrue(completed)
        system_contents = [c for r, c in messages if r == "system"]
        self.assertIn("Planning...", system_contents)

    def test_send_message_stores_user_message(self) -> None:
        self._run_send("Build a module")
        msgs = self.store.get_messages(self.session_id)
        roles = [m.role for m in msgs]
        self.assertIn("user", roles)

    def test_send_message_stores_agent_response(self) -> None:
        self._run_send("Create a data pipeline")
        msgs = self.store.get_messages(self.session_id)
        roles = [m.role for m in msgs]
        self.assertIn("agent", roles)

    def test_send_message_calls_on_complete(self) -> None:
        _, _, completed = self._run_send("Build a bridge")
        self.assertTrue(completed)

    def test_foreman_execute_receives_correct_personality(self) -> None:
        """Verify personality is passed to foreman.execute()."""
        # Create a session with a specific personality
        sid = self.handler.create_session(personality="engineer")
        self.handler.foreman_enabled = True

        token = CancellationToken()
        errors: list[str] = []
        completed = [False]

        def on_msg(r: str, c: str) -> None:
            pass

        def on_err(e: str) -> None:
            errors.append(e)

        def on_done() -> None:
            completed[0] = True

        self.handler.send_message(
            session_id=sid,
            message="Build a bridge",
            token=token,
            on_message=on_msg,
            on_error=on_err,
            on_complete=on_done,
        )

        deadline = time.time() + 5
        while not completed[0] and not errors and time.time() < deadline:
            time.sleep(0.01)

        self.mock_foreman.execute.assert_called()
        # Get the last call (or only call)
        call_kwargs = self.mock_foreman.execute.call_args[1]
        self.assertEqual(call_kwargs.get("personality"), "engineer")


# ======================================================================
# Force foreman
# ======================================================================


class ForemanChatHandlerForceForemanTests(unittest.TestCase):
    """force_foreman parameter overrides the foreman_enabled flag."""

    def setUp(self) -> None:
        self.store = _make_chat_store()
        self.mock_foreman = MagicMock(spec=ForemanAgent)
        self.mock_foreman.execute.return_value = "Forced foreman response"

        self.handler = _make_handler(
            chat_store=self.store,
            client=MagicMock(spec=OllamaClient),
        )
        self.handler._foreman = self.mock_foreman
        self.session_id = self.handler.create_session(personality="general")
        # Ensure foreman is OFF by default
        self.assertFalse(self.handler.foreman_enabled)

    def tearDown(self) -> None:
        self.store.close()

    def _run_send_force(self, message: str = "Hi") -> tuple[list, list, bool]:
        """Helper with force_foreman=True."""
        token = CancellationToken()
        messages: list[tuple[str, str]] = []
        errors: list[str] = []
        completed = [False]

        def on_msg(role: str, content: str) -> None:
            messages.append((role, content))

        def on_err(err: str) -> None:
            errors.append(err)

        def on_done() -> None:
            completed[0] = True

        self.handler.send_message(
            session_id=self.session_id,
            message=message,
            token=token,
            force_foreman=True,
            on_message=on_msg,
            on_error=on_err,
            on_complete=on_done,
        )

        deadline = time.time() + 5
        while not completed[0] and not errors and time.time() < deadline:
            time.sleep(0.01)

        return messages, errors, completed[0]

    def test_force_foreman_calls_foreman_execute(self) -> None:
        """Even with foreman_enabled=False, force_foreman=True uses foreman."""
        self._run_send_force("Test")
        self.mock_foreman.execute.assert_called_once()

    def test_force_foreman_sends_system_message(self) -> None:
        messages, _, completed = self._run_send_force("Test")
        self.assertTrue(completed)
        system_contents = [c for r, c in messages if r == "system"]
        self.assertIn("Planning...", system_contents)


# ======================================================================
# Cancellation
# ======================================================================


class ForemanChatHandlerCancellationTests(unittest.TestCase):
    """Cancellation in foreman mode."""

    def setUp(self) -> None:
        self.store = _make_chat_store()
        self.mock_foreman = MagicMock(spec=ForemanAgent)
        self.mock_foreman.execute.return_value = "Should not appear"

        self.handler = _make_handler(
            chat_store=self.store,
            client=MagicMock(spec=OllamaClient),
        )
        self.handler._foreman = self.mock_foreman
        self.session_id = self.handler.create_session(personality="general")
        self.handler.foreman_enabled = True

    def tearDown(self) -> None:
        self.store.close()

    def test_cancellation_before_send(self) -> None:
        token = CancellationToken()
        token.cancel()

        errors: list[str] = []
        completed = [False]

        def on_msg(r: str, c: str) -> None:
            pass

        def on_err(e: str) -> None:
            errors.append(e)

        def on_done() -> None:
            completed[0] = True

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

        self.assertIn("Operation cancelled", errors)
        self.assertFalse(completed[0])
        # foreman.execute should NOT be called (cancelled pre-flight)
        self.mock_foreman.execute.assert_not_called()

    def test_cancellation_stores_cancelled_message(self) -> None:
        token = CancellationToken()
        token.cancel()

        errors: list[str] = []

        def on_msg(r: str, c: str) -> None:
            pass

        def on_err(e: str) -> None:
            errors.append(e)

        def on_done() -> None:
            pass

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

        msgs = self.store.get_messages(self.session_id)
        roles = [m.role for m in msgs]
        self.assertIn("cancelled", roles)


# ======================================================================
# Error handling
# ======================================================================


class ForemanChatHandlerErrorTests(unittest.TestCase):
    """Error handling when ForemanAgent raises."""

    def setUp(self) -> None:
        self.store = _make_chat_store()
        self.mock_foreman = MagicMock(spec=ForemanAgent)
        self.mock_foreman.execute.side_effect = RuntimeError("Foreman failure")

        self.handler = _make_handler(
            chat_store=self.store,
            client=MagicMock(spec=OllamaClient),
        )
        self.handler._foreman = self.mock_foreman
        self.session_id = self.handler.create_session(personality="general")
        self.handler.foreman_enabled = True

    def tearDown(self) -> None:
        self.store.close()

    def test_foreman_error_reports_error(self) -> None:
        errors: list[str] = []

        def on_msg(r: str, c: str) -> None:
            pass

        def on_err(e: str) -> None:
            errors.append(e)

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

        self.assertTrue(len(errors) > 0)

    def test_foreman_error_stores_error_message(self) -> None:
        errors: list[str] = []

        def on_msg(r: str, c: str) -> None:
            pass

        def on_err(e: str) -> None:
            errors.append(e)

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

        msgs = self.store.get_messages(self.session_id)
        roles = [m.role for m in msgs]
        self.assertIn("error", roles)


# ======================================================================
# Thread safety
# ======================================================================


class ForemanChatHandlerThreadSafetyTests(unittest.TestCase):
    """Verify send_message runs in a daemon thread (both modes)."""

    def setUp(self) -> None:
        self.store = _make_chat_store()
        self.mock_foreman = MagicMock(spec=ForemanAgent)
        self.mock_foreman.execute.return_value = "Foreman response"

        self.mock_client = MagicMock(spec=OllamaClient)
        self.mock_client.ask.return_value = "Simple response"

        self.handler = _make_handler(
            chat_store=self.store,
            client=self.mock_client,
        )
        self.handler._foreman = self.mock_foreman
        self.session_id = self.handler.create_session()

    def tearDown(self) -> None:
        self.store.close()

    def test_foreman_mode_daemon_thread(self) -> None:
        """Foreman send_message uses a daemon thread."""
        self.handler.foreman_enabled = True
        main_thread = threading.current_thread()
        thread_ref = [None]

        original_execute = self.mock_foreman.execute

        def execute_hook(*args: object, **kwargs: object) -> str:
            thread_ref[0] = threading.current_thread()
            return original_execute(*args, **kwargs)

        self.mock_foreman.execute.side_effect = execute_hook

        token = CancellationToken()
        errors: list[str] = []
        completed = [False]

        def on_msg(r: str, c: str) -> None:
            pass

        def on_err(e: str) -> None:
            errors.append(e)

        def on_done() -> None:
            completed[0] = True

        self.handler.send_message(
            session_id=self.session_id,
            message="Test daemon",
            token=token,
            on_message=on_msg,
            on_error=on_err,
            on_complete=on_done,
        )

        deadline = time.time() + 5
        while (thread_ref[0] is None or not completed[0]) and time.time() < deadline:
            time.sleep(0.01)

        self.assertIsNotNone(thread_ref[0])
        self.assertTrue(thread_ref[0].daemon)
        self.assertNotEqual(thread_ref[0], main_thread)

    def test_simple_mode_daemon_thread(self) -> None:
        """Simple (non-foreman) send_message uses a daemon thread."""
        self.handler.foreman_enabled = False
        main_thread = threading.current_thread()
        thread_ref = [None]

        original_ask = self.mock_client.ask

        def ask_hook(*args: object, **kwargs: object) -> str:
            thread_ref[0] = threading.current_thread()
            return original_ask(*args, **kwargs)

        self.mock_client.ask.side_effect = ask_hook

        token = CancellationToken()
        errors: list[str] = []
        completed = [False]

        def on_msg(r: str, c: str) -> None:
            pass

        def on_err(e: str) -> None:
            errors.append(e)

        def on_done() -> None:
            completed[0] = True

        self.handler.send_message(
            session_id=self.session_id,
            message="Test daemon simple",
            token=token,
            on_message=on_msg,
            on_error=on_err,
            on_complete=on_done,
        )

        deadline = time.time() + 5
        while (thread_ref[0] is None or not completed[0]) and time.time() < deadline:
            time.sleep(0.01)

        self.assertIsNotNone(thread_ref[0])
        self.assertTrue(thread_ref[0].daemon)
        self.assertNotEqual(thread_ref[0], main_thread)


# ======================================================================
# Backward compat tests
# ======================================================================


class ForemanChatHandlerBackwardCompatTests(unittest.TestCase):
    """ForemanChatHandler is a drop-in replacement for AgentChatHandler."""

    def test_handler_has_same_public_methods(self) -> None:
        """All AgentChatHandler public methods exist on ForemanChatHandler."""
        from Agent.chat_handler import AgentChatHandler

        ach_methods = {
            m for m in dir(AgentChatHandler)
            if not m.startswith("_")
        }
        fch_methods = {
            m for m in dir(ForemanChatHandler)
            if not m.startswith("_")
        }
        # ForemanChatHandler has at least all of AgentChatHandler's methods
        for m in ach_methods:
            self.assertIn(m, fch_methods, f"Missing method: {m}")

    def test_foreman_handler_can_be_imported(self) -> None:
        from PhiConnect.foreman_handler import ForemanChatHandler
        self.assertTrue(callable(ForemanChatHandler))

    def test_agent_tab_imports_still_work(self) -> None:
        """PhiConnect.gui should still be importable (regression check)."""
        try:
            from PhiConnect.gui import PhiConnectApp
            self.assertTrue(callable(PhiConnectApp))
        except Exception as exc:
            self.fail(f"PhiConnect.gui import failed: {exc}")


# ======================================================================
# ForemanChatHandler with real OllamaClient (smoke test)
# ======================================================================


class ForemanChatHandlerSmokeTests(unittest.TestCase):
    """Lightweight smoke tests that don't require network."""

    def test_config_round_trip(self) -> None:
        """update_config + config property round-trip."""
        store = _make_chat_store()
        handler = _make_handler(chat_store=store)
        handler.update_config(
            parallel_by_default=True,
            max_sub_agents=5,
            max_turns_per_sub_agent=20,
        )
        self.assertTrue(handler.config.parallel_by_default)
        self.assertEqual(handler.config.max_sub_agents, 5)
        self.assertEqual(handler.config.max_turns_per_sub_agent, 20)
        store.close()

    def test_double_toggle(self) -> None:
        """Toggle foreman on and off without errors."""
        store = _make_chat_store()
        handler = _make_handler(chat_store=store)
        handler.foreman_enabled = True
        self.assertTrue(handler.foreman_enabled)
        handler.foreman_enabled = False
        self.assertFalse(handler.foreman_enabled)
        handler.foreman_enabled = True
        self.assertTrue(handler.foreman_enabled)
        store.close()

    def test_session_create_and_delete_repeated(self) -> None:
        """Create and delete sessions multiple times."""
        store = _make_chat_store()
        handler = _make_handler(chat_store=store)
        ids = []
        for i in range(5):
            sid = handler.create_session(personality="general")
            ids.append(sid)
        self.assertEqual(len(handler.list_sessions()), 5)
        for sid in ids:
            handler.delete_session(sid)
        self.assertEqual(handler.list_sessions(), [])
        store.close()

    def test_default_constructor_no_crash(self) -> None:
        """Default constructor with no optional args doesn't crash."""
        store = _make_chat_store()
        handler = ForemanChatHandler(chat_store=store)
        self.assertIsNotNone(handler)
        store.close()


if __name__ == "__main__":
    unittest.main()
