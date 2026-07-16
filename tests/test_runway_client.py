"""Tests for Runway models and the transport-injected client."""

import socket
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

from engine.media.providers.base import MediaProviderError
from engine.media.providers.config import (
    ProviderConfig,
    ProviderConfigurationError,
)
from integrations.runway.client import RUNWAY_DEFAULT_BASE_URL, RunwayClient
from integrations.runway.models import (
    RUNWAY_OFFICIAL_TEXT_TO_VIDEO_MODELS,
    RunwayGenerationMode,
    RunwayGenerationRequest,
    RunwayTask,
    normalize_runway_duration,
)


class RecordingRunwayTransport:
    """In-memory transport that records calls without external I/O."""

    def __init__(self, task: RunwayTask) -> None:
        """Create a transport returning a fixed task."""
        self.task = task
        self.create_calls: list[tuple[RunwayGenerationRequest, str, str, float]] = []
        self.get_calls: list[tuple[str, str, str, float]] = []
        self.error: Exception | None = None

    def create_video(
        self,
        request: RunwayGenerationRequest,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
    ) -> RunwayTask:
        """Record one create call and return the configured task."""
        if self.error is not None:
            raise self.error
        self.create_calls.append((request, api_key, base_url, timeout_seconds))
        return self.task

    def get_task(
        self,
        task_id: str,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
    ) -> RunwayTask:
        """Record one get call and return the configured task."""
        if self.error is not None:
            raise self.error
        self.get_calls.append((task_id, api_key, base_url, timeout_seconds))
        return self.task


def create_request() -> RunwayGenerationRequest:
    """Create a valid generation request."""
    return RunwayGenerationRequest(
        model="gen4.5",
        prompt_text="A deterministic product workflow.",
        ratio="720:1280",
        duration_seconds=10,
        seed=None,
    )


def create_task(status: str = "SUCCEEDED") -> RunwayTask:
    """Create a valid Runway task."""
    return RunwayTask(
        task_id="runway-task-1",
        status=status,
        output_urls=("https://example.invalid/output.mp4",),
    )


def create_config(
    api_key: str | None = "runway-secret",
    enabled: bool = True,
    base_url: str | None = "https://runway.example.invalid/v1",
) -> ProviderConfig:
    """Create a Runway provider configuration."""
    return ProviderConfig(
        provider_id="runway",
        api_key=api_key,
        base_url=base_url,
        model="gen4.5",
        timeout_seconds=25.0,
        enabled=enabled,
    )


class RunwayClientTestCase(unittest.TestCase):
    """Tests for Runway models and client transport behavior."""

    def test_generation_request_validation(self) -> None:
        """Generation requests validate required text and duration."""
        request = create_request()

        self.assertEqual(request.model, "gen4.5")
        self.assertIs(type(request.duration_seconds), int)
        self.assertIs(request.mode, RunwayGenerationMode.TEXT_TO_VIDEO)
        self.assertIsNone(request.prompt_image)
        for field_name in ("model", "prompt_text", "ratio"):
            values = {
                "model": request.model,
                "prompt_text": request.prompt_text,
                "ratio": request.ratio,
            }
            values[field_name] = " "
            with self.subTest(field_name=field_name):
                with self.assertRaises(ValueError):
                    RunwayGenerationRequest(
                        model=values["model"],
                        prompt_text=values["prompt_text"],
                        ratio=values["ratio"],
                        duration_seconds=10,
                        seed=None,
                    )

    def test_official_text_models_are_documented_separately(self) -> None:
        """The official endpoint model set is distinct from implemented support."""
        self.assertIn("gen4.5", RUNWAY_OFFICIAL_TEXT_TO_VIDEO_MODELS)
        self.assertIn("veo3.1", RUNWAY_OFFICIAL_TEXT_TO_VIDEO_MODELS)

        with self.assertRaises(ValueError):
            RunwayGenerationRequest(
                model="gen4.5",
                prompt_text="Prompt",
                ratio="720:1280",
                duration_seconds=0,
                seed=None,
            )

    def test_generation_mode_validates_image_requirements(self) -> None:
        """Only image mode accepts and requires an input image."""
        with self.assertRaises(ValueError):
            RunwayGenerationRequest(
                model="gen4.5",
                prompt_text="Prompt",
                ratio="720:1280",
                duration_seconds=5,
                mode=RunwayGenerationMode.IMAGE_TO_VIDEO,
            )
        with self.assertRaises(ValueError):
            RunwayGenerationRequest(
                model="gen4.5",
                prompt_text="Prompt",
                ratio="720:1280",
                duration_seconds=5,
                mode=RunwayGenerationMode.TEXT_TO_VIDEO,
                prompt_image="https://example.invalid/source.png",
            )

    def test_text_to_video_contract_rejects_unsupported_values(self) -> None:
        """Gen-4.5 text requests enforce model, prompt, ratio and seed."""
        invalid_requests = (
            {
                "model": "unsupported",
                "prompt_text": "Prompt",
                "ratio": "1280:720",
                "duration_seconds": 5,
            },
            {
                "model": "gen4.5",
                "prompt_text": "Prompt",
                "ratio": "768:1280",
                "duration_seconds": 5,
            },
            {
                "model": "gen4.5",
                "prompt_text": "x" * 1001,
                "ratio": "1280:720",
                "duration_seconds": 5,
            },
            {
                "model": "gen4.5",
                "prompt_text": "Prompt",
                "ratio": "1280:720",
                "duration_seconds": 5,
                "seed": 4_294_967_296,
            },
        )
        for values in invalid_requests:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    RunwayGenerationRequest(**values)  # type: ignore[arg-type]

    def test_duration_normalization_is_exact_and_model_aware(self) -> None:
        """Whole CLI floats normalize to int without silent rounding."""
        for duration in (5, 5.0):
            with self.subTest(duration=duration):
                normalized = normalize_runway_duration("gen4.5", duration)
                self.assertEqual(normalized, 5)
                self.assertIs(type(normalized), int)

        invalid_durations: tuple[int | float, ...] = (
            0,
            1,
            11,
            5.5,
            float("nan"),
            float("inf"),
            True,
        )
        for duration in invalid_durations:
            with self.subTest(duration=duration):
                with self.assertRaises(ValueError):
                    normalize_runway_duration("gen4.5", duration)

    def test_runway_task_validation(self) -> None:
        """Runway tasks validate IDs, status and output values."""
        self.assertEqual(create_task().task_id, "runway-task-1")

        with self.assertRaises(ValueError):
            RunwayTask(task_id=" ", status="SUCCEEDED")
        with self.assertRaises(ValueError):
            RunwayTask(task_id="task", status=" ")
        with self.assertRaises(ValueError):
            RunwayTask(
                task_id="task",
                status="SUCCEEDED",
                output_urls=cast(tuple[str, ...], []),
            )
        with self.assertRaises(ValueError):
            RunwayTask(
                task_id="task",
                status="SUCCEEDED",
                output_urls=("",),
            )
        with self.assertRaises(ValueError):
            RunwayTask(
                task_id="task",
                status="FAILED",
                failure_message=" ",
            )

    def test_client_requires_api_key(self) -> None:
        """Missing and blank API keys reject client construction."""
        transport = RecordingRunwayTransport(create_task())
        for api_key in (None, " "):
            with self.subTest(api_key=api_key):
                with self.assertRaises(ProviderConfigurationError):
                    RunwayClient(create_config(api_key=api_key), transport)

    def test_disabled_config_is_rejected(self) -> None:
        """Disabled provider configuration cannot create a client."""
        with self.assertRaises(ProviderConfigurationError):
            RunwayClient(
                create_config(enabled=False),
                RecordingRunwayTransport(create_task()),
            )

    def test_secret_is_absent_from_repr_and_exceptions(self) -> None:
        """Client representation and transport errors never expose API keys."""
        secret = "do-not-expose-runway-key"
        transport = RecordingRunwayTransport(create_task())
        transport.error = RuntimeError("transport unavailable")
        client = RunwayClient(create_config(api_key=secret), transport)

        self.assertNotIn(secret, repr(client))
        self.assertNotIn(secret, repr(client.config))
        with self.assertRaises(MediaProviderError) as context:
            client.create_video(create_request())
        self.assertNotIn(secret, str(context.exception))

    def test_client_forwards_configuration_to_transport(self) -> None:
        """Create calls forward the same request and configured values."""
        transport = RecordingRunwayTransport(create_task())
        config = create_config()
        client = RunwayClient(config, transport)
        request = create_request()

        task = client.create_video(request)

        self.assertIs(task, transport.task)
        self.assertEqual(
            transport.create_calls,
            [
                (
                    request,
                    "runway-secret",
                    "https://runway.example.invalid/v1",
                    25.0,
                ),
            ],
        )

    def test_client_uses_official_default_base_url(self) -> None:
        """Missing base URLs use the official Runway API convention."""
        transport = RecordingRunwayTransport(create_task())
        client = RunwayClient(create_config(base_url=None), transport)

        client.create_video(create_request())

        self.assertEqual(transport.create_calls[0][2], RUNWAY_DEFAULT_BASE_URL)

    def test_get_task_forwards_configuration(self) -> None:
        """Task retrieval forwards ID and configured transport values."""
        transport = RecordingRunwayTransport(create_task())
        client = RunwayClient(create_config(), transport)

        task = client.get_task("runway-task-1")

        self.assertIs(task, transport.task)
        self.assertEqual(
            transport.get_calls,
            [
                (
                    "runway-task-1",
                    "runway-secret",
                    "https://runway.example.invalid/v1",
                    25.0,
                ),
            ],
        )

    def test_transport_errors_are_wrapped_with_cause(self) -> None:
        """Transport errors become MediaProviderError with original cause."""
        transport = RecordingRunwayTransport(create_task())
        original_error = RuntimeError("transport unavailable")
        transport.error = original_error
        client = RunwayClient(create_config(), transport)

        with self.assertRaises(MediaProviderError) as context:
            client.create_video(create_request())

        self.assertIs(context.exception.__cause__, original_error)

    def test_client_does_not_mutate_config_or_request(self) -> None:
        """Client calls preserve configuration and immutable requests."""
        transport = RecordingRunwayTransport(create_task())
        config = create_config()
        request = create_request()
        client = RunwayClient(config, transport)

        client.create_video(request)

        self.assertIs(client.config, config)
        self.assertIs(transport.create_calls[0][0], request)

    def test_recording_transport_uses_no_file_or_network_io(self) -> None:
        """Injected recording transport permits fully local client tests."""
        transport = RecordingRunwayTransport(create_task())
        client = RunwayClient(create_config(), transport)

        with (
            patch.object(socket, "socket", side_effect=AssertionError("network")),
            patch.object(Path, "open", side_effect=AssertionError("file")),
        ):
            task = client.create_video(create_request())

        self.assertEqual(task.status, "SUCCEEDED")


if __name__ == "__main__":
    unittest.main()
