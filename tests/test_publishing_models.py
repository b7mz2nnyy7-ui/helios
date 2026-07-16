"""Tests for provider-neutral publishing foundation models."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
import json
import unittest

from engine.publishing.models import (
    PlatformConnection,
    PublishingJob,
    PublishingTarget,
    UploadStatus,
    VideoMetadata,
)


_NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)


class PublishingModelsTestCase(unittest.TestCase):
    """Validate serialization, immutability, and secret-free contracts."""

    def test_targets_include_current_and_future_platforms(self) -> None:
        """All explicitly planned publishing targets remain represented."""
        self.assertEqual(
            [target.value for target in PublishingTarget],
            [
                "TikTok",
                "YouTube",
                "Instagram",
                "X",
                "LinkedIn",
                "Facebook",
                "Pinterest",
                "Snapchat",
            ],
        )

    def test_upload_status_contract(self) -> None:
        """Publishing lifecycle values match the provider-neutral contract."""
        self.assertEqual(
            [status.value for status in UploadStatus],
            [
                "QUEUED",
                "WAITING",
                "UPLOADING",
                "PUBLISHED",
                "FAILED",
                "CANCELLED",
            ],
        )

    def test_video_metadata_round_trip_and_immutability(self) -> None:
        """Metadata survives JSON serialization and protects collections."""
        metadata = VideoMetadata(
            title="Launch",
            description="A launch film",
            hashtags=("helios", "ai"),
            language="de",
            visibility="private",
            category="Technology",
            thumbnail=None,
            tags=("automation",),
            scheduled_at=_NOW,
        )
        restored = VideoMetadata.from_dict(
            json.loads(json.dumps(metadata.to_dict())),
        )

        self.assertEqual(restored, metadata)
        self.assertIsInstance(restored.hashtags, tuple)
        with self.assertRaises(FrozenInstanceError):
            restored.title = "Changed"  # type: ignore[misc]

    def test_connection_round_trip_contains_no_token_fields(self) -> None:
        """Platform connections serialize without credentials or secrets."""
        connection = PlatformConnection(
            connection_id="connection-1",
            platform=PublishingTarget.YOUTUBE,
            display_name="Helios Channel",
            connected=False,
            created_at=_NOW,
            last_validated_at=None,
        )
        payload = connection.to_dict()
        restored = PlatformConnection.from_dict(
            json.loads(json.dumps(payload)),
        )

        self.assertEqual(restored, connection)
        serialized = json.dumps(payload).lower()
        self.assertNotIn("token", serialized)
        self.assertNotIn("secret", serialized)
        self.assertNotIn("api_key", serialized)

    def test_publishing_job_round_trip(self) -> None:
        """Publishing jobs retain target, status, and UTC timestamps."""
        job = PublishingJob(
            mission_id="mission-1",
            target=PublishingTarget.TIKTOK,
            status=UploadStatus.WAITING,
            created_at=_NOW,
            scheduled_at=_NOW,
        )
        restored = PublishingJob.from_dict(
            json.loads(json.dumps(job.to_dict())),
        )

        self.assertEqual(restored, job)
        self.assertIs(restored.created_at.tzinfo, UTC)

    def test_required_values_and_utc_are_validated(self) -> None:
        """Invalid publication models fail before any provider interaction."""
        with self.assertRaises(ValueError):
            VideoMetadata(
                title="",
                description="Description",
                hashtags=(),
                language="de",
                visibility="private",
                category="Technology",
                tags=(),
            )
        with self.assertRaises(ValueError):
            PlatformConnection(
                connection_id="connection-1",
                platform=PublishingTarget.X,
                display_name="Account",
                connected=False,
                created_at=datetime(2026, 7, 16, 12, 0),
            )


if __name__ == "__main__":
    unittest.main()
