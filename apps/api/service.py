"""Application service for executing the local content pipeline."""

from collections.abc import Callable

from apps.api.models import ContentPipelineRequest, ContentPipelineResponse
from engine.runtime.runtime import HeliosRuntime
from workflows.content_pipeline import ContentPipeline

PipelineFactory = Callable[[], ContentPipeline]


class ContentPipelineService:
    """Execute a fresh content pipeline and map its result to an API response."""

    def __init__(self, pipeline_factory: PipelineFactory | None = None) -> None:
        """Create a service with an optional pipeline factory for testing."""
        self._pipeline_factory = pipeline_factory or self._create_pipeline

    def execute(self, request: ContentPipelineRequest) -> ContentPipelineResponse:
        """Execute one isolated pipeline run for an API request."""
        pipeline = self._pipeline_factory()
        result = pipeline.run(
            request.query,
            language=request.language,
            target_age_range=request.target_age_range,
            target_duration_seconds=request.target_duration_seconds,
        )
        render_job = result.render_job
        return ContentPipelineResponse(
            status="COMPLETED",
            query=result.query,
            completed_task_ids=list(result.completed_task_ids),
            script_title=result.video_script.title,
            selected_hook=result.optimized_hook.selected_hook.text,
            storyboard_scene_count=len(result.storyboard.scenes),
            target_platform=render_job.plan.target_platform,
            total_duration_seconds=render_job.plan.total_duration_seconds,
            render_job_id=render_job.job_id,
            render_job_status=render_job.status.value,
            report_markdown=result.to_markdown(),
        )

    def _create_pipeline(self) -> ContentPipeline:
        return ContentPipeline(HeliosRuntime())
