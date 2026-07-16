"""Tests for the local Helios HTTP API."""

import json
import os
import socket
import struct
import unittest
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.api.app import create_app
from apps.api.models import ContentPipelineRequest, ContentPipelineResponse
from apps.api.service import ContentPipelineService
from engine.guardian.guardian import ArgusGuardian, GuardianContext, create_guardian
from engine.media.scanner import MediaStorageScanner


def api_mp4_bytes(duration_seconds: float = 6.0) -> bytes:
    """Create a minimal MP4 payload for API streaming tests."""
    timescale = 1000
    duration = int(duration_seconds * timescale)
    mvhd_payload = b"\x00\x00\x00\x00" + struct.pack(
        ">IIII",
        0,
        0,
        timescale,
        duration,
    )
    mvhd = struct.pack(">I4s", len(mvhd_payload) + 8, b"mvhd") + mvhd_payload
    moov = struct.pack(">I4s", len(mvhd) + 8, b"moov") + mvhd
    return struct.pack(">I4s", 16, b"ftyp") + b"isom\x00\x00\x00\x00" + moov


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


class VideoAPITestCase(unittest.TestCase):
    """Tests for local video discovery and HTTP streaming."""

    def setUp(self) -> None:
        """Create one temporary video catalog and isolated API client."""
        self.temporary_directory = TemporaryDirectory()
        self.output_directory = Path(self.temporary_directory.name)
        self.video_bytes = api_mp4_bytes()
        self.video_path = self.output_directory / "gen45-demo.mp4"
        self.video_path.write_bytes(self.video_bytes)
        self.video_path.with_suffix(".json").write_text(
            json.dumps({"model": "gen4.5", "provider": "runway"}),
            encoding="utf-8",
        )

        def scanner_factory() -> MediaStorageScanner:
            return MediaStorageScanner(self.output_directory)

        self.client = TestClient(create_app(scanner_factory=scanner_factory))
        self.video_id = self.client.get("/api/videos").json()[0]["id"]

    def tearDown(self) -> None:
        """Remove temporary catalog files."""
        self.temporary_directory.cleanup()

    def test_video_list_returns_required_summary_fields(self) -> None:
        """GET /api/videos exposes the compact catalog contract."""
        response = self.client.get("/api/videos")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(
            set(payload[0]),
            {
                "id",
                "filename",
                "created_at",
                "duration",
                "size_bytes",
                "sha256",
                "model",
            },
        )
        self.assertEqual(payload[0]["duration"], 6.0)
        self.assertEqual(payload[0]["model"], "gen4.5")
        self.assertEqual(payload[0]["sha256"], sha256(self.video_bytes).hexdigest())

    def test_video_detail_returns_complete_metadata(self) -> None:
        """GET /api/videos/{id} includes MIME and sidecar metadata."""
        response = self.client.get(f"/api/videos/{self.video_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mime_type"], "video/mp4")
        self.assertEqual(payload["metadata"]["provider"], "runway")

    def test_video_stream_returns_complete_mp4(self) -> None:
        """A request without Range streams the entire local file."""
        response = self.client.get(f"/api/videos/{self.video_id}/stream")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.video_bytes)
        self.assertEqual(response.headers["accept-ranges"], "bytes")
        self.assertEqual(response.headers["content-type"], "video/mp4")
        self.assertEqual(
            response.headers["content-length"],
            str(len(self.video_bytes)),
        )

    def test_video_stream_supports_bounded_range(self) -> None:
        """A bounded Range request returns exactly the selected bytes."""
        response = self.client.get(
            f"/api/videos/{self.video_id}/stream",
            headers={"Range": "bytes=4-11"},
        )

        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, self.video_bytes[4:12])
        self.assertEqual(
            response.headers["content-range"],
            f"bytes 4-11/{len(self.video_bytes)}",
        )
        self.assertEqual(response.headers["content-length"], "8")

    def test_video_stream_supports_open_and_suffix_ranges(self) -> None:
        """Open-ended and suffix byte ranges follow HTTP semantics."""
        open_response = self.client.get(
            f"/api/videos/{self.video_id}/stream",
            headers={"Range": "bytes=8-"},
        )
        suffix_response = self.client.get(
            f"/api/videos/{self.video_id}/stream",
            headers={"Range": "bytes=-7"},
        )

        self.assertEqual(open_response.content, self.video_bytes[8:])
        self.assertEqual(suffix_response.content, self.video_bytes[-7:])
        self.assertEqual(open_response.status_code, 206)
        self.assertEqual(suffix_response.status_code, 206)

    def test_invalid_range_returns_416(self) -> None:
        """Unsatisfiable ranges return the complete file size."""
        response = self.client.get(
            f"/api/videos/{self.video_id}/stream",
            headers={"Range": f"bytes={len(self.video_bytes)}-"},
        )

        self.assertEqual(response.status_code, 416)
        self.assertEqual(
            response.headers["content-range"],
            f"bytes */{len(self.video_bytes)}",
        )

    def test_unknown_video_returns_404_for_detail_and_stream(self) -> None:
        """Unknown public IDs never expose filesystem paths."""
        for path in (
            "/api/videos/missing",
            "/api/videos/missing/stream",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), {"detail": "Video not found."})


class SystemGuardianAPITestCase(unittest.TestCase):
    """Tests for ARGUS JSON and Markdown API endpoints."""

    def setUp(self) -> None:
        """Create an isolated output directory and guardian API client."""
        self.temporary_directory = TemporaryDirectory()
        output_directory = Path(self.temporary_directory.name)

        def guardian_factory() -> ArgusGuardian:
            return create_guardian(
                GuardianContext(
                    runtime_probe=lambda: True,
                    output_directory=output_directory,
                ),
            )

        self.client = TestClient(create_app(guardian_factory=guardian_factory))

    def tearDown(self) -> None:
        """Remove temporary guardian API state."""
        self.temporary_directory.cleanup()

    def test_system_health_returns_complete_json_report(self) -> None:
        """GET /api/system/health exposes all ARGUS report fields."""
        response = self.client.get("/api/system/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["generated_by"], "Argus")
        self.assertEqual(payload["overall_status"], "HEALTHY")
        self.assertEqual(len(payload["checks"]), 15)
        self.assertIn("counters", payload)
        self.assertIn("created_at", payload)

    def test_system_report_returns_markdown(self) -> None:
        """GET /api/system/report returns the readable ARGUS report."""
        response = self.client.get("/api/system/report")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/markdown"))
        self.assertIn("# ARGUS REPORT", response.text)
        self.assertIn("Overall: **HEALTHY**", response.text)

    def test_system_health_runs_fresh_inspections(self) -> None:
        """Repeated requests return independent current UTC reports."""
        first = self.client.get("/api/system/health").json()
        second = self.client.get("/api/system/health").json()

        self.assertIsNot(first, second)
        self.assertEqual(first["guardian_version"], second["guardian_version"])

    def test_system_endpoints_expose_no_secret_values(self) -> None:
        """Guardian API output contains no environment or API key values."""
        secret = "must-not-appear"
        with patch.dict(os.environ, {"HELIOS_MEDIA_RUNWAY_API_KEY": secret}):
            health = self.client.get("/api/system/health")
            report = self.client.get("/api/system/report")

        self.assertNotIn(secret, health.text)
        self.assertNotIn(secret, report.text)


if __name__ == "__main__":
    unittest.main()
