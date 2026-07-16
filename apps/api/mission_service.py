"""Local application service for Mission Studio production runs."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import struct
from uuid import uuid4

from apps.api.mission_models import (
    Mission,
    MissionMediaAsset,
    MissionPipelineState,
    MissionPlatform,
    MissionStage,
    MissionStatus,
)
from apps.api.mission_repository import MissionRepository
from engine.media.asset import MediaAsset
from engine.media.providers.mock_provider import MockVideoProvider
from engine.media.providers.registry import MediaProviderRegistry
from engine.media.render_service import RenderService
from engine.media.storage import DEFAULT_MEDIA_OUTPUT_DIRECTORY
from engine.runtime.runtime import HeliosRuntime
from workflows.content_pipeline import ContentPipeline
from workflows.models import ContentPipelineResult

MissionIdFactory = Callable[[], str]
Clock = Callable[[], datetime]
TaskIdGenerator = Callable[[str], str]
PipelineFactory = Callable[[TaskIdGenerator], ContentPipeline]
RenderServiceFactory = Callable[[], RenderService]

_PIPELINE_STAGE_BY_STEP = {
    "trend_research": MissionStage.RESEARCH,
    "audience_research": MissionStage.RESEARCH,
    "knowledge": MissionStage.RESEARCH,
    "strategy": MissionStage.SCRIPT,
    "script": MissionStage.SCRIPT,
    "hook": MissionStage.SCRIPT,
    "storyboard": MissionStage.STORYBOARD,
    "creative_director": MissionStage.STORYBOARD,
    "avatar": MissionStage.STORYBOARD,
    "voice": MissionStage.STORYBOARD,
    "music": MissionStage.STORYBOARD,
    "video_production": MissionStage.STORYBOARD,
}
_STAGE_ORDER = (
    MissionStage.RESEARCH,
    MissionStage.SCRIPT,
    MissionStage.STORYBOARD,
    MissionStage.RENDERING,
    MissionStage.DOWNLOAD,
    MissionStage.COMPLETED,
)


class MissionService:
    """Create and execute local missions through the existing pipeline."""

    def __init__(
        self,
        repository: MissionRepository,
        *,
        output_directory: Path = DEFAULT_MEDIA_OUTPUT_DIRECTORY,
        pipeline_factory: PipelineFactory | None = None,
        render_service_factory: RenderServiceFactory | None = None,
        mission_id_factory: MissionIdFactory = lambda: uuid4().hex,
        clock: Clock = lambda: datetime.now(UTC),
    ) -> None:
        """Create a mission service with injectable deterministic edges."""
        self.repository = repository
        self.output_directory = output_directory
        self._pipeline_factory = pipeline_factory or self._create_pipeline
        self._render_service_factory = (
            render_service_factory or self._create_render_service
        )
        self._mission_id_factory = mission_id_factory
        self._clock = clock

    def create(
        self,
        *,
        prompt: str,
        platform: MissionPlatform,
        duration: int,
        render_model: str,
    ) -> Mission:
        """Create and queue one mission without executing it inline."""
        clean_prompt = _required_text(prompt, "prompt")
        clean_model = _required_text(render_model, "render_model")
        mission_id = _safe_mission_id(self._mission_id_factory())
        timestamp = self._clock()
        mission = Mission(
            mission_id=mission_id,
            title=_mission_title(clean_prompt),
            prompt=clean_prompt,
            platform=platform,
            duration=duration,
            render_model=clean_model,
            status=MissionStatus.QUEUED,
            created_at=timestamp,
            updated_at=timestamp,
            pipeline_state=MissionPipelineState(MissionStage.RESEARCH),
        )
        self.repository.register(mission)
        return mission

    def execute(self, mission_id: str) -> None:
        """Run one queued mission and persist each observable stage."""
        mission = self.repository.get(mission_id)
        if mission.status is not MissionStatus.QUEUED:
            msg = "Only QUEUED missions can be executed."
            raise ValueError(msg)
        try:
            self._execute(mission_id)
        except Exception:
            mission = self.repository.get(mission_id)
            self.repository.save(
                replace(
                    mission,
                    status=MissionStatus.FAILED,
                    render_status=(
                        "FAILED"
                        if mission.render_job_id is not None
                        else mission.render_status
                    ),
                    error_message="Mission execution failed.",
                    updated_at=self._clock(),
                ),
            )

    def get(self, mission_id: str) -> Mission:
        """Return one local mission."""
        return self.repository.get(mission_id)

    def all(self) -> list[Mission]:
        """Return all local missions newest first."""
        return self.repository.all()

    def _execute(self, mission_id: str) -> None:
        mission = self.repository.get(mission_id)
        self.repository.save(
            replace(
                mission,
                updated_at=self._clock(),
                status=MissionStatus.RUNNING,
                error_message=None,
                pipeline_state=MissionPipelineState(MissionStage.RESEARCH),
            ),
        )

        def generate_task_id(step: str) -> str:
            self._advance_pipeline(mission_id, _PIPELINE_STAGE_BY_STEP[step])
            return f"mission-{mission_id}-{step}"

        pipeline = self._pipeline_factory(generate_task_id)
        result = pipeline.run(
            mission.prompt,
            target_duration_seconds=float(mission.duration),
        )
        result.render_job.plan.target_platform = mission.platform.value
        current = self.repository.get(mission_id)
        self.repository.save(
            replace(
                current,
                updated_at=self._clock(),
                render_job_id=result.render_job.job_id,
                render_status=result.render_job.status.value,
                pipeline_state=MissionPipelineState(
                    current_stage=MissionStage.RENDERING,
                    completed_stages=_completed_before(MissionStage.RENDERING),
                    completed_task_ids=tuple(result.completed_task_ids),
                ),
            ),
        )

        asset = self._render_service_factory().render(
            result.render_job,
            provider_id="mock-video",
        )
        current = self.repository.get(mission_id)
        asset_snapshot = MissionMediaAsset(
            asset_id=asset.asset_id,
            asset_type=asset.asset_type.value,
            name=asset.name,
            description=asset.description,
            provider=asset.provider,
            format=asset.format,
            metadata=asset.metadata,
        )
        self.repository.save(
            replace(
                current,
                updated_at=self._clock(),
                render_status=result.render_job.status.value,
                media_asset=asset_snapshot,
                pipeline_state=MissionPipelineState(
                    current_stage=MissionStage.DOWNLOAD,
                    completed_stages=_completed_before(MissionStage.DOWNLOAD),
                    completed_task_ids=tuple(result.completed_task_ids),
                ),
            ),
        )
        video_id = self._publish_local_video(mission, result, asset)
        current = self.repository.get(mission_id)
        self.repository.save(
            replace(
                current,
                updated_at=self._clock(),
                status=MissionStatus.COMPLETED,
                video_id=video_id,
                pipeline_state=MissionPipelineState(
                    current_stage=MissionStage.COMPLETED,
                    completed_stages=_completed_before(MissionStage.COMPLETED),
                    completed_task_ids=tuple(result.completed_task_ids),
                ),
            ),
        )

    def _advance_pipeline(
        self,
        mission_id: str,
        stage: MissionStage,
    ) -> None:
        mission = self.repository.get(mission_id)
        if mission.pipeline_state.current_stage is stage:
            return
        self.repository.save(
            replace(
                mission,
                updated_at=self._clock(),
                pipeline_state=MissionPipelineState(
                    current_stage=stage,
                    completed_stages=_completed_before(stage),
                ),
            ),
        )

    def _create_pipeline(self, task_id_generator: TaskIdGenerator) -> ContentPipeline:
        return ContentPipeline(
            HeliosRuntime(),
            task_id_generator=task_id_generator,
        )

    def _create_render_service(self) -> RenderService:
        registry = MediaProviderRegistry()
        registry.register(MockVideoProvider())
        return RenderService(registry)

    def _publish_local_video(
        self,
        mission: Mission,
        result: ContentPipelineResult,
        asset: MediaAsset,
    ) -> str:
        self.output_directory.mkdir(parents=True, exist_ok=True)
        filename = f"mission-{mission.mission_id}.mp4"
        video_path = self.output_directory / filename
        sidecar_path = video_path.with_suffix(".json")
        if video_path.exists() or sidecar_path.exists():
            msg = "Mission output already exists."
            raise FileExistsError(msg)
        metadata = {
            "mission_id": mission.mission_id,
            "render_job_id": result.render_job.job_id,
            "provider": asset.provider,
            "model": mission.render_model,
            "target_platform": mission.platform.value,
            "total_duration_seconds": float(mission.duration),
        }
        try:
            video_path.write_bytes(_mock_mp4_bytes(float(mission.duration)))
            sidecar_path.write_text(
                json.dumps(metadata, sort_keys=True),
                encoding="utf-8",
            )
        except Exception:
            video_path.unlink(missing_ok=True)
            sidecar_path.unlink(missing_ok=True)
            raise
        return sha256(filename.encode("utf-8")).hexdigest()[:16]


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        msg = f"{field_name} must be a non-empty string."
        raise ValueError(msg)
    return value.strip()


def _safe_mission_id(value: object) -> str:
    mission_id = _required_text(value, "mission_id")
    if re.fullmatch(r"[A-Za-z0-9_-]+", mission_id) is None:
        msg = "mission_id contains unsupported characters."
        raise ValueError(msg)
    return mission_id


def _mission_title(prompt: str) -> str:
    first_line = prompt.splitlines()[0].strip()
    return first_line[:72]


def _completed_before(stage: MissionStage) -> tuple[MissionStage, ...]:
    index = _STAGE_ORDER.index(stage)
    return _STAGE_ORDER[:index]


def _mock_mp4_bytes(duration_seconds: float) -> bytes:
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
