"""FastAPI application exposing the local Helios content pipeline."""

from collections.abc import Callable

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Response, status
from fastapi.responses import PlainTextResponse, StreamingResponse

from apps.api.models import (
    ContentPipelineRequest,
    ContentPipelineResponse,
    HealthResponse,
    MissionCreateRequest,
    MissionMediaAssetResponse,
    MissionPipelineStateResponse,
    MissionResponse,
    SystemHealthResponse,
    VideoDetailResponse,
    VideoSummaryResponse,
)
from apps.api.mission_models import Mission
from apps.api.mission_repository import (
    DEFAULT_MISSION_REPOSITORY_PATH,
    MissionRepository,
)
from apps.api.mission_service import MissionService
from apps.api.service import ContentPipelineService
from apps.api.video_streaming import ByteRange, iter_file_range, parse_range_header
from engine.guardian.guardian import ArgusGuardian, create_guardian
from engine.media.scanner import MediaStorageScanner, ScannedVideo

ServiceFactory = Callable[[], ContentPipelineService]
ScannerFactory = Callable[[], MediaStorageScanner]
GuardianFactory = Callable[[], ArgusGuardian]
MissionServiceFactory = Callable[[MissionRepository], MissionService]


def create_app(
    service_factory: ServiceFactory | None = None,
    scanner_factory: ScannerFactory | None = None,
    guardian_factory: GuardianFactory | None = None,
    mission_repository: MissionRepository | None = None,
    mission_service_factory: MissionServiceFactory | None = None,
) -> FastAPI:
    """Create the local Helios API with isolated per-request services."""
    selected_service_factory = service_factory or ContentPipelineService
    selected_scanner_factory = scanner_factory or MediaStorageScanner
    selected_guardian_factory = guardian_factory or create_guardian
    selected_mission_repository = (
        mission_repository
        if mission_repository is not None
        else MissionRepository(DEFAULT_MISSION_REPOSITORY_PATH)
    )
    selected_mission_service_factory = mission_service_factory or MissionService
    mission_service = selected_mission_service_factory(selected_mission_repository)
    api = FastAPI(title="Helios Local API", version="1.0.0")

    @api.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Return the local API health status."""
        return HealthResponse(status="ok")

    @api.post(
        "/api/v1/content-pipeline",
        response_model=ContentPipelineResponse,
    )
    def run_content_pipeline(
        request: ContentPipelineRequest,
    ) -> ContentPipelineResponse:
        """Execute the deterministic content pipeline for one request."""
        try:
            return selected_service_factory().execute(request)
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Content pipeline execution failed.",
            ) from error

    @api.get("/api/videos", response_model=list[VideoSummaryResponse])
    def list_videos() -> list[VideoSummaryResponse]:
        """List all locally stored videos, newest first."""
        return [
            _video_summary(video)
            for video in selected_scanner_factory().scan()
        ]

    @api.post(
        "/api/missions",
        response_model=MissionResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def create_mission(
        request: MissionCreateRequest,
        background_tasks: BackgroundTasks,
    ) -> MissionResponse:
        """Queue one mission and execute it after returning the response."""
        mission = mission_service.create(
            prompt=request.prompt,
            platform=request.platform,
            duration=request.duration,
            render_model=request.render_model,
        )
        background_tasks.add_task(mission_service.execute, mission.mission_id)
        return _mission_response(mission)

    @api.get("/api/missions", response_model=list[MissionResponse])
    def list_missions() -> list[MissionResponse]:
        """Return all locally known missions newest first."""
        return [_mission_response(mission) for mission in mission_service.all()]

    @api.get("/api/missions/{mission_id}", response_model=MissionResponse)
    def get_mission(mission_id: str) -> MissionResponse:
        """Return one mission or a controlled 404 response."""
        try:
            mission = mission_service.get(mission_id)
        except KeyError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mission not found.",
            ) from error
        return _mission_response(mission)

    @api.get("/api/videos/{video_id}", response_model=VideoDetailResponse)
    def get_video(video_id: str) -> VideoDetailResponse:
        """Return complete public metadata for one local video."""
        return _video_detail(_find_video(selected_scanner_factory(), video_id))

    @api.get("/api/videos/{video_id}/stream")
    def stream_video(
        video_id: str,
        range_header: str | None = Header(default=None, alias="Range"),
    ) -> Response:
        """Stream one local MP4 with optional single-range support."""
        video = _find_video(selected_scanner_factory(), video_id)
        full_range = ByteRange(0, video.size_bytes - 1)
        selected_range = full_range
        response_status = status.HTTP_200_OK
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(video.size_bytes),
        }
        if range_header is not None:
            try:
                selected_range = parse_range_header(
                    range_header,
                    video.size_bytes,
                )
            except ValueError:
                return Response(
                    status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                    headers={
                        "Accept-Ranges": "bytes",
                        "Content-Range": f"bytes */{video.size_bytes}",
                    },
                )
            response_status = status.HTTP_206_PARTIAL_CONTENT
            headers["Content-Length"] = str(selected_range.length)
            headers["Content-Range"] = (
                f"bytes {selected_range.start}-{selected_range.end}/"
                f"{video.size_bytes}"
            )
        return StreamingResponse(
            iter_file_range(video.path, selected_range),
            status_code=response_status,
            media_type="video/mp4",
            headers=headers,
        )

    @api.get("/api/system/health", response_model=SystemHealthResponse)
    def system_health() -> SystemHealthResponse:
        """Return a fresh structured ARGUS health report."""
        report = selected_guardian_factory().inspect()
        return SystemHealthResponse.model_validate_json(report.to_json())

    @api.get("/api/system/report", response_class=PlainTextResponse)
    def system_report() -> PlainTextResponse:
        """Return a fresh ARGUS report as Markdown."""
        report = selected_guardian_factory().inspect()
        return PlainTextResponse(report.to_markdown(), media_type="text/markdown")

    return api


def _find_video(scanner: MediaStorageScanner, video_id: str) -> ScannedVideo:
    for video in scanner.scan():
        if video.video_id == video_id:
            return video
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Video not found.",
    )


def _video_summary(video: ScannedVideo) -> VideoSummaryResponse:
    return VideoSummaryResponse(
        id=video.video_id,
        filename=video.filename,
        created_at=video.created_at,
        duration=video.duration,
        size_bytes=video.size_bytes,
        sha256=video.sha256,
        model=video.model,
    )


def _video_detail(video: ScannedVideo) -> VideoDetailResponse:
    return VideoDetailResponse(
        **_video_summary(video).model_dump(),
        mime_type=video.mime_type,
        metadata=dict(video.metadata),
    )


def _mission_response(mission: Mission) -> MissionResponse:
    state = mission.pipeline_state
    return MissionResponse(
        id=mission.mission_id,
        title=mission.title,
        prompt=mission.prompt,
        platform=mission.platform.value,
        duration=mission.duration,
        render_model=mission.render_model,
        status=mission.status.value,
        created_at=mission.created_at,
        updated_at=mission.updated_at,
        video_id=mission.video_id,
        render_job_id=mission.render_job_id,
        render_status=mission.render_status,
        media_asset=(
            None
            if mission.media_asset is None
            else MissionMediaAssetResponse(
                asset_id=mission.media_asset.asset_id,
                asset_type=mission.media_asset.asset_type,
                name=mission.media_asset.name,
                description=mission.media_asset.description,
                provider=mission.media_asset.provider,
                format=mission.media_asset.format,
                metadata=dict(mission.media_asset.metadata),
            )
        ),
        pipeline_state=MissionPipelineStateResponse(
            current_stage=state.current_stage.value,
            completed_stages=[stage.value for stage in state.completed_stages],
            completed_task_ids=list(state.completed_task_ids),
        ),
        error_message=mission.error_message,
    )


app = create_app()
