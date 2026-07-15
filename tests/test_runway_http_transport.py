"""Tests for the synchronous Runway HTTP transport."""

import json
import socket
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import cast
from unittest.mock import patch

from engine.media.providers.base import MediaProviderError
from integrations.runway.http_transport import (
    HTTPExecutor,
    HTTPResponse,
    RUNWAY_API_VERSION,
    RunwayHTTPTransport,
    UrllibHTTPExecutor,
)
from integrations.runway.models import RunwayGenerationRequest


class RecordingHTTPExecutor:
    """In-memory executor recording requests without network access."""

    def __init__(self, response: HTTPResponse) -> None:
        """Create an executor returning a fixed response."""
        self.response = response
        self.calls: list[
            tuple[str, str, Mapping[str, str], bytes | None, float]
        ] = []
        self.error: Exception | None = None

    def execute(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> HTTPResponse:
        """Record one request or raise the configured error."""
        if self.error is not None:
            raise self.error
        self.calls.append((method, url, dict(headers), body, timeout_seconds))
        return self.response


def response(
    payload: object,
    status_code: int = 200,
) -> HTTPResponse:
    """Create a JSON HTTP response."""
    return HTTPResponse(
        status_code=status_code,
        headers={"Content-Type": "application/json"},
        body=json.dumps(payload).encode("utf-8"),
    )


def request(seed: int | None = None) -> RunwayGenerationRequest:
    """Create a valid generation request."""
    return RunwayGenerationRequest(
        model="gen4.5",
        prompt_text="A precise product story.",
        ratio="768:1280",
        duration_seconds=5.0,
        seed=seed,
    )


def create_transport(
    payload: object | None = None,
    status_code: int = 200,
) -> tuple[RunwayHTTPTransport, RecordingHTTPExecutor]:
    """Create a transport with a recording executor."""
    response_payload = {"id": "task-1"} if payload is None else payload
    executor = RecordingHTTPExecutor(response(response_payload, status_code))
    return RunwayHTTPTransport(executor), executor


class HTTPResponseTestCase(unittest.TestCase):
    """Tests for immutable HTTP response values."""

    def test_response_validates_status_and_body(self) -> None:
        """Status codes and byte bodies are validated."""
        for status_code in (99, 600, True):
            with self.subTest(status_code=status_code):
                with self.assertRaises(ValueError):
                    HTTPResponse(status_code, {}, b"")

        with self.assertRaises(ValueError):
            HTTPResponse(200, {}, cast(bytes, "not-bytes"))

    def test_response_protects_headers_from_mutation(self) -> None:
        """Response headers are copied and exposed read-only."""
        headers = {"Content-Type": "application/json"}
        http_response = HTTPResponse(200, headers, b"{}")
        headers["Injected"] = "value"

        self.assertNotIn("Injected", http_response.headers)
        with self.assertRaises(TypeError):
            http_response.headers["Other"] = "value"  # type: ignore[index]

    def test_response_rejects_invalid_headers(self) -> None:
        """Header containers and values must match the protocol."""
        with self.assertRaises(ValueError):
            HTTPResponse(200, cast(Mapping[str, str], []), b"{}")
        with self.assertRaises(ValueError):
            HTTPResponse(200, cast(Mapping[str, str], {"Header": 1}), b"{}")

    def test_response_repr_hides_headers_and_body(self) -> None:
        """Potentially sensitive response data never appears in repr."""
        secret = "never-represent-this-key"
        http_response = HTTPResponse(
            401,
            {"Authorization": f"Bearer {secret}"},
            secret.encode("utf-8"),
        )

        self.assertNotIn(secret, repr(http_response))
        self.assertNotIn("Authorization", repr(http_response))


class RunwayHTTPTransportTestCase(unittest.TestCase):
    """Tests for request construction and response mapping."""

    def test_executor_contract_and_stdlib_executor_construction(self) -> None:
        """The fake satisfies the protocol and live executor is constructible."""
        executor = RecordingHTTPExecutor(response({"id": "task-1"}))
        executor_contract: HTTPExecutor = executor

        self.assertIs(executor_contract, executor)
        self.assertIsInstance(UrllibHTTPExecutor(), UrllibHTTPExecutor)

    def test_create_uses_post_headers_and_joined_url(self) -> None:
        """Create requests contain the official HTTP contract once."""
        transport, executor = create_transport()

        transport.create_video(
            request(),
            "runway-secret",
            "https://api.example/v1/",
            12.0,
        )

        method, url, headers, _, timeout = executor.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://api.example/v1/image_to_video")
        self.assertEqual(headers["Authorization"], "Bearer runway-secret")
        self.assertEqual(headers["X-Runway-Version"], RUNWAY_API_VERSION)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Accept"], "application/json")
        self.assertEqual(len(headers), 4)
        self.assertEqual(timeout, 12.0)

    def test_create_body_is_stable_and_omits_none(self) -> None:
        """Create JSON is deterministic and excludes optional None values."""
        transport, executor = create_transport()

        transport.create_video(request(), "secret", "https://api.example/v1", 10)

        body = executor.calls[0][3]
        self.assertEqual(
            body,
            (
                b'{"duration":5.0,"model":"gen4.5",'
                b'"promptText":"A precise product story.",'
                b'"ratio":"768:1280"}'
            ),
        )
        self.assertNotIn(b"seed", body or b"")
        self.assertNotIn(b"secret", body or b"")

    def test_create_includes_configured_seed(self) -> None:
        """Configured seed values are serialized."""
        transport, executor = create_transport()

        transport.create_video(
            request(seed=42),
            "secret",
            "https://api.example/v1",
            10,
        )

        body = executor.calls[0][3]
        self.assertEqual(json.loads(body or b"{}")["seed"], 42)

    def test_get_uses_get_without_body_and_encodes_task_id(self) -> None:
        """Task IDs remain one safely encoded URL path segment."""
        transport, executor = create_transport(
            {"id": "../task 1", "status": "running"},
        )

        task = transport.get_task(
            "../task 1",
            "secret",
            "https://api.example/v1/",
            8.0,
        )

        method, url, _, body, _ = executor.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, "https://api.example/v1/tasks/%2E%2E%2Ftask%201")
        self.assertIsNone(body)
        self.assertEqual(task.status, "RUNNING")

    def test_create_response_defaults_to_pending(self) -> None:
        """Official create responses with only an ID become pending tasks."""
        transport, _ = create_transport({"id": "task-1"})

        task = transport.create_video(
            request(),
            "secret",
            "https://api.example/v1",
            10,
        )

        self.assertEqual(task.task_id, "task-1")
        self.assertEqual(task.status, "PENDING")
        self.assertEqual(task.output_urls, ())

    def test_get_response_parses_outputs_as_tuple(self) -> None:
        """Completed task output URLs are mapped to an immutable tuple."""
        transport, _ = create_transport(
            {
                "id": "task-1",
                "status": "succeeded",
                "output": ["https://example.invalid/video.mp4"],
            },
        )

        task = transport.get_task(
            "task-1",
            "secret",
            "https://api.example/v1",
            10,
        )

        self.assertEqual(task.status, "SUCCEEDED")
        self.assertEqual(
            task.output_urls,
            ("https://example.invalid/video.mp4",),
        )

    def test_failed_task_maps_failure_message(self) -> None:
        """Failed task details map to the existing task model."""
        transport, _ = create_transport(
            {
                "id": "task-failed",
                "status": "FAILED",
                "failure": "Input rejected",
                "output": [],
            },
        )

        task = transport.get_task(
            "task-failed",
            "secret",
            "https://api.example/v1",
            10,
        )

        self.assertEqual(task.failure_message, "Input rejected")

    def test_supported_statuses_are_normalized(self) -> None:
        """Documented statuses are accepted and normalized consistently."""
        statuses = (
            "pending",
            "throttled",
            "running",
            "succeeded",
            "failed",
            "cancelled",
        )
        for status in statuses:
            with self.subTest(status=status):
                transport, _ = create_transport({"id": "task-1", "status": status})
                task = transport.get_task(
                    "task-1",
                    "secret",
                    "https://api.example/v1",
                    10,
                )
                self.assertEqual(task.status, status.upper())

    def test_http_failures_are_safely_wrapped(self) -> None:
        """Relevant HTTP failures expose status but never credentials."""
        secret = "highly-sensitive-key"
        for status_code in (400, 401, 429, 500):
            with self.subTest(status_code=status_code):
                transport, _ = create_transport(
                    {
                        "message": (
                            f"Authorization: Bearer {secret} request rejected"
                        ),
                        "private": "full-sensitive-response",
                    },
                    status_code,
                )
                with self.assertRaises(MediaProviderError) as context:
                    transport.create_video(
                        request(),
                        secret,
                        "https://api.example/v1",
                        10,
                    )

                message = str(context.exception)
                self.assertIn(str(status_code), message)
                self.assertNotIn(secret, message)
                self.assertNotIn("full-sensitive-response", message)

    def test_invalid_json_is_wrapped_with_cause(self) -> None:
        """Invalid JSON becomes a MediaProviderError with decoder cause."""
        executor = RecordingHTTPExecutor(HTTPResponse(200, {}, b"not-json"))
        transport = RunwayHTTPTransport(executor)

        with self.assertRaises(MediaProviderError) as context:
            transport.create_video(
                request(),
                "secret",
                "https://api.example/v1",
                10,
            )

        self.assertIsInstance(context.exception.__cause__, json.JSONDecodeError)

    def test_missing_task_fields_are_rejected(self) -> None:
        """Create requires an ID and retrieved tasks require status."""
        transport, _ = create_transport({"status": "PENDING"})
        with self.assertRaises(MediaProviderError):
            transport.create_video(
                request(),
                "secret",
                "https://api.example/v1",
                10,
            )

        transport, _ = create_transport({"id": "task-1"})
        with self.assertRaises(MediaProviderError):
            transport.get_task(
                "task-1",
                "secret",
                "https://api.example/v1",
                10,
            )

    def test_invalid_output_structure_is_rejected(self) -> None:
        """Output must be a list containing only non-empty URLs."""
        invalid_outputs: tuple[object, ...] = (
            "https://example.invalid/video.mp4",
            {"url": "https://example.invalid/video.mp4"},
            [1],
            [""],
        )
        for invalid_output in invalid_outputs:
            with self.subTest(output=invalid_output):
                transport, _ = create_transport(
                    {
                        "id": "task-1",
                        "status": "SUCCEEDED",
                        "output": invalid_output,
                    },
                )
                with self.assertRaises(MediaProviderError):
                    transport.get_task(
                        "task-1",
                        "secret",
                        "https://api.example/v1",
                        10,
                    )

    def test_executor_error_preserves_cause(self) -> None:
        """Executor failures are wrapped with their original cause."""
        transport, executor = create_transport()
        original_error = OSError("executor unavailable")
        executor.error = original_error

        with self.assertRaises(MediaProviderError) as context:
            transport.create_video(
                request(),
                "secret",
                "https://api.example/v1",
                10,
            )

        self.assertIs(context.exception.__cause__, original_error)

    def test_secret_is_absent_from_repr_and_errors(self) -> None:
        """Transport representation and validation errors hide credentials."""
        secret = "never-print-this-key"
        transport, _ = create_transport({"id": "task-1", "status": "UNKNOWN"})

        self.assertNotIn(secret, repr(transport))
        with self.assertRaises(MediaProviderError) as context:
            transport.create_video(
                request(),
                secret,
                "https://api.example/v1",
                10,
            )
        self.assertNotIn(secret, str(context.exception))

    def test_request_and_response_are_not_mutated(self) -> None:
        """Transport preserves request and raw response values."""
        generation_request = request(seed=7)
        raw_response = response({"id": "task-1"})
        original_response = (
            raw_response.status_code,
            dict(raw_response.headers),
            raw_response.body,
        )
        executor = RecordingHTTPExecutor(raw_response)
        transport = RunwayHTTPTransport(executor)

        transport.create_video(
            generation_request,
            "secret",
            "https://api.example/v1",
            10,
        )

        self.assertEqual(generation_request, request(seed=7))
        self.assertEqual(
            (
                raw_response.status_code,
                dict(raw_response.headers),
                raw_response.body,
            ),
            original_response,
        )

    def test_no_network_file_polling_or_retry_occurs(self) -> None:
        """One fake-executor call completes without external side effects."""
        transport, executor = create_transport({"id": "task-1"})

        with (
            patch.object(socket, "socket", side_effect=AssertionError("network")),
            patch.object(Path, "open", side_effect=AssertionError("file")),
        ):
            task = transport.create_video(
                request(),
                "secret",
                "https://api.example/v1",
                10,
            )

        self.assertEqual(task.status, "PENDING")
        self.assertEqual(len(executor.calls), 1)


if __name__ == "__main__":
    unittest.main()
