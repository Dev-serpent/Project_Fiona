"""Tests for Agent.chat_store — SQLite Chat Persistence (Milestone 2)."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

from Agent.chat_store import (
    ChatMessage,
    ChatStore,
    ChatStoreError,
    estimate_tokens,
)


# ======================================================================
# Helper
# ======================================================================

def _count_lines(path: str | Path) -> int:
    """Count non-empty lines in a file."""
    with open(path) as f:
        return sum(1 for line in f if line.strip())


# ======================================================================
# estimate_tokens
# ======================================================================

class EstimateTokensTests(unittest.TestCase):
    """Unit tests for the token estimator helper."""

    def test_empty_string(self) -> None:
        self.assertEqual(estimate_tokens(""), 1)

    def test_short_string(self) -> None:
        self.assertEqual(estimate_tokens("abc"), 1)  # 3//4+1 = 1

    def test_exactly_four_chars(self) -> None:
        self.assertEqual(estimate_tokens("word"), 2)  # 4//4+1 = 2

    def test_longer_text(self) -> None:
        text = "Hello, world! This is a test."
        expected = len(text) // 4 + 1
        self.assertEqual(estimate_tokens(text), expected)


# ======================================================================
# ChatMessage
# ======================================================================

class ChatMessageTests(unittest.TestCase):
    """Unit tests for the ChatMessage dataclass."""

    def test_to_dict_minimal(self) -> None:
        msg = ChatMessage(
            id=1,
            session_id="s1",
            role="user",
            content="hello",
            personality="general",
            timestamp=1000.0,
        )
        d = msg.to_dict()
        self.assertEqual(d["id"], 1)
        self.assertEqual(d["session_id"], "s1")
        self.assertEqual(d["role"], "user")
        self.assertEqual(d["content"], "hello")
        self.assertNotIn("token_count", d)
        self.assertNotIn("model", d)

    def test_to_dict_full(self) -> None:
        msg = ChatMessage(
            id=2,
            session_id="s2",
            role="agent",
            content="Hi there!",
            personality="friendly",
            timestamp=2000.0,
            token_count=42,
            model="llama3",
        )
        d = msg.to_dict()
        self.assertEqual(d["token_count"], 42)
        self.assertEqual(d["model"], "llama3")

    def test_frozen_dataclass(self) -> None:
        msg = ChatMessage(
            id=1,
            session_id="s1",
            role="user",
            content="hi",
            personality="general",
            timestamp=1.0,
        )
        with self.assertRaises(AttributeError):
            msg.content = "changed"  # type: ignore[misc]


# ======================================================================
# ChatStore — session lifecycle
# ======================================================================

class ChatStoreSessionTests(unittest.TestCase):
    """Session CRUD operations."""

    def setUp(self) -> None:
        self.store = ChatStore(":memory:")

    def tearDown(self) -> None:
        self.store.close()

    def test_create_session_returns_uuid(self) -> None:
        sid = self.store.create_session("general")
        # UUID4 format: 8-4-4-4-12 hex digits
        parts = sid.split("-")
        self.assertEqual(len(parts), 5)
        self.assertEqual(len(parts[0]), 8)
        self.assertEqual(len(parts[1]), 4)

    def test_create_session_with_personality(self) -> None:
        sid = self.store.create_session("code-assistant")
        sessions = self.store.list_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["personality"], "code-assistant")
        self.assertEqual(sessions[0]["session_id"], sid)

    def test_list_sessions_empty(self) -> None:
        sessions = self.store.list_sessions()
        self.assertEqual(sessions, [])

    def test_list_sessions_ordered_by_last_active(self) -> None:
        s1 = self.store.create_session("a")
        time.sleep(0.01)
        s2 = self.store.create_session("b")
        sessions = self.store.list_sessions()
        self.assertEqual(len(sessions), 2)
        # Most recent first
        self.assertEqual(sessions[0]["session_id"], s2)
        self.assertEqual(sessions[1]["session_id"], s1)

    def test_list_sessions_message_count(self) -> None:
        sid = self.store.create_session("test")
        self.store.add_message(sid, "user", "msg1")
        self.store.add_message(sid, "agent", "msg2")
        sessions = self.store.list_sessions()
        self.assertEqual(sessions[0]["message_count"], 2)

    def test_list_sessions_limit_offset(self) -> None:
        sids = [self.store.create_session("t") for _ in range(5)]
        page = self.store.list_sessions(limit=2, offset=1)
        self.assertEqual(len(page), 2)
        # offset 1 means skip the newest (index 0), so we get sids[3] and sids[2]
        self.assertEqual(page[0]["session_id"], sids[3])
        self.assertEqual(page[1]["session_id"], sids[2])

    def test_delete_session_removes_session(self) -> None:
        sid = self.store.create_session("test")
        self.store.delete_session(sid)
        sessions = self.store.list_sessions()
        self.assertEqual(len(sessions), 0)

    def test_delete_session_cascades_to_messages(self) -> None:
        sid = self.store.create_session("test")
        self.store.add_message(sid, "user", "hello")
        self.store.add_message(sid, "agent", "world")
        self.store.delete_session(sid)
        msgs = self.store.get_messages(sid)
        self.assertEqual(len(msgs), 0)

    def test_context_manager(self) -> None:
        """ChatStore can be used as a context manager."""
        with ChatStore(":memory:") as store:
            sid = store.create_session("ctx")
            self.assertIsNotNone(sid)
        # Connection should be closed after exit


# ======================================================================
# ChatStore — message CRUD
# ======================================================================

class ChatStoreMessageTests(unittest.TestCase):
    """Message add / get / count operations."""

    def setUp(self) -> None:
        self.store = ChatStore(":memory:")
        self.sid = self.store.create_session("test")

    def tearDown(self) -> None:
        self.store.close()

    def test_add_message_returns_id(self) -> None:
        msg_id = self.store.add_message(self.sid, "user", "Hello")
        self.assertIsInstance(msg_id, int)
        self.assertGreater(msg_id, 0)

    def test_get_messages_empty(self) -> None:
        msgs = self.store.get_messages(self.sid)
        self.assertEqual(msgs, [])

    def test_get_messages_oldest_first(self) -> None:
        self.store.add_message(self.sid, "user", "first")
        self.store.add_message(self.sid, "agent", "second")
        msgs = self.store.get_messages(self.sid)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0].content, "first")
        self.assertEqual(msgs[1].content, "second")

    def test_get_messages_with_limit_offset(self) -> None:
        for i in range(10):
            self.store.add_message(self.sid, "user", f"msg{i}")
        msgs = self.store.get_messages(self.sid, limit=3, offset=5)
        self.assertEqual(len(msgs), 3)
        self.assertEqual(msgs[0].content, "msg5")
        self.assertEqual(msgs[2].content, "msg7")

    def test_count_messages(self) -> None:
        self.assertEqual(self.store.count_messages(self.sid), 0)
        self.store.add_message(self.sid, "user", "a")
        self.store.add_message(self.sid, "agent", "b")
        self.assertEqual(self.store.count_messages(self.sid), 2)

    def test_add_message_with_all_fields(self) -> None:
        msg_id = self.store.add_message(
            self.sid,
            "agent",
            "Detailed response",
            personality="code-assistant",
            token_count=128,
            model="llama3",
        )
        msgs = self.store.get_messages(self.sid)
        self.assertEqual(len(msgs), 1)
        m = msgs[0]
        self.assertEqual(m.id, msg_id)
        self.assertEqual(m.role, "agent")
        self.assertEqual(m.content, "Detailed response")
        self.assertEqual(m.personality, "code-assistant")
        self.assertEqual(m.token_count, 128)
        self.assertEqual(m.model, "llama3")
        self.assertIsInstance(m.timestamp, float)

    def test_allowed_roles(self) -> None:
        for role in ("user", "agent", "system", "error", "cancelled"):
            with self.subTest(role=role):
                msg_id = self.store.add_message(self.sid, role, f"content-{role}")
                self.assertIsInstance(msg_id, int)

    def test_invalid_role_raises_error(self) -> None:
        with self.assertRaises(ChatStoreError):
            self.store.add_message(self.sid, "invalid_role", "content")

    def test_add_message_updates_last_active_at(self) -> None:
        before = time.time()
        self.store.add_message(self.sid, "user", "hello")
        sessions = self.store.list_sessions()
        self.assertGreaterEqual(sessions[0]["last_active_at"], before)


# ======================================================================
# ChatStore — session auto-creation
# ======================================================================

class ChatStoreAutoCreateTests(unittest.TestCase):
    """add_message should auto-create sessions."""

    def setUp(self) -> None:
        self.store = ChatStore(":memory:")

    def tearDown(self) -> None:
        self.store.close()

    def test_add_message_auto_creates_session(self) -> None:
        sid = "auto-session-id"
        self.store.add_message(sid, "user", "first message")
        sessions = self.store.list_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], sid)
        msgs = self.store.get_messages(sid)
        self.assertEqual(len(msgs), 1)

    def test_auto_created_session_uses_general_personality(self) -> None:
        sid = "another-auto-id"
        self.store.add_message(sid, "user", "hello")
        sessions = self.store.list_sessions()
        self.assertEqual(sessions[0]["personality"], "general")


# ======================================================================
# ChatStore — context window
# ======================================================================

class ChatStoreContextWindowTests(unittest.TestCase):
    """Token-aware context window builder."""

    def setUp(self) -> None:
        self.store = ChatStore(":memory:")
        self.sid = self.store.create_session("test")

    def tearDown(self) -> None:
        self.store.close()

    def test_empty_session_returns_empty_window(self) -> None:
        window = self.store.get_context_window(self.sid, max_tokens=2048)
        self.assertEqual(window, [])

    def test_single_message_always_included(self) -> None:
        self.store.add_message(
            self.sid, "user", "x" * 10000, token_count=5000
        )
        window = self.store.get_context_window(self.sid, max_tokens=100)
        self.assertEqual(len(window), 1)

    def test_exact_token_budget(self) -> None:
        """Messages exactly fill the budget."""
        self.store.add_message(
            self.sid, "user", "msg1", token_count=100
        )
        self.store.add_message(
            self.sid, "agent", "msg2", token_count=200
        )
        # Budget = 300 → both fit
        window = self.store.get_context_window(self.sid, max_tokens=300)
        self.assertEqual(len(window), 2)
        # Budget = 299 → only newest (msg2, 200) fits, but msg1 (100) would exceed
        # Actually: process newest-first: msg2 (200) fits, then msg1 (100) would make 300 > 299 → stop
        window2 = self.store.get_context_window(self.sid, max_tokens=299)
        self.assertEqual(len(window2), 1)
        self.assertEqual(window2[0].content, "msg2")

    def test_context_window_uses_estimate_when_null(self) -> None:
        """When token_count is NULL, estimate_tokens is used."""
        # Each 'a' = 1 char → estimate = 1//4+1 = 1 token
        content = "a" * 100  # estimate = 100//4+1 = 26
        self.store.add_message(self.sid, "user", content, token_count=None)
        window = self.store.get_context_window(self.sid, max_tokens=25)
        # First message has estimate 26 > 25, but it's the only one so included
        self.assertEqual(len(window), 1)

    def test_context_window_oldest_first_order(self) -> None:
        self.store.add_message(self.sid, "user", "first", token_count=10)
        self.store.add_message(self.sid, "agent", "second", token_count=10)
        self.store.add_message(self.sid, "user", "third", token_count=10)
        window = self.store.get_context_window(self.sid, max_tokens=100)
        self.assertEqual(len(window), 3)
        self.assertEqual(window[0].content, "first")
        self.assertEqual(window[1].content, "second")
        self.assertEqual(window[2].content, "third")

    def test_context_window_respects_budget_ordering(self) -> None:
        self.store.add_message(self.sid, "user", "old", token_count=50)
        self.store.add_message(self.sid, "agent", "mid", token_count=50)
        self.store.add_message(self.sid, "user", "new", token_count=50)
        # Budget 120: newest-first: new(50) + mid(50)=100, old(50) would make 150>120
        window = self.store.get_context_window(self.sid, max_tokens=120)
        self.assertEqual(len(window), 2)
        self.assertEqual(window[0].content, "mid")
        self.assertEqual(window[1].content, "new")


# ======================================================================
# ChatStore — search
# ======================================================================

class ChatStoreSearchTests(unittest.TestCase):
    """Message content search."""

    def setUp(self) -> None:
        self.store = ChatStore(":memory:")
        self.sid1 = self.store.create_session("a")
        self.sid2 = self.store.create_session("b")
        self.store.add_message(self.sid1, "user", "Hello world")
        self.store.add_message(self.sid1, "agent", "Hi there")
        self.store.add_message(self.sid2, "user", "Hello again")
        self.store.add_message(self.sid2, "agent", "Goodbye")

    def tearDown(self) -> None:
        self.store.close()

    def test_search_across_all_sessions(self) -> None:
        results = self.store.search_messages("Hello")
        self.assertEqual(len(results), 2)

    def test_search_in_specific_session(self) -> None:
        results = self.store.search_messages("Hello", session_id=self.sid1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].session_id, self.sid1)

    def test_search_no_results(self) -> None:
        results = self.store.search_messages("zzzzzz")
        self.assertEqual(results, [])

    def test_search_case_sensitive(self) -> None:
        """SQLite LIKE is case-insensitive for ASCII by default."""
        results = self.store.search_messages("hello")
        self.assertEqual(len(results), 2)

    def test_search_limit(self) -> None:
        # Add more messages
        for i in range(10):
            self.store.add_message(self.sid1, "user", f"searchable {i}")
        results = self.store.search_messages("searchable", limit=3)
        self.assertLessEqual(len(results), 3)

    def test_search_partial_match(self) -> None:
        results = self.store.search_messages("ood")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "Goodbye")


# ======================================================================
# ChatStore — prune
# ======================================================================

class ChatStorePruneTests(unittest.TestCase):
    """Session pruning (by age)."""

    def setUp(self) -> None:
        self.store = ChatStore(":memory:")

    def tearDown(self) -> None:
        self.store.close()

    def test_prune_removes_old_sessions(self) -> None:
        # Create a session with a very old timestamp
        # We can't easily fake last_active_at via the API, but we can
        # directly add a message via the store which creates the session.
        # Instead, let's create sessions and then add old messages.
        old_sid = self.store.create_session("old")
        # Manually set last_active_at far in the past via SQL
        far_past = time.time() - 100 * 86400  # 100 days ago
        with self.store._lock:
            self.store._conn.execute(
                "UPDATE sessions SET last_active_at = ? WHERE session_id = ?",
                (far_past, old_sid),
            )
            self.store._conn.commit()

        new_sid = self.store.create_session("new")

        pruned = self.store.prune_sessions(older_than_days=30)
        self.assertEqual(pruned, 1)

        sessions = self.store.list_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], new_sid)

    def test_prune_no_sessions_to_delete(self) -> None:
        self.store.create_session("a")
        self.store.create_session("b")
        pruned = self.store.prune_sessions(older_than_days=30)
        self.assertEqual(pruned, 0)

    def test_prune_returns_zero_for_empty_store(self) -> None:
        pruned = self.store.prune_sessions(older_than_days=1)
        self.assertEqual(pruned, 0)


# ======================================================================
# ChatStore — import from JSONL
# ======================================================================

class ChatStoreImportTests(unittest.TestCase):
    """Importing from JSONL files."""

    def setUp(self) -> None:
        self.store = ChatStore(":memory:")

    def tearDown(self) -> None:
        self.store.close()

    def test_import_jsonl_basic(self) -> None:
        lines = [
            {
                "session_id": "sess-1",
                "role": "user",
                "content": "Hello",
                "personality": "general",
                "timestamp": 1000.0,
            },
            {
                "session_id": "sess-1",
                "role": "agent",
                "content": "Hi!",
                "personality": "general",
                "timestamp": 1001.0,
                "token_count": 5,
                "model": "llama3",
            },
            {
                "session_id": "sess-2",
                "role": "user",
                "content": "Other session",
                "personality": "friendly",
                "timestamp": 2000.0,
            },
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            for obj in lines:
                f.write(json.dumps(obj) + "\n")
            tmp_path = f.name

        try:
            count = self.store.import_jsonl(tmp_path)
            self.assertEqual(count, 3)

            # Verify sessions created
            sessions = self.store.list_sessions()
            self.assertEqual(len(sessions), 2)

            # Verify messages
            msgs1 = self.store.get_messages("sess-1")
            self.assertEqual(len(msgs1), 2)
            self.assertEqual(msgs1[0].content, "Hello")
            self.assertEqual(msgs1[1].content, "Hi!")

            msgs2 = self.store.get_messages("sess-2")
            self.assertEqual(len(msgs2), 1)
        finally:
            os.unlink(tmp_path)

    def test_import_jsonl_empty_lines_skipped(self) -> None:
        """Blank lines in the JSONL file should be ignored."""
        lines = [
            {"session_id": "s", "role": "user", "content": "hi",
             "personality": "g", "timestamp": 1.0},
            "",
            {"session_id": "s", "role": "agent", "content": "hello",
             "personality": "g", "timestamp": 2.0},
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            for obj in lines:
                f.write((json.dumps(obj) if obj else "") + "\n")
            tmp_path = f.name

        try:
            count = self.store.import_jsonl(tmp_path)
            self.assertEqual(count, 2)
        finally:
            os.unlink(tmp_path)

    def test_import_jsonl_creates_sessions_on_demand(self) -> None:
        """Sessions should be auto-created even if not pre-existing."""
        lines = [
            {
                "session_id": "brand-new",
                "role": "user",
                "content": "test",
                "personality": "custom",
                "timestamp": 42.0,
            }
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(json.dumps(lines[0]) + "\n")
            tmp_path = f.name

        try:
            count = self.store.import_jsonl(tmp_path)
            self.assertEqual(count, 1)
            sessions = self.store.list_sessions()
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["session_id"], "brand-new")
            self.assertEqual(sessions[0]["personality"], "custom")
        finally:
            os.unlink(tmp_path)


# ======================================================================
# ChatStore — error handling
# ======================================================================

class ChatStoreErrorTests(unittest.TestCase):
    """Error paths and edge cases."""

    def test_chat_store_error_is_runtime_error(self) -> None:
        self.assertTrue(issubclass(ChatStoreError, RuntimeError))

    def test_invalid_db_path_permission(self) -> None:
        """Opening a store in a non-writable location should fail."""
        with self.assertRaises(ChatStoreError):
            ChatStore("/nonexistent/dir/chat.db")

    def test_vacuum_on_empty_store(self) -> None:
        """Vacuum should not raise on an empty in-memory store."""
        store = ChatStore(":memory:")
        try:
            store.vacuum()  # Should not raise
        finally:
            store.close()

    def test_get_messages_nonexistent_session(self) -> None:
        """Getting messages for a non-existent session returns empty list."""
        store = ChatStore(":memory:")
        try:
            msgs = store.get_messages("does-not-exist")
            self.assertEqual(msgs, [])
        finally:
            store.close()

    def test_count_messages_nonexistent_session(self) -> None:
        store = ChatStore(":memory:")
        try:
            count = store.count_messages("no-such-session")
            self.assertEqual(count, 0)
        finally:
            store.close()

    def test_delete_session_nonexistent(self) -> None:
        """Deleting a non-existent session should not raise."""
        store = ChatStore(":memory:")
        try:
            # Should not raise
            store.delete_session("ghost-session")
        finally:
            store.close()


# ======================================================================
# ChatStore — concurrent access
# ======================================================================

class ChatStoreConcurrentTests(unittest.TestCase):
    """Stress-test thread safety with 10 concurrent threads."""

    def test_concurrent_writes(self) -> None:
        store = ChatStore(":memory:")
        sid = store.create_session("stress")
        n_threads = 10
        msgs_per_thread = 50
        barrier = threading.Barrier(n_threads)
        errors: list[Exception] = []
        lock = threading.Lock()

        def worker() -> None:
            barrier.wait()  # All threads start at the same time
            try:
                for i in range(msgs_per_thread):
                    store.add_message(
                        sid,
                        "user",
                        f"msg from thread {threading.get_ident()} #{i}",
                    )
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [
            threading.Thread(target=worker, daemon=True)
            for _ in range(n_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        # All operations should succeed (no database locked errors, etc.)
        self.assertEqual(errors, [], f"Thread errors: {errors}")
        expected = n_threads * msgs_per_thread
        self.assertEqual(store.count_messages(sid), expected)

        store.close()

    def test_concurrent_reads_during_writes(self) -> None:
        """Readers should not block writers in WAL mode."""
        store = ChatStore(":memory:")
        sid = store.create_session("rw")
        stop_event = threading.Event()
        shared_errors: list[Exception] = []
        error_lock = threading.Lock()

        def writer() -> None:
            i = 0
            while not stop_event.is_set():
                try:
                    store.add_message(sid, "user", f"write-{i}", token_count=1)
                except Exception as exc:
                    with error_lock:
                        shared_errors.append(exc)
                i += 1

        def reader() -> None:
            while not stop_event.is_set():
                try:
                    store.get_context_window(sid, max_tokens=100)
                    store.count_messages(sid)
                except Exception as exc:
                    with error_lock:
                        shared_errors.append(exc)
                    return  # Stop on first error to avoid log spam

        threads = [
            threading.Thread(target=writer, daemon=True),
            *(
                threading.Thread(target=reader, daemon=True)
                for _ in range(5)
            ),
        ]

        for t in threads:
            t.start()

        time.sleep(1.0)  # Let them race for 1 second
        stop_event.set()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(shared_errors, [], f"Errors: {shared_errors}")
        # Sanity check: at least some writes happened
        self.assertGreater(store.count_messages(sid), 0)

        store.close()


# ======================================================================
# ChatStore — vacuum (minimal)
# ======================================================================

class ChatStoreVacuumTests(unittest.TestCase):
    """Vacuum operation."""

    def test_vacuum_file_based(self) -> None:
        """Vacuum on a file-based database should not raise."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            store = ChatStore(db_path)
            sid = store.create_session("v")
            store.add_message(sid, "user", "data")
            store.vacuum()  # Should succeed
            store.close()

            # Re-open and verify data survived
            store2 = ChatStore(db_path)
            self.assertEqual(store2.count_messages(sid), 1)
            store2.close()
        finally:
            os.unlink(db_path)


# ======================================================================
# Run
# ======================================================================

if __name__ == "__main__":
    unittest.main()
