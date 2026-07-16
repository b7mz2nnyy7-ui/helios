"""Persistence and restart tests for local Mission Studio history."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from apps.api.app import create_app
from apps.api.mission_models import (
    Mission,
    MissionMediaAsset,
    MissionPipelineState,
    MissionPlatform,
    MissionStage,
    MissionStatus,
)
from apps.api.mission_repository import MissionRepository
from apps.api.mission_service import MissionService
from engine.media.scanner import MediaStorageScanner


_NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)


def persisted_mission(
    mission_id: str,
    created_at: datetime = _NOW,
) -> Mission:
    """Create a completed mission with its full media relationship."""
    return Mission(
        mission_id=mission_id,
        title="Persistent Mission",
        prompt="Build a durable production",
        platform=MissionPlatform.X,
        duration=30,
        render_model="gen4.5",
        status=MissionStatus.COMPLETED,
        created_at=created_at,
        updated_at=created_at,
        video_id="video-1",
        render_job_id="render-1",
        render_status="COMPLETED",
        pipeline_state=MissionPipelineState(
            current_stage=MissionStage.COMPLETED,
            completed_stages=(
                MissionStage.RESEARCH,
                MissionStage.SCRIPT,
                MissionStage.STORYBOARD,
                MissionStage.RENDERING,
                MissionStage.DOWNLOAD,
            ),
            completed_task_ids=("task-1", "task-2"),
        ),
        media_asset=MissionMediaAsset(
            asset_id="asset-1",
            asset_type="VIDEO",
            name="Persistent Video",
            description="Local mock render",
            provider="mock-video",
            format="mp4",
            metadata={"scene_count": 4, "nested": {"safe": True}},
        ),
    )


class MissionPersistenceTestCase(unittest.TestCase):
    """Verify durable mission storage and restart reconstruction."""

    def setUp(self) -> None:
        """Create an isolated JSON repository path."""
        self.temporary_directory = TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.repository_path = self.directory / "missions" / "missions.json"

    def tearDown(self) -> None:
        """Remove persistent test files."""
        self.temporary_directory.cleanup()

    def test_repository_survives_restart_with_full_relationship(self) -> None:
        """Mission, render, video, and asset references survive reload."""
        first_repository = MissionRepository(self.repository_path)
        first_repository.register(persisted_mission("mission-1"))

        second_repository = MissionRepository(self.repository_path)
        restored = second_repository.get("mission-1")

        self.assertEqual(restored.render_job_id, "render-1")
        self.assertEqual(restored.render_status, "COMPLETED")
        self.assertEqual(restored.video_id, "video-1")
        self.assertIsNotNone(restored.media_asset)
        assert restored.media_asset is not None
        self.assertEqual(restored.media_asset.asset_id, "asset-1")
        self.assertEqual(restored.media_asset.provider, "mock-video")
        self.assertEqual(restored.media_asset.metadata["scene_count"], 4)

    def test_save_is_persisted_and_history_is_newest_first(self) -> None:
        """Updates and mission history retain deterministic ordering."""
        repository = MissionRepository(self.repository_path)
        older = persisted_mission("older", _NOW - timedelta(days=1))
        newer = persisted_mission("newer", _NOW)
        repository.register(older)
        repository.register(newer)
        repository.save(replace(older, title="Updated Mission"))

        restarted = MissionRepository(self.repository_path)
        self.assertEqual(
            [mission.mission_id for mission in restarted.all()],
            ["newer", "older"],
        )
        self.assertEqual(restarted.get("older").title, "Updated Mission")

    def test_asset_metadata_is_deeply_immutable_after_reload(self) -> None:
        """Persisted asset metadata cannot be mutated by API consumers."""
        repository = MissionRepository(self.repository_path)
        repository.register(persisted_mission("mission-1"))
        asset = MissionRepository(self.repository_path).get("mission-1").media_asset
        assert asset is not None

        with self.assertRaises(TypeError):
            asset.metadata["scene_count"] = 8  # type: ignore[index]
        nested = asset.metadata["nested"]
        with self.assertRaises(TypeError):
            nested["safe"] = False  # type: ignore[index]
        with self.assertRaises(FrozenInstanceError):
            asset.provider = "other"  # type: ignore[misc]

    def test_invalid_repository_data_is_rejected(self) -> None:
        """Malformed history never loads as partial mission state."""
        self.repository_path.parent.mkdir(parents=True)
        self.repository_path.write_text("not-json", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "invalid data"):
            MissionRepository(self.repository_path)

    def test_api_restart_retains_completed_mission_and_gallery_video(self) -> None:
        """A second API instance reconstructs mission detail and video mapping."""
        output_directory = self.directory / "videos"
        repository = MissionRepository(self.repository_path)

        def service_factory(selected: MissionRepository) -> MissionService:
            return MissionService(
                selected,
                output_directory=output_directory,
                mission_id_factory=lambda: "restart-mission",
                clock=lambda: _NOW,
            )

        first_client = TestClient(
            create_app(
                scanner_factory=lambda: MediaStorageScanner(output_directory),
                mission_repository=repository,
                mission_service_factory=service_factory,
            ),
        )
        first_client.post(
            "/api/missions",
            json={
                "prompt": "Persistent production",
                "platform": "YouTube",
                "duration": 30,
            },
        )

        restarted_repository = MissionRepository(self.repository_path)
        second_client = TestClient(
            create_app(
                scanner_factory=lambda: MediaStorageScanner(output_directory),
                mission_repository=restarted_repository,
                mission_service_factory=service_factory,
            ),
        )
        mission = second_client.get("/api/missions/restart-mission").json()
        videos = second_client.get("/api/videos").json()

        self.assertEqual(mission["status"], "COMPLETED")
        self.assertEqual(mission["render_status"], "COMPLETED")
        self.assertEqual(mission["media_asset"]["provider"], "mock-video")
        self.assertEqual(videos[0]["id"], mission["video_id"])


if __name__ == "__main__":
    unittest.main()
