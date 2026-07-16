"""FastAPI application exposing the local Helios content pipeline."""

from collections.abc import Callable

from fastapi import FastAPI, Header, HTTPException, Response, status
from fastapi.responses import StreamingResponse

from apps.api.models import (
    ContentPipelineRequest,
    ContentPipelineResponse,
    HealthResponse,
    VideoDetailResponse,
    VideoSummaryResponse,
)
from apps.api.service import ContentPipelineService
from apps.api.video_streaming import ByteRange, iter_file_range, parse_range_header
from engine.media.scanner import MediaStorageScanner, ScannedVideo

ServiceFactory = Callable[[], ContentPipelineService]
ScannerFactory = Callable[[], MediaStorageScanner]


def create_app(
    service_factory: ServiceFactory | None = None,
    scanner_factory: ScannerFactory | None = None,
) -> FastAPI:
    """Create the local Helios API with isolated per-request services."""
    selected_service_factory = service_factory or ContentPipelineService
    selected_scanner_factory = scanner_factory or MediaStorageScanner
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


app = create_app()
