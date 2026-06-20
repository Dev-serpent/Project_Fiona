"""GUI-facing handler that wraps ForemanAgent with a toggle for orchestration.

Provides a drop-in replacement for AgentChatHandler that can optionally
delegate to ForemanAgent for multi-agent orchestration. When foreman is
disabled (the default), behaviour is identical to AgentChatHandler.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import replace
from typing import Any, Callable

from Agent.cancellation import CancellationToken, CancelledError
from Agent.chat_handler import AgentChatHandler
from Agent.chat_store import ChatStore
from Agent.ollama import OllamaClient, OllamaError
from Agent.orchestration import ForemanAgent, ForemanConfig
from Agent.personality import PersonalityRegistry

logger = logging.getLogger(__name__)


class ForemanChatHandler:
    """GUI-facing handler that wraps ForemanAgent for use in PhiConnect GUI.

    Provides a toggle to switch between simple chat (AgentChatHandler)
    and full orchestration (ForemanAgent).

    Usage::

        handler = ForemanChatHandler(chat_store=store)
        handler.foreman_enabled = True
        handler.send_message(
            session_id="...",
            message="What is the capital of France?",
            token=CancellationToken(),
            on_message=lambda role, content: print(role, content),
            on_error=lambda err: print("Error:", err),
            on_complete=lambda: print("Done"),
        )
    """

    def __init__(
        self,
        chat_store: ChatStore,
        client: OllamaClient | None = None,
        personality_registry: PersonalityRegistry | None = None,
        config: ForemanConfig | None = None,
    ) -> None:
        """Creates a ForemanAgent internally.

        Parameters
        ----------
        chat_store:
            Persistence backend for sessions and messages.
        client:
            Ollama client.  If ``None`` a default ``OllamaClient()``
            is created.
        personality_registry:
            Registry of available personalities.  If ``None`` the
            global singleton is used.
        config:
            Foreman orchestration configuration.  If ``None`` uses
            ``ForemanConfig()`` defaults.
        """
        self._chat_store = chat_store
        self._client = client if client is not None else OllamaClient()
        self._registry = (
            personality_registry
            if personality_registry is not None
            else PersonalityRegistry.get_instance()
        )
        self._config = config if config is not None else ForemanConfig()

        # Internal ForemanAgent for orchestration mode
        self._foreman = ForemanAgent(
            client=self._client,
            registry=self._registry,
            chat_store=chat_store,
            config=self._config,
        )

        # Internal AgentChatHandler for simple (non-foreman) mode.
        # We use it for session management and as a fallback when
        # foreman is disabled.
        self._simple_handler = AgentChatHandler(
            chat_store=chat_store,
            client=client,
            personality_registry=self._registry,
        )

        self._foreman_enabled = False
        self._session_personality: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Foreman toggle
    # ------------------------------------------------------------------

    @property
    def foreman_enabled(self) -> bool:
        """Whether Foreman orchestration is currently enabled."""
        return self._foreman_enabled

    @foreman_enabled.setter
    def foreman_enabled(self, value: bool) -> None:
        """Toggle orchestration on/off.

        When ``False`` (the default), ``send_message()`` delegates to
        :class:`AgentChatHandler` — identical to M3 behaviour.

        When ``True``, ``send_message()`` delegates to
        :class:`ForemanAgent` for multi-agent orchestration.
        """
        self._foreman_enabled = bool(value)

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    @property
    def config(self) -> ForemanConfig:
        """Current ForemanConfig (read-only access)."""
        return self._config

    def update_config(self, **kwargs: Any) -> None:
        """Update ForemanConfig fields (creates new frozen instance).

        Accepted kwargs:
            parallel_by_default, max_sub_agents, max_turns_per_sub_agent,
            max_plan_retries, context_max_tokens, default_personality.

        Only recognised field names are applied; unknown names are
        silently ignored.
        """
        allowed = {
            "parallel_by_default",
            "max_sub_agents",
            "max_turns_per_sub_agent",
            "max_plan_retries",
            "context_max_tokens",
            "default_personality",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        self._config = replace(self._config, **updates)
        # Recreate foreman agent to pick up new config
        self._foreman = ForemanAgent(
            client=self._client,
            registry=self._registry,
            chat_store=self._chat_store,
            config=self._config,
        )

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def create_session(self, personality: str = "general") -> str:
        """Create a new chat session.

        Delegates to :class:`AgentChatHandler` and tracks the
        session-to-personality mapping for use in foreman mode.

        Returns the session ID (UUID4 string).
        """
        session_id = self._simple_handler.create_session(personality=personality)
        self._session_personality[session_id] = personality
        return session_id

    def list_sessions(self) -> list[dict[str, Any]]:
        """Return all sessions, newest-active first.

        Delegates to :class:`AgentChatHandler`.

        Each dictionary has keys ``session_id``, ``personality``,
        ``message_count``, ``created_at``, ``last_active_at``.
        """
        return self._simple_handler.list_sessions()

    def delete_session(self, session_id: str) -> None:
        """Delete a session and all its messages.

        Delegates to :class:`AgentChatHandler`.
        """
        self._session_personality.pop(session_id, None)
        self._simple_handler.delete_session(session_id)

    # ------------------------------------------------------------------
    # Send message
    # ------------------------------------------------------------------

    def send_message(
        self,
        session_id: str,
        message: str,
        token: CancellationToken,
        *,
        force_foreman: bool = False,
        on_message: Callable[[str, str], None],
        on_error: Callable[[str], None],
        on_complete: Callable[[], None],
    ) -> None:
        """Send *message* in a **daemon thread**.

        If *foreman_enabled* or *force_foreman* is ``True`` the message
        is handled by :class:`ForemanAgent` (orchestration pipeline).
        Otherwise it is delegated to :class:`AgentChatHandler` (simple
        single-agent chat).

        All callbacks are invoked from the worker thread — the caller
        must marshal them onto the GUI thread (e.g. via
        ``widget.after()``).

        Parameters
        ----------
        session_id:
            Active session identifier.
        message:
            The user's chat message.
        token:
            Cancellation token checked throughout execution.
        force_foreman:
            If ``True``, use the ForemanAgent even when
            ``foreman_enabled`` is ``False``.
        on_message:
            Called with ``(role, content)`` for each message (user,
            agent, or system status).  The caller **must** marshal this
            onto the GUI thread.
        on_error:
            Called with an error description on cancellation or failure.
            The caller **must** marshal this onto the GUI thread.
        on_complete:
            Called when the round-trip finishes successfully.  The
            caller **must** marshal this onto the GUI thread.
        """
        if self._foreman_enabled or force_foreman:
            personality = self._session_personality.get(session_id, "general")
            thread = threading.Thread(
                target=self._send_foreman_thread,
                args=(
                    session_id,
                    message,
                    token,
                    personality,
                    on_message,
                    on_error,
                    on_complete,
                ),
                daemon=True,
            )
            thread.start()
        else:
            # Delegate to AgentChatHandler — identical to M3 behaviour
            self._simple_handler.send_message(
                session_id=session_id,
                message=message,
                token=token,
                on_message=on_message,
                on_error=on_error,
                on_complete=on_complete,
            )

    def _send_foreman_thread(
        self,
        session_id: str,
        message: str,
        token: CancellationToken,
        personality: str,
        on_message: Callable[[str, str], None],
        on_error: Callable[[str], None],
        on_complete: Callable[[], None],
    ) -> None:
        """Worker thread body for foreman-based ``send_message``."""
        try:
            # Step 1 — pre-flight cancellation check
            token.raise_if_cancelled()

            # Step 2 — persist user message
            self._chat_store.add_message(
                session_id,
                "user",
                message,
                personality=personality,
            )

            # Step 3 — notify UI of user message
            on_message("user", message)

            # Step 4 — status: planning
            on_message("system", "Planning...")

            # Step 5 — execute via ForemanAgent
            response = self._foreman.execute(
                goal=message,
                personality=personality,
                token=token,
            )

            # Step 6 — re-check cancellation before persisting
            token.raise_if_cancelled()

            # Step 7 — persist agent response
            self._chat_store.add_message(
                session_id,
                "agent",
                response,
                personality=personality,
            )

            # Step 8 — notify UI of agent response
            on_message("agent", response)

            # Step 9 — signal completion
            on_complete()

        except CancelledError:
            logger.info("Foreman chat cancelled for session %s", session_id)
            try:
                self._chat_store.add_message(
                    session_id,
                    "cancelled",
                    "Operation cancelled",
                    personality=personality,
                )
            except Exception:
                logger.exception("Failed to store cancellation message")
            on_error("Operation cancelled")

        except OllamaError as exc:
            logger.warning("Ollama error in foreman chat: %s", exc)
            try:
                self._chat_store.add_message(
                    session_id,
                    "error",
                    str(exc),
                    personality=personality,
                )
            except Exception:
                logger.exception("Failed to store error message")
            on_error(str(exc))

        except Exception as exc:
            logger.exception("Unexpected error in foreman chat")
            try:
                self._chat_store.add_message(
                    session_id,
                    "error",
                    f"Unexpected error: {exc}",
                    personality=personality,
                )
            except Exception:
                logger.exception("Failed to store unexpected error message")
            on_error(f"Unexpected error: {exc}")
