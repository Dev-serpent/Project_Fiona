"""Tests for the pairing protocol (CamComs/pairing.py).

Covers compute_fingerprint, PairingManager (submit/approve/deny/list, stale
pruning, duplicate rejection), handle_pairing_request_post, and the
PairingHttpServer start/stop lifecycle.
"""

from __future__ import annotations

import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from CamComs import CamComsIdentity, PublicKeyBundle
from CamComs.pairing import (
    PAIRING_REQUEST_TIMEOUT,
    PairingHttpServer,
    PairingManager,
    PairingRequest,
    compute_fingerprint,
    handle_pairing_request_post,
)


def _make_bundle(device_id: str = "test_device") -> PublicKeyBundle:
    return CamComsIdentity.generate(device_id).public_bundle


class ComputeFingerprintTests(unittest.TestCase):
    """compute_fingerprint() — short visual fingerprint from key bundle."""

    def test_returns_string(self) -> None:
        bundle = _make_bundle()
        fp = compute_fingerprint(bundle)
        self.assertIsInstance(fp, str)
        self.assertGreater(len(fp), 0)

    def test_returns_first_n_chars(self) -> None:
        bundle = _make_bundle()
        enc_key = bundle.to_dict()["encryption_public_key"]
        self.assertEqual(compute_fingerprint(bundle, length=8), enc_key[:8])

    def test_default_length_is_16(self) -> None:
        bundle = _make_bundle()
        self.assertEqual(len(compute_fingerprint(bundle)), 16)

    def test_different_devices_have_different_fingerprints(self) -> None:
        bundle_a = _make_bundle("device_a")
        bundle_b = _make_bundle("device_b")
        self.assertNotEqual(compute_fingerprint(bundle_a), compute_fingerprint(bundle_b))


class PairingManagerTests(unittest.TestCase):
    """PairingManager — request lifecycle, pruning, duplicate rejection."""

    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.trusted_dir = Path(self.tmpdir.name) / "trusted"
        self.manager = PairingManager(trusted_dir=self.trusted_dir)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_submit_request_returns_pairing_request(self) -> None:
        bundle = _make_bundle("sensor1")
        req = self.manager.submit_request(bundle)
        self.assertIsInstance(req, PairingRequest)
        self.assertEqual(req.device_id, "sensor1")
        self.assertIsNotNone(req.request_id)
        self.assertEqual(req.fingerprint, compute_fingerprint(bundle))

    def test_submit_request_rejects_duplicate(self) -> None:
        bundle = _make_bundle("sensor1")
        # First submit and approve — saves to trusted dir
        req = self.manager.submit_request(bundle)
        self.manager.approve_request(req.request_id)
        # Second submit with same device must raise (already in trusted dir)
        with self.assertRaises(ValueError) as ctx:
            self.manager.submit_request(bundle)
        self.assertIn("already trusted", str(ctx.exception).lower())

    def test_approve_request_returns_true(self) -> None:
        bundle = _make_bundle("sensor1")
        req = self.manager.submit_request(bundle)
        self.assertTrue(self.manager.approve_request(req.request_id))
        # The trust file should now exist
        trust_file = self.trusted_dir / "sensor1.public.json"
        self.assertTrue(trust_file.exists())

    def test_approve_request_returns_false_for_missing(self) -> None:
        self.assertFalse(self.manager.approve_request("nonexistent-id"))

    def test_approve_request_with_expiry(self) -> None:
        bundle = _make_bundle("sensor1")
        req = self.manager.submit_request(bundle)
        self.assertTrue(self.manager.approve_request(req.request_id, expires_in_days=30))
        trust_file = self.trusted_dir / "sensor1.public.json"
        import json
        data = json.loads(trust_file.read_text(encoding="utf-8"))
        self.assertIsNotNone(data.get("expires_at"))
        self.assertGreater(data["expires_at"], int(time.time()))

    def test_deny_request_returns_true(self) -> None:
        bundle = _make_bundle("sensor1")
        req = self.manager.submit_request(bundle)
        self.assertTrue(self.manager.deny_request(req.request_id))

    def test_deny_request_returns_false_for_missing(self) -> None:
        self.assertFalse(self.manager.deny_request("nonexistent-id"))

    def test_get_pending_requests_returns_requests(self) -> None:
        bundle = _make_bundle("sensor1")
        req = self.manager.submit_request(bundle)
        pending = self.manager.get_pending_requests()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].request_id, req.request_id)

    def test_get_pending_requests_empty_initially(self) -> None:
        self.assertEqual(self.manager.get_pending_requests(), [])

    def test_approved_request_removed_from_pending(self) -> None:
        bundle = _make_bundle("sensor1")
        req = self.manager.submit_request(bundle)
        self.manager.approve_request(req.request_id)
        self.assertEqual(self.manager.get_pending_requests(), [])

    def test_denied_request_removed_from_pending(self) -> None:
        bundle = _make_bundle("sensor1")
        req = self.manager.submit_request(bundle)
        self.manager.deny_request(req.request_id)
        self.assertEqual(self.manager.get_pending_requests(), [])

    def test_stale_request_is_pruned(self) -> None:
        """Requests older than PAIRING_REQUEST_TIMEOUT are pruned."""
        bundle = _make_bundle("sensor1")
        req = self.manager.submit_request(bundle)
        # Manually set the received_at far in the past
        old_time = time.monotonic() - PAIRING_REQUEST_TIMEOUT - 10
        self.manager._pending_requests[req.request_id] = PairingRequest(
            request_id=req.request_id,
            device_id=req.device_id,
            public_bundle=req.public_bundle,
            received_at=old_time,
            fingerprint=req.fingerprint,
        )
        pending = self.manager.get_pending_requests()
        self.assertEqual(pending, [])

    def test_approve_stale_request_returns_false(self) -> None:
        """After pruning, a stale request is no longer approvable."""
        bundle = _make_bundle("sensor1")
        req = self.manager.submit_request(bundle)
        old_time = time.monotonic() - PAIRING_REQUEST_TIMEOUT - 10
        self.manager._pending_requests[req.request_id] = PairingRequest(
            request_id=req.request_id,
            device_id=req.device_id,
            public_bundle=req.public_bundle,
            received_at=old_time,
            fingerprint=req.fingerprint,
        )
        # Calling get_pending_requests prunes stale entries
        self.manager.get_pending_requests()
        # Now approve should return False (request was removed by pruning)
        self.assertFalse(self.manager.approve_request(req.request_id))

    def test_multiple_pending_requests(self) -> None:
        bundle1 = _make_bundle("sensor1")
        bundle2 = _make_bundle("sensor2")
        req1 = self.manager.submit_request(bundle1)
        req2 = self.manager.submit_request(bundle2)
        pending = self.manager.get_pending_requests()
        self.assertEqual(len(pending), 2)
        ids = {r.request_id for r in pending}
        self.assertIn(req1.request_id, ids)
        self.assertIn(req2.request_id, ids)

    def test_duplicate_device_rejected_even_after_approve_then_resubmit(self) -> None:
        """After approving, the device is trusted — resubmit should raise."""
        bundle = _make_bundle("sensor1")
        req = self.manager.submit_request(bundle)
        self.manager.approve_request(req.request_id)
        with self.assertRaises(ValueError):
            self.manager.submit_request(bundle)


class HandlePairingRequestPostTests(unittest.TestCase):
    """handle_pairing_request_post() — HTTP body parsing."""

    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.manager = PairingManager(trusted_dir=Path(self.tmpdir.name) / "trusted")

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_valid_body_returns_ok(self) -> None:
        bundle = _make_bundle("http_device")
        body = json.dumps(bundle.to_dict()).encode("utf-8")
        response = handle_pairing_request_post(body, self.manager)
        self.assertTrue(response["ok"])
        self.assertIn("request_id", response)
        self.assertIn("fingerprint", response)

    def test_missing_device_id_returns_error(self) -> None:
        body = json.dumps({"encryption_public_key": "abc"}).encode("utf-8")
        response = handle_pairing_request_post(body, self.manager)
        self.assertFalse(response["ok"])
        self.assertIn("error", response)

    def test_invalid_json_returns_error(self) -> None:
        body = b"not-json-at-all"
        response = handle_pairing_request_post(body, self.manager)
        self.assertFalse(response["ok"])

    def test_empty_body_returns_error(self) -> None:
        response = handle_pairing_request_post(b"", self.manager)
        self.assertFalse(response["ok"])

    def test_duplicate_device_returns_error(self) -> None:
        bundle = _make_bundle("dup_device")
        body = json.dumps(bundle.to_dict()).encode("utf-8")
        # First request succeeds
        resp1 = handle_pairing_request_post(body, self.manager)
        self.assertTrue(resp1["ok"])
        # Approve it
        self.manager.approve_request(resp1["request_id"])
        # Second request should fail
        resp2 = handle_pairing_request_post(body, self.manager)
        self.assertFalse(resp2["ok"])


class PairingRequestDataclassTests(unittest.TestCase):
    """PairingRequest to_dict and construction."""

    def test_to_dict_contains_expected_keys(self) -> None:
        bundle = _make_bundle("test")
        req = PairingRequest(
            request_id="abc-123",
            device_id="test",
            public_bundle=bundle,
            received_at=time.monotonic(),
            fingerprint="abcd1234efgh5678",
        )
        d = req.to_dict()
        self.assertEqual(d["request_id"], "abc-123")
        self.assertEqual(d["device_id"], "test")
        self.assertEqual(d["fingerprint"], "abcd1234efgh5678")
        self.assertIn("public_key", d)


class PairingHttpServerTests(unittest.TestCase):
    """PairingHttpServer start/stop lifecycle."""

    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.manager = PairingManager(trusted_dir=Path(self.tmpdir.name) / "trusted")

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_start_stop_lifecycle(self) -> None:
        server = PairingHttpServer(self.manager, host="127.0.0.1", port=0)
        self.assertFalse(server.is_running)
        server.start()
        self.assertTrue(server.is_running)
        server.stop()
        self.assertFalse(server.is_running)

    def test_double_start_is_noop(self) -> None:
        server = PairingHttpServer(self.manager, host="127.0.0.1", port=0)
        server.start()
        self.assertTrue(server.is_running)
        # Second start should not crash
        server.start()
        self.assertTrue(server.is_running)
        server.stop()

    def test_stop_when_not_started(self) -> None:
        server = PairingHttpServer(self.manager, host="127.0.0.1", port=0)
        # Should not raise
        server.stop()
        self.assertFalse(server.is_running)


if __name__ == "__main__":
    unittest.main()
