"""Tests for the isolated ARGUS check registry."""

import unittest

from engine.guardian.models import CheckStatus, Severity, SystemCheckResult
from engine.guardian.registry import GuardianRegistry


class FixedCheck:
    """Check double returning one fixed result."""

    def __init__(self, check_id: str, status: CheckStatus = CheckStatus.PASS) -> None:
        self.id = check_id
        self.name = check_id.replace("_", " ").title()
        self.severity = Severity.MEDIUM
        self.status = status
        self.run_count = 0

    def run(self) -> SystemCheckResult:
        """Return the configured result and record execution."""
        self.run_count += 1
        return SystemCheckResult(
            id=self.id,
            name=self.name,
            severity=self.severity,
            status=self.status,
            summary="Fixed check complete.",
        )


class RaisingCheck(FixedCheck):
    """Check double that raises a secret-bearing exception."""

    def run(self) -> SystemCheckResult:
        """Raise a deterministic check failure."""
        msg = "api_key=must-not-leak"
        raise RuntimeError(msg)


class GuardianRegistryTestCase(unittest.TestCase):
    """Tests for registration, isolation, and execution order."""

    def test_register_list_and_unregister(self) -> None:
        """Registry stores checks by ID and returns a copied list."""
        registry = GuardianRegistry()
        runtime = FixedCheck("runtime")
        storage = FixedCheck("storage")
        registry.register(runtime)
        registry.register(storage)

        listed = registry.list()
        listed.clear()

        self.assertEqual(registry.list(), [runtime, storage])
        registry.unregister("runtime")
        self.assertEqual(registry.list(), [storage])

    def test_duplicate_registration_is_rejected(self) -> None:
        """Check IDs remain unique inside one registry."""
        registry = GuardianRegistry()
        registry.register(FixedCheck("runtime"))

        with self.assertRaisesRegex(ValueError, "runtime"):
            registry.register(FixedCheck("runtime"))

    def test_unknown_unregister_raises_key_error(self) -> None:
        """Unknown IDs preserve dictionary-style KeyError behavior."""
        with self.assertRaises(KeyError):
            GuardianRegistry().unregister("missing")

    def test_run_all_preserves_registration_order(self) -> None:
        """Checks execute synchronously in registration order."""
        registry = GuardianRegistry()
        first = FixedCheck("first")
        second = FixedCheck("second", CheckStatus.WARNING)
        registry.register(first)
        registry.register(second)

        results = registry.run_all()

        self.assertEqual([result.id for result in results], ["first", "second"])
        self.assertEqual(first.run_count, 1)
        self.assertEqual(second.run_count, 1)

    def test_run_all_isolates_errors_and_redacts_exception_text(self) -> None:
        """One broken check does not prevent later checks from running."""
        registry = GuardianRegistry(clock=lambda: 1.0)
        registry.register(RaisingCheck("broken"))
        healthy = FixedCheck("healthy")
        registry.register(healthy)

        results = registry.run_all()

        self.assertEqual(results[0].status, CheckStatus.FAIL)
        self.assertEqual(results[0].details["error_type"], "RuntimeError")
        self.assertNotIn("must-not-leak", results[0].summary)
        self.assertEqual(results[1].status, CheckStatus.PASS)
        self.assertEqual(healthy.run_count, 1)

    def test_registries_share_no_state(self) -> None:
        """Each registry owns an independent check collection."""
        first = GuardianRegistry()
        second = GuardianRegistry()
        first.register(FixedCheck("runtime"))

        self.assertEqual(len(first.list()), 1)
        self.assertEqual(second.list(), [])


if __name__ == "__main__":
    unittest.main()
