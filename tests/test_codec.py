"""Tests for CamComs.codec — envelope encoding/decoding for ESP32 transport."""

from __future__ import annotations

import unittest

from CamComs.codec import decode_envelope, encode_envelope


class EncodeEnvelopeTests(unittest.TestCase):
    def test_encodes_simple_envelope(self):
        envelope = {"message_id": "abc123", "body": "hello"}
        encoded = encode_envelope(envelope)
        self.assertIsInstance(encoded, str)
        self.assertTrue(encoded.endswith("=") or encoded.endswith("==") or len(encoded) % 4 == 0)

    def test_encodes_empty_envelope(self):
        encoded = encode_envelope({})
        self.assertIsInstance(encoded, str)

    def test_encodes_nested_envelope(self):
        envelope = {"data": {"key": "value"}, "iv": b"binary".hex()}
        encoded = encode_envelope(envelope)
        decoded = decode_envelope(encoded)
        self.assertEqual(decoded, envelope)

    def test_encodes_with_list_value(self):
        envelope = {"items": [1, 2, 3], "name": "test"}
        encoded = encode_envelope(envelope)
        decoded = decode_envelope(encoded)
        self.assertEqual(decoded, envelope)


class DecodeEnvelopeTests(unittest.TestCase):
    def test_decodes_valid_message(self):
        envelope = {"msg": "hello", "ts": 1234567890}
        encoded = encode_envelope(envelope)
        decoded = decode_envelope(encoded)
        self.assertEqual(decoded, envelope)

    def test_decoded_content_is_dict(self):
        encoded = encode_envelope({"key": "value"})
        decoded = decode_envelope(encoded)
        self.assertIsInstance(decoded, dict)

    def test_raises_value_error_for_non_dict_result(self):
        """If the decoded JSON is not a dict, ValueError is raised."""
        import base64, json
        bad_json = json.dumps(["list", "not", "dict"])
        encoded = base64.urlsafe_b64encode(bad_json.encode("utf-8")).decode("ascii")
        with self.assertRaises(ValueError):
            decode_envelope(encoded)

    def test_raises_error_for_invalid_base64(self):
        with self.assertRaises(Exception):
            decode_envelope("not-valid-base64!!!")  # '!' is not valid base64url

    def test_raises_error_for_truncated_input(self):
        with self.assertRaises(Exception):
            decode_envelope("a")

    def test_round_trip_preserves_types(self):
        original = {"int_val": 42, "bool_val": True, "none_val": None, "str_val": "test"}
        encoded = encode_envelope(original)
        decoded = decode_envelope(encoded)
        self.assertEqual(decoded, original)

    def test_round_trip_with_unicode(self):
        original = {"emoji": "🚀", "text": "héllo wörld"}
        encoded = encode_envelope(original)
        decoded = decode_envelope(encoded)
        self.assertEqual(decoded, original)


class RoundTripTests(unittest.TestCase):
    def test_multiple_round_trips(self):
        envelopes = [
            {"id": "1"},
            {"id": "2", "data": "test"},
            {"a": 1, "b": 2, "c": 3},
            {},
        ]
        for env in envelopes:
            with self.subTest(envelope=env):
                self.assertEqual(decode_envelope(encode_envelope(env)), env)


if __name__ == "__main__":
    unittest.main()
