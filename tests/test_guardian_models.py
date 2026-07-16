"""Tests for immutable and secret-safe ARGUS models."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
import json
from typing import Any, cast
import unittest

from engine.guardian.models import (
    CheckStatus,
    GuardianStatus,
    Severity,
    SystemCheckResult,
    SystemHealthReport,
)


def check_result(
    status: CheckStatus = CheckStatus.PASS,
    severity: Severity = Severity.INFO,
) -> SystemCheckResult:
    """Create one valid check result for model tests."""
    return SystemCheckResult(
        id="runtime",
        name="Runtime",
        severity=severity,
        status=status,
        summary="Runtime check complete.",
        details={"running": True},
        duration_seconds=0.01,
    )


class GuardianModelsTestCase(unittest.TestCase):
    """Tests for guardian enums, result protection, and serialization."""

    def test_status_and_severity_values(self) -> None:
        """Guardian enums expose the documented string values."""
        self.assertEqual(GuardianStatus.HEALTHY.value, "HEALTHY")
        self.assertEqual(CheckStatus.SKIPPED.value, "SKIPPED")
        self.assertEqual(Severity.CRITICAL.value, "CRITICAL")

    def test_check_result_uses_utc_and_is_immutable(self) -> None:
        """Check timestamps use UTC and frozen fields reject mutation."""
        result = check_result()

        self.assertIs(result.checked_at.tzinfo, UTC)
        with self.assertRaises(FrozenInstanceError):
            setattr(result, "summary", "changed")

    def test_details_are_copied_and_recursively_protected(self) -> None:
        """External mappings cannot mutate stored check details."""
        details = {"nested": {"values": [1, 2]}}
        result = SystemCheckResult(
            id="storage",
            name="Storage",
            severity=Severity.HIGH,
            status=CheckStatus.PASS,
            summary="Storage is readable.",
            details=details,
        )
        details["nested"] = {"values": [9]}

        protected = cast(dict[str, Any], result.details)
        with self.assertRaises(TypeError):
            protected["new"] = True
        nested = cast(dict[str, Any], result.details["nested"])
        with self.assertRaises(TypeError):
            nested["new"] = True
        self.assertEqual(result.details["nested"]["values"], (1, 2))

    def test_sensitive_details_and_summary_are_redacted(self) -> None:
        """Common secret fields never survive model construction."""
        secret = "live-secret-value"
        result = SystemCheckResult(
            id="provider",
            name="Provider",
            severity=Severity.HIGH,
            status=CheckStatus.WARNING,
            summary=f"api_key={secret}",
            details={"api_key": secret, "nested": {"token": secret}},
        )

        rendered = json.dumps(json.loads(_report(result).to_json()))
        self.assertNotIn(secret, rendered)
        self.assertIn("[REDACTED]", rendered)

    def test_invalid_timestamps_and_duration_are_rejected(self) -> None:
        """Checks require UTC timestamps and non-negative durations."""
        with self.assertRaisesRegex(ValueError, "UTC"):
            SystemCheckResult(
                id="runtime",
                name="Runtime",
                severity=Severity.INFO,
                status=CheckStatus.PASS,
                summary="ok",
                checked_at=datetime.now(),
            )
        with self.assertRaisesRegex(ValueError, "negative"):
            SystemCheckResult(
                id="runtime",
                name="Runtime",
                severity=Severity.INFO,
                status=CheckStatus.PASS,
                summary="ok",
                duration_seconds=-0.1,
            )

    def test_report_serializes_to_markdown_and_json(self) -> None:
        """Reports expose complete deterministic Markdown and JSON views."""
        report = _report(check_result())

        markdown = report.to_markdown()
        payload = json.loads(report.to_json())

        self.assertIn("# ARGUS REPORT", markdown)
        self.assertIn("Runtime", markdown)
        self.assertEqual(payload["generated_by"], "Argus")
        self.assertEqual(payload["overall_status"], "HEALTHY")
        self.assertEqual(payload["checks"][0]["status"], "PASS")
        self.assertIs(report.created_at.tzinfo, UTC)

    def test_report_counters_are_copied_and_protected(self) -> None:
        """Counter mappings cannot mutate an existing report."""
        counters = {status: 0 for status in CheckStatus}
        counters[CheckStatus.PASS] = 1
        report = SystemHealthReport(
            guardian_version="0.1.0",
            overall_status=GuardianStatus.HEALTHY,
            checks=(check_result(),),
            counters=counters,
            summary="System healthy.",
        )
        counters[CheckStatus.PASS] = 99

        protected = cast(dict[CheckStatus, int], report.counters)
        with self.assertRaises(TypeError):
            protected[CheckStatus.PASS] = 2
        self.assertEqual(report.counters[CheckStatus.PASS], 1)


def _report(result: SystemCheckResult) -> SystemHealthReport:
    counters = {status: int(status is result.status) for status in CheckStatus}
    return SystemHealthReport(
        guardian_version="0.1.0",
        overall_status=GuardianStatus.HEALTHY,
        checks=(result,),
        counters=counters,
        summary="System healthy.",
    )


if __name__ == "__main__":
    unittest.main()
