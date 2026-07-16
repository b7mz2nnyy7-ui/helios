"""Tests for the local Mission Studio backend."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
from typing import cast
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.api.app import create_app
from apps.api.mission_models import (
    Mission,
    MissionPipelineState,
    MissionPlatform,
    MissionStage,
    MissionStatus,
)
from apps.api.mission_repository import MissionRepository
from apps.api.mission_service import (
    MissionService,
    PipelineFactory,
    TaskIdGenerator,
)
from engine.media.scanner import MediaStorageScanner
from engine.runtime.runtime import HeliosRuntime
from workflows.content_pipeline import ContentPipeline


def fixed_time() -> datetime:
    """Return a stable UTC timestamp for mission tests."""
    return datetime(2026, 7, 16, 12, 0, tzinfo=UTC)


def sample_mission(mission_id: str = "mission-1") -> Mission:
    """Create one valid immutable mission."""
    return Mission(
        mission_id=mission_id,
        title="AI Agents",
        prompt="AI Agents",
        platform=MissionPlatform.YOUTUBE,
        duration=30,
        render_model="gen4.5",
        status=MissionStatus.QUEUED,
        created_at=fixed_time(),
        updated_at=fixed_time(),
        pipeline_state=MissionPipelineState(MissionStage.RESEARCH),
    )


class MissionModelTestCase(unittest.TestCase):
    """Validate mission enums and immutable state models."""

    def test_statuses_and_stages_match_public_contract(self) -> None:
        """Mission lifecycle values remain stable for API consumers."""
        self.assertEqual(
            [status.value for status in MissionStatus],
            ["QUEUED", "RUNNING", "COMPLETED", "FAILED"],
        )
        self.assertEqual(
            [stage.value for stage in MissionStage],
            [
                "Research",
                "Script",
                "Storyboard",
                "Rendering",
                "Download",
                "Completed",
            ],
        )

    def test_mission_is_immutable_and_uses_utc(self) -> None:
        """Mission snapshots cannot be changed by API consumers."""
        mission = sample_mission()

        self.assertIs(mission.created_at.tzinfo, UTC)
        with self.assertRaises(FrozenInstanceError):
            mission.status = MissionStatus.RUNNING  # type: ignore[misc]

    def test_invalid_duration_is_rejected(self) -> None:
        """Only the three Mission Studio duration choices are accepted."""
        with self.assertRaises(ValueError):
            Mission(
                **{
                    **sample_mission().__dict__,
                    "duration": 20,
                },
            )


class MissionRepositoryTestCase(unittest.TestCase):
    """Verify isolated local mission storage."""

    def test_register_get_save_list_and_count(self) -> None:
        """Repository operations preserve immutable mission snapshots."""
        repository = MissionRepository()
        mission = sample_mission()
        repository.register(mission)

        self.assertIs(repository.get(mission.mission_id), mission)
        self.assertEqual(repository.all(), [mission])
        self.assertEqual(repository.count(), 1)

    def test_duplicate_and_unknown_ids_are_rejected(self) -> None:
        """Mission IDs remain unique and unknown values raise KeyError."""
        repository = MissionRepository()
        repository.register(sample_mission())

        with self.assertRaises(ValueError):
            repository.register(sample_mission())
        with self.assertRaises(KeyError):
            repository.get("missing")


class MissionServiceTestCase(unittest.TestCase):
    """Exercise the complete local mission lifecycle."""

    def setUp(self) -> None:
        """Create an isolated repository and output directory."""
        self.temporary_directory = TemporaryDirectory()
        self.output_directory = Path(self.temporary_directory.name)
        self.repository = MissionRepository()

    def tearDown(self) -> None:
        """Remove generated local media."""
        self.temporary_directory.cleanup()

    def test_existing_pipeline_drives_real_stages_and_completes(self) -> None:
        """Mission stages follow actual pipeline task execution."""
        observed_stages: list[MissionStage] = []

        def pipeline_factory(task_id_generator: TaskIdGenerator) -> ContentPipeline:
            def recording_generator(step: str) -> str:
                task_id = task_id_generator(step)
                observed_stages.append(
                    self.repository.get("mission-1").pipeline_state.current_stage,
                )
                return task_id

            return ContentPipeline(
                HeliosRuntime(),
                task_id_generator=recording_generator,
            )

        service = MissionService(
            self.repository,
            output_directory=self.output_directory,
            pipeline_factory=cast(PipelineFactory, pipeline_factory),
            mission_id_factory=lambda: "mission-1",
            clock=fixed_time,
        )
        mission = service.create(
            prompt="AI Agents",
            platform=MissionPlatform.INSTAGRAM,
            duration=30,
            render_model="gen4.5",
        )
        service.execute(mission.mission_id)

        completed = service.get(mission.mission_id)
        self.assertEqual(completed.status, MissionStatus.COMPLETED)
        self.assertEqual(completed.pipeline_state.current_stage, MissionStage.COMPLETED)
        self.assertEqual(len(completed.pipeline_state.completed_task_ids), 12)
        self.assertIn(MissionStage.RESEARCH, observed_stages)
        self.assertIn(MissionStage.SCRIPT, observed_stages)
        self.assertIn(MissionStage.STORYBOARD, observed_stages)
        self.assertIsNotNone(completed.render_job_id)
        self.assertIsNotNone(completed.video_id)

    def test_completed_mission_is_visible_to_video_scanner(self) -> None:
        """Publishing the mock render immediately adds one gallery item."""
        service = self._service()
        mission = self._create(service)
        service.execute(mission.mission_id)

        videos = MediaStorageScanner(self.output_directory).scan()
        completed = service.get(mission.mission_id)
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0].video_id, completed.video_id)
        self.assertEqual(videos[0].duration, 30.0)
        self.assertEqual(videos[0].model, "gen4.5")
        self.assertEqual(videos[0].metadata["target_platform"], "YouTube")

    def test_pipeline_failure_marks_mission_failed_without_details(self) -> None:
        """Internal pipeline errors produce a controlled FAILED mission."""
        class FailingPipeline:
            def run(self, *_args: object, **_kwargs: object) -> object:
                msg = "sensitive internal failure"
                raise RuntimeError(msg)

        service = MissionService(
            self.repository,
            output_directory=self.output_directory,
            pipeline_factory=cast(
                PipelineFactory,
                lambda _generator: FailingPipeline(),
            ),
            mission_id_factory=lambda: "mission-1",
            clock=fixed_time,
        )
        mission = self._create(service)
        service.execute(mission.mission_id)

        failed = service.get(mission.mission_id)
        self.assertEqual(failed.status, MissionStatus.FAILED)
        self.assertEqual(failed.error_message, "Mission execution failed.")
        self.assertNotIn("sensitive", failed.error_message or "")
        self.assertIsNone(failed.video_id)

    def test_local_pipeline_uses_no_network(self) -> None:
        """Mission execution remains fully local under the mock provider."""
        service = self._service()
        mission = self._create(service)

        with patch.object(
            socket,
            "socket",
            side_effect=AssertionError("network used"),
        ):
            service.execute(mission.mission_id)

        self.assertEqual(service.get(mission.mission_id).status, MissionStatus.COMPLETED)

    def test_completed_mission_cannot_be_executed_again(self) -> None:
        """Duplicate execution is rejected without corrupting final state."""
        service = self._service()
        mission = self._create(service)
        service.execute(mission.mission_id)

        with self.assertRaises(ValueError):
            service.execute(mission.mission_id)

        self.assertEqual(
            service.get(mission.mission_id).status,
            MissionStatus.COMPLETED,
        )

    def _service(self) -> MissionService:
        return MissionService(
            self.repository,
            output_directory=self.output_directory,
            mission_id_factory=lambda: "mission-1",
            clock=fixed_time,
        )

    def _create(self, service: MissionService) -> Mission:
        return service.create(
            prompt="AI Agents",
            platform=MissionPlatform.YOUTUBE,
            duration=30,
            render_model="gen4.5",
        )


class MissionAPITestCase(unittest.TestCase):
    """Verify Mission API contracts and gallery integration."""

    def setUp(self) -> None:
        """Create an isolated API with one local mission repository."""
        self.temporary_directory = TemporaryDirectory()
        output_directory = Path(self.temporary_directory.name)
        self.repository = MissionRepository()

        def service_factory(repository: MissionRepository) -> MissionService:
            return MissionService(
                repository,
                output_directory=output_directory,
                mission_id_factory=lambda: "api-mission-1",
                clock=fixed_time,
            )

        self.client = TestClient(
            create_app(
                scanner_factory=lambda: MediaStorageScanner(output_directory),
                mission_repository=self.repository,
                mission_service_factory=service_factory,
            ),
        )

    def tearDown(self) -> None:
        """Remove generated mission files."""
        self.temporary_directory.cleanup()

    def test_post_get_list_and_gallery_lifecycle(self) -> None:
        """A POST queues work that completes and appears in the gallery."""
        response = self.client.post(
            "/api/missions",
            json={
                "prompt": "AI Agents",
                "platform": "TikTok",
                "duration": 30,
                "render_model": "gen4.5",
            },
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "QUEUED")
        mission = self.client.get("/api/missions/api-mission-1")
        missions = self.client.get("/api/missions")
        videos = self.client.get("/api/videos")
        self.assertEqual(mission.status_code, 200)
        self.assertEqual(mission.json()["status"], "COMPLETED")
        self.assertEqual(mission.json()["platform"], "TikTok")
        self.assertEqual(len(mission.json()["pipeline_state"]["completed_task_ids"]), 12)
        self.assertEqual(len(missions.json()), 1)
        self.assertEqual(videos.json()[0]["id"], mission.json()["video_id"])

    def test_invalid_requests_return_422(self) -> None:
        """Prompt, platform, and duration are validated before queueing."""
        invalid_payloads = (
            {"prompt": " ", "platform": "YouTube", "duration": 30},
            {"prompt": "AI", "platform": "Unknown", "duration": 30},
            {"prompt": "AI", "platform": "YouTube", "duration": 20},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.client.post("/api/missions", json=payload)
                self.assertEqual(response.status_code, 422)

    def test_unknown_mission_returns_404(self) -> None:
        """Unknown mission IDs return a controlled public error."""
        response = self.client.get("/api/missions/missing")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Mission not found."})


if __name__ == "__main__":
    unittest.main()
