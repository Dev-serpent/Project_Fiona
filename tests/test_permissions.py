"""Tests for FionaCore.permissions — sender-specific permission profiles."""

from __future__ import annotations

import unittest

from FionaCore.permissions import (
    PROFILES,
    RISK_ORDER,
    PermissionProfile,
    permission_allows,
    permission_profile,
)


class PermissionProfileDataclassTests(unittest.TestCase):
    def test_default_name(self):
        p = PermissionProfile("test", "low", frozenset({"read"}))
        self.assertEqual(p.name, "test")

    def test_default_max_risk(self):
        p = PermissionProfile("test", "high", frozenset())
        self.assertEqual(p.max_risk, "high")

    def test_default_allowed_permissions(self):
        p = PermissionProfile("test", "low", frozenset({"read", "write"}))
        self.assertEqual(p.allowed_permissions, frozenset({"read", "write"}))

    def test_frozen_cannot_be_modified(self):
        p = PermissionProfile("test", "low", frozenset({"read"}))
        with self.assertRaises(AttributeError):
            p.name = "other"  # type: ignore[misc]

    def test_hashable(self):
        p1 = PermissionProfile("a", "low", frozenset({"read"}))
        p2 = PermissionProfile("a", "low", frozenset({"read"}))
        self.assertEqual(hash(p1), hash(p2))


class BuiltinProfilesTests(unittest.TestCase):
    def test_local_profile_has_high_max_risk(self):
        self.assertEqual(PROFILES["local"].max_risk, "high")

    def test_local_profile_includes_gui_permission(self):
        self.assertIn("gui", PROFILES["local"].allowed_permissions)

    def test_agent_profile_has_medium_max_risk(self):
        self.assertEqual(PROFILES["agent"].max_risk, "medium")

    def test_agent_profile_excludes_gui(self):
        self.assertNotIn("gui", PROFILES["agent"].allowed_permissions)

    def test_remote_safe_profile_has_low_max_risk(self):
        self.assertEqual(PROFILES["remote_safe"].max_risk, "low")

    def test_remote_safe_profile_only_allows_read(self):
        self.assertEqual(PROFILES["remote_safe"].allowed_permissions, frozenset({"read"}))

    def test_all_profiles_have_valid_risk_levels(self):
        for name, profile in PROFILES.items():
            with self.subTest(profile=name):
                self.assertIn(profile.max_risk, RISK_ORDER)


class PermissionProfileFunctionTests(unittest.TestCase):
    def test_permission_profile_known_name(self):
        p = permission_profile("local")
        self.assertIs(p, PROFILES["local"])

    def test_permission_profile_unknown_name_falls_to_remote_safe(self):
        p = permission_profile("nonexistent")
        self.assertIs(p, PROFILES["remote_safe"])

    def test_permission_profile_empty_name_falls_to_remote_safe(self):
        p = permission_profile("")
        self.assertIs(p, PROFILES["remote_safe"])


class PermissionAllowsTests(unittest.TestCase):
    def test_allows_low_risk_read_for_local(self):
        self.assertTrue(permission_allows(profile="local", risk="low", permission="read"))

    def test_allows_high_risk_service_for_local(self):
        self.assertTrue(permission_allows(profile="local", risk="high", permission="service"))

    def test_denies_high_risk_for_remote_safe(self):
        self.assertFalse(permission_allows(profile="remote_safe", risk="high", permission="control"))

    def test_denies_medium_risk_for_remote_safe(self):
        self.assertFalse(permission_allows(profile="remote_safe", risk="medium", permission="read"))

    def test_allows_low_risk_read_for_remote_safe(self):
        self.assertTrue(permission_allows(profile="remote_safe", risk="low", permission="read"))

    def test_allows_medium_risk_for_agent(self):
        self.assertTrue(permission_allows(profile="agent", risk="medium", permission="control"))

    def test_denies_high_risk_for_agent(self):
        self.assertFalse(permission_allows(profile="agent", risk="high", permission="service"))

    def test_denies_permission_not_in_allowed_set(self):
        self.assertFalse(permission_allows(profile="remote_safe", risk="low", permission="network"))

    def test_unknown_risk_is_treated_as_high(self):
        self.assertFalse(permission_allows(profile="local", risk="extreme", permission="read"))

    def test_unknown_profile_falls_to_remote_safe(self):
        self.assertTrue(permission_allows(profile="unknown", risk="low", permission="read"))

    def test_unknown_profile_denies_medium_risk(self):
        self.assertFalse(permission_allows(profile="unknown", risk="medium", permission="read"))


class RiskOrderTests(unittest.TestCase):
    def test_risk_order_low_first(self):
        self.assertEqual(RISK_ORDER["low"], 1)

    def test_risk_order_medium_second(self):
        self.assertEqual(RISK_ORDER["medium"], 2)

    def test_risk_order_high_third(self):
        self.assertEqual(RISK_ORDER["high"], 3)

    def test_risk_order_immutable_keys(self):
        expected = {"low": 1, "medium": 2, "high": 3}
        self.assertEqual(RISK_ORDER, expected)


if __name__ == "__main__":
    unittest.main()
