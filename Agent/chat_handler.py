"""Bridge between GUI and LLM for single-agent chat sessions.

All LLM calls run in daemon threads. UI updates are delegated to
callbacks so the caller can schedule them on the correct thread
(e.g. via ``widget.after()`` in Tkinter).
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from Agent.cancellation import CancelledError, CancellationToken
from Agent.chat_store import ChatMessage, ChatStore
from Agent.ollama import OllamaClient, OllamaError
from Agent.personality import Personality, PersonalityRegistry

logger = logging.getLogger(__name__)


class AgentChatHandler:
    """Bridge between GUI and LLM for single-agent chat sessions.

    All LLM calls run in **daemon threads** so they never block the
    caller.  The caller provides callbacks that are invoked from the
    worker thread — it is the caller's responsibility to marshal those
    callbacks onto the GUI thread (e.g. ``widget.after(0, cb)``).

    Session management (create / list / delete) is delegated to the
    underlying :class:`ChatStore`.
    """

    def __init__(
        self,
        chat_store: ChatStore,
        client: OllamaClient | None = None,
        personality_registry: PersonalityRegistry | None = None,
    ) -> None:
        """Initialise the handler.

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
        """
        self._chat_store = chat_store
        self._client = client if client is not None else OllamaClient()
        self._registry = (
            personality_registry
            if personality_registry is not None
            else PersonalityRegistry.get_instance()
        )
        self._session_personality: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def create_session(self, personality: str = "general") -> str:
        """Create a new chat session.

        The session is created via :meth:`ChatStore.create_session`
        and the handler remembers the associated *personality* for
        subsequent :meth:`send_message` calls.

        Returns the session ID (UUID4 string).
        """
        session_id = self._chat_store.create_session(personality=personality)
        self._session_personality[session_id] = personality
        return session_id

    def list_sessions(self) -> list[dict[str, Any]]:
        """Return all sessions, newest-active first.

        Each dictionary has keys ``session_id``, ``personality``,
        ``message_count``, ``created_at``, ``last_active_at``.
        """
        return self._chat_store.list_sessions()

    def delete_session(self, session_id: str) -> None:
        """Delete a session and all its messages."""
        self._session_personality.pop(session_id, None)
        self._chat_store.delete_session(session_id)

    # ------------------------------------------------------------------
    # Send message (daemon thread)
    # ------------------------------------------------------------------

    def send_message(
        self,
        session_id: str,
        message: str,
        token: CancellationToken,
        on_message: Callable[[str, str], None],
        on_error: Callable[[str], None],
        on_complete: Callable[[], None],
        system_prompt_override: str | None = None,
    ) -> None:
        """Send *message* in a **daemon thread**.

        The call flow inside the worker thread:

         1. ``token.raise_if_cancelled()``
         2. Store ``"user"`` message in :class:`ChatStore`
         3. ``on_message("user", message)``
         4. Build context window via :meth:`ChatStore.get_context_window`
         5. Look up the session's :class:`Personality`
         6. Call :meth:`OllamaClient.ask` with the effective system prompt
            (*system_prompt_override* if given, otherwise the personality's
            ``system_prompt``)
         7. Store ``"agent"`` response in :class:`ChatStore`
         8. ``on_message("agent", response)``
         9. ``on_complete()``

        If a :class:`CancelledError` is caught the message ``"Operation
        cancelled"`` is stored with role ``"cancelled"`` and
        ``on_error("Operation cancelled")`` is called.

        If an :class:`OllamaError` is caught the error text is stored
        with role ``"error"`` and ``on_error(str(exc))`` is called.

        Parameters
        ----------
        session_id:
            Active session identifier.
        message:
            The user's chat message.
        token:
            Cancellation token checked before and after the LLM call.
        on_message:
            Called from the worker thread with ``(role, content)`` for
            each stored message (user & agent).  The caller **must**
            marshal this onto the GUI thread.
        on_error:
            Called from the worker thread with an error description on
            cancellation or LLM failure.  The caller **must** marshal
            this onto the GUI thread.
        on_complete:
            Called from the worker thread when the round-trip finishes
            successfully.  The caller **must** marshal this onto the
            GUI thread.
        system_prompt_override:
            If provided, this string is used as the system prompt
            instead of the personality's ``system_prompt``.  Used by
            :class:`ForemanChatHandler` when the :class:`QueryDetector`
            classifies a message as a conversational query — avoids
            wasting tokens on ReAct-style planning.
        """
        personality = self._session_personality.get(session_id, "general")

        thread = threading.Thread(
            target=self._send_message_thread,
            args=(
                session_id,
                message,
                token,
                on_message,
                on_error,
                on_complete,
                personality,
                system_prompt_override,
            ),
            daemon=True,
        )
        thread.start()

    def _send_message_thread(
        self,
        session_id: str,
        message: str,
        token: CancellationToken,
        on_message: Callable[[str, str], None],
        on_error: Callable[[str], None],
        on_complete: Callable[[], None],
        personality: str,
        system_prompt_override: str | None = None,
    ) -> None:
        """Worker thread body for :meth:`send_message`."""
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

            # Step 3 — notify UI
            on_message("user", message)

            # Step 4 — build token-aware context window
            context_messages = self._chat_store.get_context_window(session_id)

            # Step 5 — get the active personality
            p = self._registry.get(personality)

            # Build prompt from context
            full_prompt = self._format_context(context_messages)

            # Step 6 — call LLM.
            # Use system_prompt_override if provided (e.g. for conversational
            # queries detected by QueryDetector), otherwise use the personality's
            # standard ReAct-style system_prompt.
            system = system_prompt_override if system_prompt_override is not None else p.system_prompt
            response = self._client.ask(
                prompt=full_prompt,
                system_prompt=system,
            )

            # Re-check cancellation before persisting the response
            token.raise_if_cancelled()

            # Step 7 — persist agent response
            self._chat_store.add_message(
                session_id,
                "agent",
                response,
                personality=personality,
            )

            # Step 8 — notify UI
            on_message("agent", response)

            # Step 9 — signal completion
            on_complete()

        except CancelledError:
            logger.info("Agent chat cancelled for session %s", session_id)
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
            logger.warning("Ollama error in agent chat: %s", exc)
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
            logger.exception("Unexpected error in agent chat handler")
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_context(messages: list[ChatMessage]) -> str:
        """Format a list of chat messages into a single conversation prompt.

        Each message is prefixed with ``User:`` or ``Assistant:``
        depending on its role.  Messages are separated by blank lines.
        """
        parts: list[str] = []
        for msg in messages:
            if msg.role == "user":
                label = "User"
            elif msg.role == "agent":
                label = "Assistant"
            else:
                label = msg.role.capitalize()
            parts.append(f"{label}: {msg.content}")
        return "\n\n".join(parts)
