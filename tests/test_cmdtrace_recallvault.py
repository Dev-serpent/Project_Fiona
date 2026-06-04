from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from CmdTrace import append_trace, read_trace
from RecallVault import load_recall, remember, search_recall


class CmdTraceTests(unittest.TestCase):
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
        from CmdTrace import clear_trace
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


class RecallVaultTests(unittest.TestCase):
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
        from RecallVault import forget
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
        from RecallVault import clear_recall
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("key1", "val1", path=path)
            self.assertTrue(path.exists())
            self.assertTrue(clear_recall(path))
            self.assertFalse(path.exists())

    def test_list_categories(self) -> None:
        from RecallVault import list_categories
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recall.json"
            remember("k1", "v1", category="cat1", path=path)
            remember("k2", "v2", category="cat2", path=path)
            remember("k3", "v3", category="cat1", path=path)

            cats = list_categories(path=path)
            self.assertEqual(cats, ["cat1", "cat2"])


if __name__ == "__main__":
    unittest.main()
