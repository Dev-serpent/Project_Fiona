"""SQLite-backed chat persistence with thread safety.

Provides ChatStore for durable, thread-safe chat history management
using WAL-mode SQLite. All public methods are safe to call from
multiple threads; all database access is serialized with a
``threading.Lock``.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def estimate_tokens(text: str) -> int:
    """Rough estimate: 1 token ≈ 4 characters for English text.

    Returns ``len(text) // 4 + 1``.
    """
    return len(text) // 4 + 1


class ChatStoreError(RuntimeError):
    """Wraps ``sqlite3.Error`` and other persistence errors."""


@dataclass(frozen=True)
class ChatMessage:
    """Immutable representation of a single chat message."""

    id: int
    session_id: str
    role: str  # 'user' | 'agent' | 'system' | 'error' | 'cancelled'
    content: str
    personality: str
    timestamp: float
    token_count: int | None = None
    model: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        d: dict[str, Any] = {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "personality": self.personality,
            "timestamp": self.timestamp,
        }
        if self.token_count is not None:
            d["token_count"] = self.token_count
        if self.model is not None:
            d["model"] = self.model
        return d


_SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS sessions (
    session_id     TEXT PRIMARY KEY,
    personality    TEXT NOT NULL DEFAULT 'general',
    created_at     REAL NOT NULL,
    last_active_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    role         TEXT NOT NULL CHECK (role IN ('user','agent','system','error','cancelled')),
    content      TEXT NOT NULL,
    personality  TEXT NOT NULL DEFAULT 'general',
    model        TEXT,
    token_count  INTEGER,
    timestamp    REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(session_id, role);
CREATE INDEX IF NOT EXISTS idx_sessions_last_active ON sessions(last_active_at DESC);

PRAGMA wal_autocheckpoint = 1000;
"""


class ChatStore:
    """Thread-safe SQLite-backed chat persistence with WAL mode.

    All public methods are safe to call from multiple threads.
    Uses ``threading.Lock`` to serialise all database access.

    Instances can be used as context managers::

        with ChatStore("chats.db") as store:
            sid = store.create_session()
            store.add_message(sid, "user", "Hello!")
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __init__(self, db_path: str | Path) -> None:
        """Open or create an SQLite database at *db_path*.

        Enables WAL mode and creates the schema if the database is new.
        Raises :class:`ChatStoreError` on failure.
        """
        self._db_path = str(db_path)
        self._lock = threading.Lock()

        try:
            self._conn = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            self._init_db()
        except sqlite3.Error as exc:
            raise ChatStoreError(
                f"Failed to open chat store at {db_path}: {exc}"
            ) from exc

    def _init_db(self) -> None:
        """Execute schema DDL inside the write lock."""
        with self._lock:
            try:
                self._conn.executescript(_SCHEMA_SQL)
                self._conn.commit()
            except sqlite3.Error as exc:
                self._conn.rollback()
                raise ChatStoreError(f"Schema initialisation failed: {exc}") from exc

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        try:
            self._conn.close()
        except sqlite3.Error as exc:
            raise ChatStoreError(f"Error closing chat store: {exc}") from exc

    def vacuum(self) -> None:
        """Reclaim unused space via ``VACUUM``.

        This is a write operation and will block other writers.
        """
        with self._lock:
            try:
                self._conn.execute("VACUUM")
                self._conn.commit()
            except sqlite3.Error as exc:
                self._conn.rollback()
                raise ChatStoreError(f"Vacuum failed: {exc}") from exc

    def __enter__(self) -> ChatStore:
        return self

    def __exit__(self, *exc_args: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def create_session(self, personality: str = "general") -> str:
        """Create a new chat session.

        Returns a UUID4 string that identifies the session.
        """
        session_id = str(uuid.uuid4())
        now = time.time()
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO sessions (session_id, personality, created_at, "
                    "last_active_at) VALUES (?, ?, ?, ?)",
                    (session_id, personality, now, now),
                )
                self._conn.commit()
            except sqlite3.Error as exc:
                self._conn.rollback()
                raise ChatStoreError(
                    f"Failed to create session: {exc}"
                ) from exc
        return session_id

    def delete_session(self, session_id: str) -> None:
        """Delete a session and all its messages (ON DELETE CASCADE)."""
        with self._lock:
            try:
                self._conn.execute(
                    "DELETE FROM sessions WHERE session_id = ?",
                    (session_id,),
                )
                self._conn.commit()
            except sqlite3.Error as exc:
                self._conn.rollback()
                raise ChatStoreError(
                    f"Failed to delete session {session_id}: {exc}"
                ) from exc

    def list_sessions(
        self, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """List sessions ordered by ``last_active_at DESC``.

        Each dictionary contains: ``session_id``, ``personality``,
        ``message_count``, ``created_at``, ``last_active_at``.
        """
        with self._lock:
            try:
                rows = self._conn.execute(
                    """
                    SELECT s.session_id,
                           s.personality,
                           COUNT(m.id) AS message_count,
                           s.created_at,
                           s.last_active_at
                    FROM sessions s
                    LEFT JOIN messages m ON m.session_id = s.session_id
                    GROUP BY s.session_id
                    ORDER BY s.last_active_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                ).fetchall()
            except sqlite3.Error as exc:
                raise ChatStoreError(
                    f"Failed to list sessions: {exc}"
                ) from exc

        return [
            {
                "session_id": row["session_id"],
                "personality": row["personality"],
                "message_count": row["message_count"],
                "created_at": row["created_at"],
                "last_active_at": row["last_active_at"],
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        personality: str = "general",
        token_count: int | None = None,
        model: str | None = None,
    ) -> int:
        """Append a message to a session.

        Auto-creates the session if it does not exist.
        Returns the new ``message.id``.
        """
        now = time.time()
        with self._lock:
            try:
                # Ensure session exists (auto-create)
                existing = self._conn.execute(
                    "SELECT 1 FROM sessions WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                if existing is None:
                    self._conn.execute(
                        "INSERT OR IGNORE INTO sessions "
                        "(session_id, personality, created_at, last_active_at) "
                        "VALUES (?, ?, ?, ?)",
                        (session_id, personality, now, now),
                    )

                # Update last_active_at
                self._conn.execute(
                    "UPDATE sessions SET last_active_at = ? WHERE session_id = ?",
                    (now, session_id),
                )

                cursor = self._conn.execute(
                    "INSERT INTO messages "
                    "(session_id, role, content, personality, model, "
                    " token_count, timestamp) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (session_id, role, content, personality, model, token_count, now),
                )
                self._conn.commit()
                return cursor.lastrowid  # type: ignore[return-value]
            except sqlite3.IntegrityError as exc:
                self._conn.rollback()
                raise ChatStoreError(
                    f"Invalid message data (check role value): {exc}"
                ) from exc
            except sqlite3.Error as exc:
                self._conn.rollback()
                raise ChatStoreError(f"Failed to add message: {exc}") from exc

    def get_messages(
        self, session_id: str, limit: int = 100, offset: int = 0
    ) -> list[ChatMessage]:
        """Get messages for a session, oldest-first."""
        with self._lock:
            try:
                rows = self._conn.execute(
                    "SELECT * FROM messages WHERE session_id = ? "
                    "ORDER BY id ASC LIMIT ? OFFSET ?",
                    (session_id, limit, offset),
                ).fetchall()
            except sqlite3.Error as exc:
                raise ChatStoreError(
                    f"Failed to get messages for {session_id}: {exc}"
                ) from exc
        return [self._row_to_message(r) for r in rows]

    def count_messages(self, session_id: str) -> int:
        """Return the number of messages in a session."""
        with self._lock:
            try:
                row = self._conn.execute(
                    "SELECT COUNT(*) AS cnt FROM messages WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                return row["cnt"] if row else 0
            except sqlite3.Error as exc:
                raise ChatStoreError(
                    f"Failed to count messages for {session_id}: {exc}"
                ) from exc

    def get_context_window(
        self, session_id: str, max_tokens: int = 2048
    ) -> list[ChatMessage]:
        """Build a token-aware context window.

        Walks messages newest-first, accumulating ``token_count``.
        Uses :func:`estimate_tokens` when ``token_count`` is NULL.
        Stops when adding the next message would exceed *max_tokens*.
        At least the most recent message is always included.
        Returns messages oldest-first within the token budget.
        """
        with self._lock:
            try:
                rows = self._conn.execute(
                    "SELECT * FROM messages WHERE session_id = ? "
                    "ORDER BY id DESC",
                    (session_id,),
                ).fetchall()
            except sqlite3.Error as exc:
                raise ChatStoreError(
                    f"Failed to build context window for {session_id}: {exc}"
                ) from exc

        window: list[ChatMessage] = []
        total_tokens = 0

        for row in rows:
            msg = self._row_to_message(row)
            tokens = (
                msg.token_count
                if msg.token_count is not None
                else estimate_tokens(msg.content)
            )
            # Always include at least the most recent message.
            if total_tokens + tokens > max_tokens and window:
                break
            total_tokens += tokens
            window.append(msg)

        window.reverse()
        return window

    # ------------------------------------------------------------------
    # Search & maintenance
    # ------------------------------------------------------------------

    def search_messages(
        self,
        query: str,
        session_id: str | None = None,
        limit: int = 50,
    ) -> list[ChatMessage]:
        """Search message content using SQL ``LIKE``.

        If *session_id* is ``None``, searches across all sessions.
        The *query* is wrapped in ``'%...%'`` for substring matching.
        """
        like_pattern = f"%{query}%"
        with self._lock:
            try:
                if session_id is not None:
                    rows = self._conn.execute(
                        "SELECT * FROM messages WHERE session_id = ? "
                        "AND content LIKE ? ORDER BY id DESC LIMIT ?",
                        (session_id, like_pattern, limit),
                    ).fetchall()
                else:
                    rows = self._conn.execute(
                        "SELECT * FROM messages WHERE content LIKE ? "
                        "ORDER BY id DESC LIMIT ?",
                        (like_pattern, limit),
                    ).fetchall()
            except sqlite3.Error as exc:
                raise ChatStoreError(
                    f"Failed to search messages: {exc}"
                ) from exc

        return [self._row_to_message(r) for r in rows]

    def prune_sessions(self, older_than_days: int = 30) -> int:
        """Delete sessions whose ``last_active_at`` is older than N days.

        Returns the number of sessions deleted.
        """
        cutoff = time.time() - older_than_days * 86400
        with self._lock:
            try:
                cursor = self._conn.execute(
                    "DELETE FROM sessions WHERE last_active_at < ?",
                    (cutoff,),
                )
                self._conn.commit()
                return cursor.rowcount  # type: ignore[return-value]
            except sqlite3.Error as exc:
                self._conn.rollback()
                raise ChatStoreError(f"Failed to prune sessions: {exc}") from exc

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def import_jsonl(self, jsonl_path: str | Path) -> int:
        """Import messages from a JSONL file into the store.

        JSONL format: one JSON object per line with keys:
        ``session_id``, ``role``, ``content``, ``personality``,
        ``timestamp``, ``token_count``, ``model``.

        Sessions are created on demand.  Returns the number of messages
        imported.
        """
        count = 0
        with self._lock:
            try:
                with open(jsonl_path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        stripped = line.strip()
                        if not stripped:
                            continue
                        data = json.loads(stripped)
                        session_id: str = data["session_id"]
                        role: str = data["role"]
                        content: str = data["content"]
                        personality: str = data.get("personality", "general")
                        timestamp: float = data.get("timestamp", time.time())
                        token_count: int | None = data.get("token_count")
                        model: str | None = data.get("model")

                        # Ensure session exists
                        existing = self._conn.execute(
                            "SELECT 1 FROM sessions WHERE session_id = ?",
                            (session_id,),
                        ).fetchone()
                        if existing is None:
                            self._conn.execute(
                                "INSERT INTO sessions "
                                "(session_id, personality, created_at, last_active_at) "
                                "VALUES (?, ?, ?, ?)",
                                (session_id, personality, timestamp, timestamp),
                            )

                        self._conn.execute(
                            "INSERT INTO messages "
                            "(session_id, role, content, personality, model, "
                            " token_count, timestamp) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (
                                session_id,
                                role,
                                content,
                                personality,
                                model,
                                token_count,
                                timestamp,
                            ),
                        )
                        count += 1
                self._conn.commit()
            except sqlite3.Error:
                self._conn.rollback()
                raise
        return count

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> ChatMessage:
        """Convert an ``sqlite3.Row`` to a :class:`ChatMessage`."""
        return ChatMessage(
            id=row["id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            personality=row["personality"],
            timestamp=row["timestamp"],
            token_count=row["token_count"],
            model=row["model"],
        )
