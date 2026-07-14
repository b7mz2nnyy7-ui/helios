"""FastAPI application exposing the local Helios content pipeline."""

from collections.abc import Callable

from fastapi import FastAPI, HTTPException, status

from apps.api.models import (
    ContentPipelineRequest,
    ContentPipelineResponse,
    HealthResponse,
)
from apps.api.service import ContentPipelineService

ServiceFactory = Callable[[], ContentPipelineService]


def create_app(service_factory: ServiceFactory | None = None) -> FastAPI:
    """Create the local Helios API with isolated per-request services."""
    selected_service_factory = service_factory or ContentPipelineService
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

    return api


app = create_app()
