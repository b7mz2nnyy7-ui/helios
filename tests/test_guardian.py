"""Tests for ARGUS report aggregation and default composition."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from engine.guardian.guardian import ArgusGuardian, GuardianContext, create_guardian
from engine.guardian.models import CheckStatus, GuardianStatus, Severity
from engine.guardian.registry import GuardianRegistry
from tests.test_guardian_registry import FixedCheck


class GuardianTestCase(unittest.TestCase):
    """Tests for status aggregation and standard check composition."""

    def test_all_pass_and_skipped_results_are_healthy(self) -> None:
        """Skipped optional integrations remain neutral."""
        registry = GuardianRegistry()
        registry.register(FixedCheck("runtime", CheckStatus.PASS))
        registry.register(FixedCheck("optional", CheckStatus.SKIPPED))

        report = ArgusGuardian(registry).inspect()

        self.assertEqual(report.overall_status, GuardianStatus.HEALTHY)
        self.assertEqual(report.counters[CheckStatus.PASS], 1)
        self.assertEqual(report.counters[CheckStatus.SKIPPED], 1)

    def test_warning_produces_degraded_status(self) -> None:
        """Any warning degrades the overall report."""
        registry = GuardianRegistry()
        registry.register(FixedCheck("provider", CheckStatus.WARNING))

        report = ArgusGuardian(registry).inspect()

        self.assertEqual(report.overall_status, GuardianStatus.DEGRADED)

    def test_noncritical_failure_produces_degraded_status(self) -> None:
        """A noncritical failed check remains degraded rather than unhealthy."""
        registry = GuardianRegistry()
        registry.register(FixedCheck("storage", CheckStatus.FAIL))

        report = ArgusGuardian(registry).inspect()

        self.assertEqual(report.overall_status, GuardianStatus.DEGRADED)

    def test_critical_failure_produces_unhealthy_status(self) -> None:
        """A critical failed check makes the full system unhealthy."""
        check = FixedCheck("backend", CheckStatus.FAIL)
        check.severity = Severity.CRITICAL
        registry = GuardianRegistry()
        registry.register(check)

        report = ArgusGuardian(registry).inspect()

        self.assertEqual(report.overall_status, GuardianStatus.UNHEALTHY)

    def test_default_guardian_registers_all_standard_checks(self) -> None:
        """Factory composition includes exactly the documented check set."""
        with TemporaryDirectory() as directory:
            guardian = create_guardian(
                GuardianContext(output_directory=Path(directory)),
            )

            check_ids = [check.id for check in guardian.registry.list()]

        self.assertEqual(
            check_ids,
            [
                "runtime",
                "agent_registry",
                "supervisor",
                "operations_monitor",
                "alert_service",
                "provider_registry",
                "provider_config",
                "storage",
                "video_scanner",
                "pipeline",
                "backend_api",
                "frontend",
                "render_queue",
                "output_directory",
                "health_endpoint",
            ],
        )

    def test_inspections_create_independent_reports(self) -> None:
        """Repeated observations share no report or counter state."""
        registry = GuardianRegistry()
        registry.register(FixedCheck("runtime"))
        guardian = ArgusGuardian(registry)

        first = guardian.inspect()
        second = guardian.inspect()

        self.assertIsNot(first, second)
        self.assertIsNot(first.counters, second.counters)
        self.assertEqual(first.to_json(), second.to_json().replace(
            second.created_at.isoformat(), first.created_at.isoformat()
        ).replace(
            second.checks[0].checked_at.isoformat(),
            first.checks[0].checked_at.isoformat(),
        ))


if __name__ == "__main__":
    unittest.main()
