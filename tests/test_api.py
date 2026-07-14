"""Tests for the local Helios HTTP API."""

import socket
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.api.app import create_app
from apps.api.models import ContentPipelineRequest, ContentPipelineResponse
from apps.api.service import ContentPipelineService


class FailingContentPipelineService(ContentPipelineService):
    """Service that fails deterministically for API error tests."""

    def execute(
        self,
        request: ContentPipelineRequest,
    ) -> ContentPipelineResponse:
        """Raise a deterministic pipeline error."""
        del request
        msg = "internal pipeline details"
        raise RuntimeError(msg)


class HeliosAPITestCase(unittest.TestCase):
    """Tests for local API behavior and isolation."""

    def setUp(self) -> None:
        """Create a fresh local test client for each test."""
        self.client = TestClient(create_app())

    def test_health_returns_ok(self) -> None:
        """The health endpoint reports a successful local process."""
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_valid_pipeline_request_returns_success(self) -> None:
        """A valid request executes the complete pipeline."""
        response = self.client.post(
            "/api/v1/content-pipeline",
            json={"query": "AI Agents"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "COMPLETED")

    def test_response_contains_all_required_fields(self) -> None:
        """The response contains the documented API contract."""
        response = self.client.post(
            "/api/v1/content-pipeline",
            json={"query": "AI Agents"},
        )

        self.assertEqual(
            set(response.json()),
            {
                "status",
                "query",
                "completed_task_ids",
                "script_title",
                "selected_hook",
                "storyboard_scene_count",
                "target_platform",
                "total_duration_seconds",
                "render_job_id",
                "render_job_status",
                "report_markdown",
            },
        )

    def test_response_contains_twelve_completed_tasks(self) -> None:
        """The response reports all twelve pipeline steps."""
        response = self.client.post(
            "/api/v1/content-pipeline",
            json={"query": "AI Agents"},
        )

        self.assertEqual(len(response.json()["completed_task_ids"]), 12)

    def test_render_job_is_pending(self) -> None:
        """The local pipeline returns a provider-neutral pending render job."""
        response = self.client.post(
            "/api/v1/content-pipeline",
            json={"query": "AI Agents"},
        )

        self.assertEqual(response.json()["render_job_status"], "PENDING")

    def test_empty_query_returns_422(self) -> None:
        """Blank queries are rejected by the request contract."""
        response = self.client.post(
            "/api/v1/content-pipeline",
            json={"query": "   "},
        )

        self.assertEqual(response.status_code, 422)

    def test_non_positive_duration_returns_422(self) -> None:
        """Non-positive target durations are rejected."""
        response = self.client.post(
            "/api/v1/content-pipeline",
            json={"query": "AI Agents", "target_duration_seconds": 0},
        )

        self.assertEqual(response.status_code, 422)

    def test_pipeline_error_returns_controlled_http_error(self) -> None:
        """Internal errors are translated without exposing their details."""
        client = TestClient(create_app(FailingContentPipelineService))

        response = client.post(
            "/api/v1/content-pipeline",
            json={"query": "AI Agents"},
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {"detail": "Content pipeline execution failed."},
        )
        self.assertNotIn("internal pipeline details", response.text)

    def test_requests_use_separate_service_instances(self) -> None:
        """Each request receives an independent pipeline service."""
        services: list[ContentPipelineService] = []

        def service_factory() -> ContentPipelineService:
            service = ContentPipelineService()
            services.append(service)
            return service

        client = TestClient(create_app(service_factory))
        first = client.post(
            "/api/v1/content-pipeline",
            json={"query": "AI Agents"},
        )
        second = client.post(
            "/api/v1/content-pipeline",
            json={"query": "Content Systems"},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(services), 2)
        self.assertIsNot(services[0], services[1])
        self.assertNotEqual(first.json()["query"], second.json()["query"])

    def test_pipeline_execution_uses_no_network(self) -> None:
        """The service completes while outbound sockets are disabled."""
        service = ContentPipelineService()
        request = ContentPipelineRequest(query="AI Agents")

        with patch.object(socket, "socket", side_effect=AssertionError("network used")):
            response = service.execute(request)

        self.assertEqual(response.status, "COMPLETED")

    def test_pipeline_execution_writes_no_files(self) -> None:
        """The API service performs no automatic file persistence."""
        service = ContentPipelineService()
        request = ContentPipelineRequest(query="AI Agents")

        with patch.object(
            Path,
            "write_text",
            side_effect=AssertionError("file write used"),
        ):
            response = service.execute(request)

        self.assertEqual(response.status, "COMPLETED")


if __name__ == "__main__":
    unittest.main()
