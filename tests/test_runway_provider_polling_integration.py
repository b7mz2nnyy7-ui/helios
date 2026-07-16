"""Integration tests for Runway provider task polling."""

import copy
import socket
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.media.asset import MediaAssetType
from engine.media.providers.base import MediaProviderError
from engine.media.providers.config import ProviderConfig
from integrations.runway.client import RunwayClient
from integrations.runway.models import (
    RunwayGenerationRequest,
    RunwayTask,
    normalize_runway_duration,
)
from integrations.runway.polling import RunwayPollingResult, RunwayTaskPoller
from integrations.runway.provider import RunwayVideoProvider, build_runway_prompt
from tests.test_runway_client import RecordingRunwayTransport
from tests.test_runway_provider import create_job, create_task


class RecordingRunwayTaskPoller(RunwayTaskPoller):
    """Poller returning one fixed result without sleeping or networking."""

    def __init__(self, result: RunwayPollingResult) -> None:
        """Create a fake poller without real time dependencies."""
        self.result = result
        self.calls: list[str] = []
        self.error: Exception | None = None

    def wait_for_completion(self, task_id: str) -> RunwayPollingResult:
        """Record the task ID and return or raise the configured value."""
        self.calls.append(task_id)
        if self.error is not None:
            raise self.error
        return self.result


def polling_result(
    status: str = "SUCCEEDED",
    poll_count: int = 3,
    elapsed_seconds: float = 4.5,
    output_urls: tuple[str, ...] = ("https://example.invalid/final.mp4",),
) -> RunwayPollingResult:
    """Create a deterministic polling result."""
    return RunwayPollingResult(
        task=RunwayTask(
            task_id="runway-final-9",
            status=status,
            output_urls=output_urls,
        ),
        poll_count=poll_count,
        elapsed_seconds=elapsed_seconds,
    )


def provider_with_polling(
    create_status: str,
    result: RunwayPollingResult | None = None,
) -> tuple[
    RunwayVideoProvider,
    RecordingRunwayTransport,
    RecordingRunwayTaskPoller,
]:
    """Create a provider using recording client and poller fakes."""
    transport = RecordingRunwayTransport(
        create_task(status=create_status, output_urls=()),
    )
    client = RunwayClient(
        ProviderConfig(
            provider_id="runway",
            api_key="synthetic-test-key",
            model="gen4.5",
        ),
        transport,
    )
    poller = RecordingRunwayTaskPoller(result or polling_result())
    return RunwayVideoProvider(client, poller), transport, poller


class RunwayProviderPollingIntegrationTestCase(unittest.TestCase):
    """Tests for immediate and polled provider task resolution."""

    def test_immediate_success_needs_no_poller(self) -> None:
        """Already successful create responses map directly to assets."""
        transport = RecordingRunwayTransport(create_task())
        client = RunwayClient(
            ProviderConfig(
                provider_id="runway",
                api_key="synthetic-test-key",
                model="gen4.5",
            ),
            transport,
        )
        provider = RunwayVideoProvider(client)

        asset = provider.render(create_job())

        self.assertIs(asset.asset_type, MediaAssetType.VIDEO)
        self.assertEqual(asset.metadata["poll_count"], 0)
        self.assertEqual(asset.metadata["polling_elapsed_seconds"], 0.0)
        self.assertEqual(transport.get_calls, [])

    def test_pollable_create_statuses_use_poller(self) -> None:
        """Pending, running and throttled create tasks delegate once."""
        for status in ("PENDING", "RUNNING", "THROTTLED"):
            with self.subTest(status=status):
                provider, transport, poller = provider_with_polling(status)

                asset = provider.render(create_job())

                self.assertEqual(len(transport.create_calls), 1)
                self.assertEqual(poller.calls, ["runway-task-42"])
                self.assertEqual(asset.asset_id, "asset-runway-runway-final-9")
                self.assertEqual(
                    asset.metadata["output_url"],
                    "https://example.invalid/final.mp4",
                )

    def test_polling_diagnostics_are_preserved_in_metadata(self) -> None:
        """Asset metadata retains final task and polling diagnostics."""
        provider, _, _ = provider_with_polling(
            "PENDING",
            polling_result(poll_count=7, elapsed_seconds=12.25),
        )

        asset = provider.render(create_job())

        self.assertEqual(asset.metadata["runway_task_id"], "runway-final-9")
        self.assertEqual(asset.metadata["poll_count"], 7)
        self.assertEqual(asset.metadata["polling_elapsed_seconds"], 12.25)
        self.assertEqual(asset.metadata["plan_id"], "plan-runway")
        self.assertEqual(asset.metadata["render_job_id"], "render-runway")
        self.assertEqual(asset.metadata["target_platform"], "TikTok")
        self.assertEqual(asset.metadata["total_duration_seconds"], 10.0)
        self.assertEqual(asset.metadata["scene_count"], 2)
        self.assertEqual(asset.metadata["model"], "gen4.5")

    def test_non_terminal_task_without_poller_is_rejected(self) -> None:
        """Non-terminal create responses require an explicit poller."""
        for status in ("PENDING", "RUNNING", "THROTTLED"):
            with self.subTest(status=status):
                transport = RecordingRunwayTransport(
                    create_task(status=status, output_urls=()),
                )
                client = RunwayClient(
                    ProviderConfig(
                        provider_id="runway",
                        api_key="synthetic-test-key",
                        model="gen4.5",
                    ),
                    transport,
                )

                with self.assertRaises(MediaProviderError):
                    RunwayVideoProvider(client).render(create_job())

                self.assertEqual(transport.get_calls, [])

    def test_terminal_create_failures_are_rejected(self) -> None:
        """Failed and cancelled create tasks never invoke polling."""
        for status in ("FAILED", "CANCELLED", "CANCELED"):
            with self.subTest(status=status):
                provider, _, poller = provider_with_polling(status)

                with self.assertRaises(MediaProviderError) as context:
                    provider.render(create_job())

                self.assertIn(status, str(context.exception))
                self.assertEqual(poller.calls, [])

    def test_failed_or_cancelled_polling_result_is_rejected(self) -> None:
        """Provider validates terminal status returned by a poller fake."""
        for status in ("FAILED", "CANCELLED", "CANCELED"):
            with self.subTest(status=status):
                provider, _, poller = provider_with_polling(
                    "PENDING",
                    polling_result(status=status, output_urls=()),
                )

                with self.assertRaises(MediaProviderError) as context:
                    provider.render(create_job())

                self.assertIn("did not succeed", str(context.exception))
                self.assertEqual(len(poller.calls), 1)

    def test_unknown_create_and_polling_statuses_are_rejected(self) -> None:
        """Unknown provider states cannot produce partial assets."""
        provider, _, poller = provider_with_polling("UNKNOWN")
        with self.assertRaises(MediaProviderError) as context:
            provider.render(create_job())
        self.assertIn("unknown status", str(context.exception))
        self.assertEqual(poller.calls, [])

        provider, _, _ = provider_with_polling(
            "PENDING",
            polling_result(status="UNKNOWN", output_urls=()),
        )
        with self.assertRaises(MediaProviderError):
            provider.render(create_job())

    def test_polled_output_requires_exactly_one_url(self) -> None:
        """Final polling task output remains deterministic."""
        for output_urls in (
            (),
            (
                "https://example.invalid/one.mp4",
                "https://example.invalid/two.mp4",
            ),
        ):
            with self.subTest(output_urls=output_urls):
                provider, _, _ = provider_with_polling(
                    "PENDING",
                    polling_result(output_urls=output_urls),
                )

                with self.assertRaises(MediaProviderError):
                    provider.render(create_job())

    def test_poller_error_is_propagated_without_rewrapping(self) -> None:
        """Existing poller MediaProviderError and its cause remain intact."""
        provider, _, poller = provider_with_polling("PENDING")
        cause = RuntimeError("safe fake cause")
        original = MediaProviderError("safe polling failure")
        original.__cause__ = cause
        poller.error = original

        with self.assertRaises(MediaProviderError) as context:
            provider.render(create_job())

        self.assertIs(context.exception, original)
        self.assertIs(context.exception.__cause__, cause)

    def test_unexpected_poller_error_is_wrapped_without_job_mutation(self) -> None:
        """Unexpected poller errors retain their cause and leave no partial state."""
        provider, _, poller = provider_with_polling("PENDING")
        original_error = RuntimeError("fake poller failed")
        poller.error = original_error
        job = create_job()
        original_job = copy.deepcopy(job)

        with self.assertRaises(MediaProviderError) as context:
            provider.render(job)

        self.assertIs(context.exception.__cause__, original_error)
        self.assertEqual(job, original_job)

    def test_job_request_and_plan_remain_unchanged(self) -> None:
        """Provider polling does not mutate production inputs."""
        provider, transport, _ = provider_with_polling("PENDING")
        job = create_job()
        original_job = copy.deepcopy(job)
        expected_request = RunwayGenerationRequest(
            model="gen4.5",
            prompt_text=build_runway_prompt(original_job.plan),
            ratio="720:1280",
            duration_seconds=normalize_runway_duration(
                "gen4.5",
                original_job.plan.total_duration_seconds,
            ),
            seed=None,
        )

        provider.render(job)

        self.assertEqual(job, original_job)
        self.assertEqual(transport.create_calls[0][0], expected_request)
        self.assertEqual(job.plan, original_job.plan)

    def test_provider_generated_errors_do_not_expose_api_key(self) -> None:
        """Provider errors never include configured credentials."""
        secret = "never-expose-provider-key"
        transport = RecordingRunwayTransport(
            RunwayTask(
                task_id="task-failed",
                status="FAILED",
                failure_message=f"Bearer {secret}",
            ),
        )
        client = RunwayClient(
            ProviderConfig(
                provider_id="runway",
                api_key=secret,
                model="gen4.5",
            ),
            transport,
        )

        with self.assertRaises(MediaProviderError) as context:
            RunwayVideoProvider(client).render(create_job())

        self.assertNotIn(secret, str(context.exception))

    def test_polling_integration_uses_no_real_sleep_network_or_file_io(self) -> None:
        """Fakes complete provider polling without external side effects."""
        provider, transport, poller = provider_with_polling("PENDING")

        with (
            patch.object(time, "sleep", side_effect=AssertionError("sleep")),
            patch.object(socket, "socket", side_effect=AssertionError("network")),
            patch.object(Path, "open", side_effect=AssertionError("file")),
        ):
            asset = provider.render(create_job())

        self.assertIs(asset.asset_type, MediaAssetType.VIDEO)
        self.assertEqual(len(transport.create_calls), 1)
        self.assertEqual(len(poller.calls), 1)


if __name__ == "__main__":
    unittest.main()
