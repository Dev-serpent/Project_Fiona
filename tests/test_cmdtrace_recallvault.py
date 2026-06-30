"""Tests for CmdTrace and RecallVault subsystems."""

from __future__ import annotations

import csv
import json
import tempfile
import time
import unittest
from pathlib import Path

from CmdTrace import (
    append_trace,
    clear_trace,
    read_trace,
    trace_compact,
    trace_export,
    trace_search,
    trace_stats,
    trace_tail,
)
from RecallVault import (
    SemanticIndex,
    backup_recall,
    clear_recall,
    export_recall,
    forget,
    import_recall,
    list_categories,
    load_recall,
    recall_stats,
    remember,
    search_recall,
)

# ── CmdTrace Tests ─────────────────────────────────────────────────────────


class CmdTraceTests(unittest.TestCase):
    """Existing CmdTrace tests — must remain passing."""

    def test_trace_round_trip_skips_invalid_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            append_trace({"action": "host.status", "ok": True}, path)
            with path.open("a", encoding="utf-8") as handle:
                handle.write("not-json\n")
            append_trace({"action": "camcoms.paths", "ok": True}, path)

            events = read_trace(limit=10, path=path)

        self.assertEqual([event["action"] for event in events], ["host.status", "camcoms.paths"])

    def test_trace_limit_reads_latest_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            for index in range(4):
                append_trace({"index": index}, path)

            events = read_trace(limit=2, path=path)

        self.assertEqual([event["index"] for event in events], [2, 3])

    def test_clear_trace_removes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            append_trace({"action": "test"}, path)
            self.assertTrue(path.exists())
            self.assertTrue(clear_trace(path))
            self.assertFalse(path.exists())

    def test_read_trace_filtering_by_action_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            append_trace({"action": "host.status"}, path)
            append_trace({"action": "camcoms.paths"}, path)
            append_trace({"action": "host.status"}, path)

            host_events = read_trace(action_name="host.status", path=path)
            cam_events = read_trace(action_name="camcoms.paths", path=path)

            self.assertEqual(len(host_events), 2)
            self.assertEqual(len(cam_events), 1)
            self.assertTrue(all(e["action"] == "host.status" for e in host_events))


class CmdTraceNewTests(unittest.TestCase):
    """Tests for new CmdTrace functionality."""

    def test_trace_stats_empty_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.jsonl"
            stats = trace_stats(path=path)
            self.assertEqual(stats["total_events"], 0)
            self.assertEqual(stats["file_size_bytes"], 0)

    def test_trace_stats_basic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            append_trace({"action": "host.status", "ok": True}, path)
            append_trace({"action": "host.status", "ok": True}, path)
            append_trace({"action": "camcoms.ping", "ok": False}, path)

            stats = trace_stats(path=path)
            self.assertEqual(stats["total_events"], 3)
            self.assertEqual(stats["success_count"], 2)
            self.assertEqual(stats["failure_count"], 1)
            self.assertEqual(stats["per_action"], {"host.status": 2, "camcoms.ping": 1})
            self.assertGreater(stats["file_size_bytes"], 0)

    def test_trace_stats_with_duration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            append_trace({"action": "slow", "ok": True, "duration": 1.5}, path)
            append_trace({"action": "fast", "ok": True, "duration": 0.5}, path)

            stats = trace_stats(path=path)
            self.assertEqual(stats["total_duration"], 2.0)
            self.assertEqual(stats["avg_duration"], 1.0)
            self.assertEqual(stats["max_duration"], 1.5)

    def test_trace_search_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            append_trace({"action": "host.status", "detail": "running"}, path)
            append_trace({"action": "camcoms.ping", "detail": "timeout"}, path)

            results = trace_search(query="running", path=path)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["action"], "host.status")

    def test_trace_search_status_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            append_trace({"action": "a", "ok": True}, path)
            append_trace({"action": "b", "ok": False}, path)
            append_trace({"action": "c", "ok": True}, path)

            successes = trace_search(status=True, path=path)
            failures = trace_search(status=False, path=path)
            self.assertEqual(len(successes), 2)
            self.assertEqual(len(failures), 1)

    def test_trace_search_action_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            append_trace({"action": "host.status"}, path)
            append_trace({"action": "camcoms.ping"}, path)
            append_trace({"action": "host.status"}, path)

            results = trace_search(action_name="host.status", path=path)
            self.assertEqual(len(results), 2)

    def test_trace_search_regex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            append_trace({"action": "host.status"}, path)
            append_trace({"action": "camcoms.ping"}, path)

            results = trace_search(regex=r"host\.\w+", path=path)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["action"], "host.status")

    def test_trace_search_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            for i in range(10):
                append_trace({"action": "test", "index": i}, path)

            results = trace_search(limit=3, path=path)
            self.assertEqual(len(results), 3)

    def test_trace_export_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            append_trace({"action": "a", "ok": True}, path)
            append_trace({"action": "b", "ok": False}, path)

            out = trace_export(path=path, output=Path(tmp) / "export.json", fmt="json")
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["action"], "a")
            self.assertEqual(data[1]["action"], "b")

    def test_trace_export_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            append_trace({"action": "test", "ok": True, "value": 42}, path)

            out = trace_export(path=path, output=Path(tmp) / "export.csv", fmt="csv")
            with out.open("r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["action"], "test")

    def test_trace_export_auto_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            append_trace({"action": "test"}, path)

            out = trace_export(path=path, output=None, fmt="json")
            self.assertTrue(out.name.startswith("cmdtrace-export-"))
            self.assertTrue(out.name.endswith(".json"))

    def test_trace_compact_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            append_trace({"action": "test"}, path)
            original_size = path.stat().st_size

            report = trace_compact(max_size_mb=100, max_age_days=1000, path=path)
            self.assertEqual(report["original_entries"], 1)
            self.assertEqual(report["new_entries"], 1)
            self.assertEqual(path.stat().st_size, original_size)

    def test_trace_compact_by_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            for i in range(20):
                append_trace({"action": "test", "index": i}, path)

            report = trace_compact(max_size_mb=0.00001, keep_last=5, path=path)
            self.assertEqual(report["original_entries"], 20)
            self.assertEqual(report["new_entries"], 5)

    def test_trace_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            append_trace({"action": "before"}, path)

            tail = trace_tail(path=path, interval=0.05)
            append_trace({"action": "after"}, path)
            time.sleep(0.15)

            events = []
            try:
                events.append(next(tail))
            except StopIteration:
                pass
            tail.close()
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["action"], "after")

    def test_trace_tail_close(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            append_trace({"action": "first"}, path)
            tail = trace_tail(path=path, interval=0.05)
            tail.close()
            append_trace({"action": "second"}, path)
            time.sleep(0.15)
            events = []
            try:
                events.append(next(tail))
            except StopIteration:
                pass
            self.assertEqual(len(events), 0)

    def test_trace_stats_with_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            append_trace({"action": "first", "time": "2026-01-01T00:00:00"}, path)
            append_trace({"action": "second", "time": "2026-06-15T12:00:00"}, path)

            stats = trace_stats(path=path)
            self.assertEqual(stats["first_event_time"], "2026-01-01T00:00:00")
            self.assertEqual(stats["last_event_time"], "2026-06-15T12:00:00")
            self.assertIsNotNone(stats["time_span_seconds"])


# ── RecallVault Tests ──────────────────────────────────────────────────────


class RecallVaultTests(unittest.TestCase):
    """Existing RecallVault tests — must remain passing."""

    def test_remember_replaces_key_and_preserves_json_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("host-port", "8080", category="camcoms", path=path)
            remember("host-port", "5000", category="phiconnect", path=path)

            raw = json.loads(path.read_text(encoding="utf-8"))
            entries = load_recall(path)

        self.assertEqual(len(raw), 1)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].key, "host-port")
        self.assertEqual(entries[0].value, "5000")
        self.assertEqual(entries[0].category, "phiconnect")

    def test_search_recall_matches_key_value_or_category(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("phi-host", "127.0.0.1", category="network", path=path)
            remember("theme", "dark", category="gui", path=path)

            network = search_recall("network", path=path)
            localhost = search_recall("127.0", path=path)

        self.assertEqual([entry.key for entry in network], ["phi-host"])
        self.assertEqual([entry.key for entry in localhost], ["phi-host"])

    def test_forget_removes_entry_by_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("key1", "val1", path=path)
            remember("key2", "val2", path=path)

            self.assertTrue(forget("key1", path=path))
            entries = load_recall(path)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].key, "key2")
            self.assertFalse(forget("key3", path=path))

    def test_clear_recall_removes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("key1", "val1", path=path)
            self.assertTrue(path.exists())
            self.assertTrue(clear_recall(path))
            self.assertFalse(path.exists())

    def test_list_categories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("k1", "v1", category="cat1", path=path)
            remember("k2", "v2", category="cat2", path=path)
            remember("k3", "v3", category="cat1", path=path)

            cats = list_categories(path=path)
            self.assertEqual(cats, ["cat1", "cat2"])


class RecallVaultNewTests(unittest.TestCase):
    """Tests for new RecallVault functionality."""

    def test_remember_with_tags_and_ttl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("key1", "val1", tags=["tag1", "tag2"], ttl_seconds=3600, path=path)
            entries = load_recall(path)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].tags, ["tag1", "tag2"])
            self.assertEqual(entries[0].ttl_seconds, 3600)

    def test_remember_tags_default_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("key1", "val1", path=path)
            entries = load_recall(path)
            self.assertIsNone(entries[0].tags)

    def test_search_recall_matches_tags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("k1", "v1", tags=["important", "network"], path=path)
            remember("k2", "v2", tags=["normal"], path=path)

            results = search_recall("important", path=path)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].key, "k1")

    def test_ttl_expiry_on_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("expires-soon", "val", ttl_seconds=0, path=path)
            # ttl_seconds=0 means expire immediately
            entries = load_recall(path)
            self.assertEqual(len(entries), 0)

    def test_ttl_no_expiry_within_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("persistent", "val", ttl_seconds=99999, path=path)
            entries = load_recall(path)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].key, "persistent")

    def test_to_dict_omits_none_ttl_and_tags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("plain", "value", path=path)
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("ttl_seconds", raw[0])
            self.assertNotIn("tags", raw[0])

    def test_to_dict_includes_set_ttl_and_tags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("rich", "value", tags=["a"], ttl_seconds=60, path=path)
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("ttl_seconds", raw[0])
            self.assertIn("tags", raw[0])

    def test_recall_stats_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.json"
            stats = recall_stats(path=path)
            self.assertEqual(stats["total_entries"], 0)
            self.assertEqual(stats["total_storage_bytes"], 0)

    def test_recall_stats_with_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("k1", "v1", category="cat1", path=path)
            remember("k2", "v2", category="cat2", tags=["tag1"], path=path)
            remember("k3", "v3", category="cat1", tags=["tag1", "tag2"], path=path)

            stats = recall_stats(path=path)
            self.assertEqual(stats["total_entries"], 3)
            self.assertEqual(stats["per_category"], {"cat1": 2, "cat2": 1})
            self.assertEqual(stats["per_tag"], {"tag1": 2, "tag2": 1})
            self.assertEqual(stats["tagged_entries"], 2)
            self.assertEqual(stats["untagged_entries"], 1)
            self.assertGreater(stats["total_storage_bytes"], 0)
            self.assertIsNotNone(stats["oldest_entry"])
            self.assertIsNotNone(stats["newest_entry"])

    def test_export_recall_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("k1", "v1", path=path)

            out = export_recall(path=path, output=Path(tmp) / "export.json", fmt="json")
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["key"], "k1")

    def test_export_recall_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("k1", "v1", category="test", path=path)

            out = export_recall(path=path, output=Path(tmp) / "export.csv", fmt="csv")
            with out.open("r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["key"], "k1")
            self.assertEqual(rows[0]["value"], "v1")

    def test_export_recall_auto_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("k1", "v1", path=path)

            out = export_recall(path=path, output=None, fmt="json")
            self.assertTrue(out.name.startswith("recallvault-export-"))
            self.assertTrue(out.name.endswith(".json"))

    def test_import_recall_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            import_path = Path(tmp) / "import.json"
            import_path.write_text(
                json.dumps([
                    {"key": "ik1", "value": "iv1", "category": "imported"},
                    {"key": "ik2", "value": "iv2", "tags": ["a", "b"]},
                ]),
                encoding="utf-8",
            )

            count = import_recall(path=path, input=import_path)
            self.assertEqual(count, 2)
            entries = load_recall(path)
            self.assertEqual(len(entries), 2)

    def test_import_recall_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            import_path = Path(tmp) / "import.csv"
            with import_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["key", "value", "category"])
                writer.writerow(["ck1", "cv1", "testcat"])

            count = import_recall(path=path, input=import_path)
            self.assertEqual(count, 1)
            entries = load_recall(path)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].key, "ck1")

    def test_import_recall_merge_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("existing", "old-value", path=path)
            import_path = Path(tmp) / "import.json"
            import_path.write_text(
                json.dumps([{"key": "existing", "value": "new-value"}]),
                encoding="utf-8",
            )

            count = import_recall(path=path, input=import_path)
            self.assertEqual(count, 1)
            entries = load_recall(path)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].value, "new-value")

    def test_backup_recall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("bk1", "bv1", path=path)

            backup = backup_recall(path=path)
            self.assertTrue(backup.exists())
            self.assertIn("recallvault-", backup.name)

    def test_backup_recall_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nonexistent.json"
            backup = backup_recall(path=path)
            self.assertTrue(backup.exists())
            self.assertEqual(json.loads(backup.read_text(encoding="utf-8")), [])


# ── Semantic Index Tests ────────────────────────────────────────────────────


class SemanticIndexTests(unittest.TestCase):
    """Tests for the TF-IDF SemanticIndex."""

    def setUp(self) -> None:
        self.index = SemanticIndex()

    def test_empty_index_returns_empty_results(self) -> None:
        results = self.index.search("test")
        self.assertEqual(results, [])

    def test_build_and_search(self) -> None:
        entries = [
            {"key": "apple", "value": "a red fruit"},
            {"key": "banana", "value": "a yellow fruit"},
            {"key": "car", "value": "a vehicle with wheels"},
        ]
        self.index.build(entries)
        results = self.index.search("fruit")
        self.assertGreater(len(results), 0)
        # Apple and banana should rank higher than car for "fruit"
        fruit_keys = {r["key"] for r in results if r["score"] > 0}
        self.assertIn("apple", fruit_keys)
        self.assertIn("banana", fruit_keys)

    def test_search_with_tags(self) -> None:
        entries = [
            {"key": "server1", "value": "main server", "tags": ["production", "critical"]},
            {"key": "server2", "value": "backup", "tags": ["staging"]},
        ]
        self.index.build(entries)
        results = self.index.search("production")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["key"], "server1")

    def test_search_limit(self) -> None:
        entries = [
            {"key": f"doc{i}", "value": "same text for all documents"}
            for i in range(10)
        ]
        self.index.build(entries)
        results = self.index.search("text", limit=3)
        self.assertLessEqual(len(results), 3)

    def test_add_entry_marks_for_rebuild(self) -> None:
        self.index.build([{"key": "a", "value": "hello"}])
        self.assertTrue(self.index._built)
        self.index.add_entry("b", "world")
        self.assertFalse(self.index._built)

    def test_search_empty_query(self) -> None:
        self.index.build([{"key": "a", "value": "hello"}])
        results = self.index.search("")
        self.assertEqual(results, [])

    def test_score_in_range(self) -> None:
        entries = [
            {"key": "python", "value": "programming language"},
            {"key": "snake", "value": "reptile"},
        ]
        self.index.build(entries)
        results = self.index.search("python programming")
        for r in results:
            self.assertGreater(r["score"], 0)
            self.assertLessEqual(r["score"], 1.0)


if __name__ == "__main__":
    unittest.main()
