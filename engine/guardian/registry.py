"""Registry for deterministic ARGUS system checks."""

import builtins
from collections.abc import Callable
import time

from engine.guardian.checks import SystemCheck
from engine.guardian.models import CheckStatus, SystemCheckResult


class GuardianRegistry:
    """Store and execute system checks in registration order."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        """Create an isolated empty check registry."""
        self._checks: dict[str, SystemCheck] = {}
        self._clock = clock

    def register(self, check: SystemCheck) -> None:
        """Register one uniquely identified guardian check."""
        if check.id in self._checks:
            msg = f"Guardian check '{check.id}' is already registered."
            raise ValueError(msg)
        self._checks[check.id] = check

    def unregister(self, check_id: str) -> None:
        """Remove one check by ID or raise KeyError when unknown."""
        del self._checks[check_id]

    def list(self) -> builtins.list[SystemCheck]:
        """Return a copy of all checks in registration order."""
        return list(self._checks.values())

    def run_all(self) -> builtins.list[SystemCheckResult]:
        """Execute every check while isolating individual failures."""
        results: builtins.list[SystemCheckResult] = []
        for check in self._checks.values():
            started_at = self._clock()
            try:
                results.append(check.run())
            except Exception as error:
                results.append(
                    SystemCheckResult(
                        id=check.id,
                        name=check.name,
                        severity=check.severity,
                        status=CheckStatus.FAIL,
                        summary=f"{check.name} check failed.",
                        details={"error_type": type(error).__name__},
                        duration_seconds=max(0.0, self._clock() - started_at),
                    ),
                )
        return results
