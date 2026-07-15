"""Runway video provider adapter with optional controlled polling."""

from engine.media.asset import MediaAsset, MediaAssetType
from engine.media.providers.base import MediaProvider, MediaProviderError
from engine.media.providers.config import ProviderConfigurationError
from engine.media.render_job import RenderJob
from engine.media.render_plan import VideoProductionPlan
from integrations.runway.client import RunwayClient
from integrations.runway.models import (
    RunwayGenerationMode,
    RunwayGenerationRequest,
    RunwayTask,
    normalize_runway_duration,
)
from integrations.runway.polling import RunwayPollingResult, RunwayTaskPoller

RUNWAY_VERTICAL_RATIO = "720:1280"
_SUCCESS_STATUSES = {"SUCCEEDED"}
_POLLING_STATUSES = {"PENDING", "THROTTLED", "RUNNING"}
_FAILURE_STATUSES = {"FAILED", "CANCELED", "CANCELLED"}


class RunwayVideoProvider(MediaProvider):
    """Create video assets from immediate or polled Runway tasks."""

    def __init__(
        self,
        client: RunwayClient,
        poller: RunwayTaskPoller | None = None,
    ) -> None:
        """Create a Runway provider with optional controlled polling."""
        super().__init__(
            provider_id="runway",
            supported_asset_types=(MediaAssetType.VIDEO,),
        )
        self.client = client
        self.poller = poller

    def _render(self, job: RenderJob) -> MediaAsset:
        """Create one task, poll when required, and map a video asset."""
        request = self._create_request(job.plan)
        created_task = self.client.create_video(request)
        polling_result = self._resolve_task(created_task)
        task = polling_result.task
        self._validate_succeeded_task(task)
        output_url = task.output_urls[0]
        plan = job.plan
        return MediaAsset(
            asset_id=f"asset-runway-{task.task_id}",
            asset_type=MediaAssetType.VIDEO,
            name=plan.title,
            description=plan.summary,
            provider=self.provider_id,
            format="mp4",
            metadata={
                "runway_task_id": task.task_id,
                "output_url": output_url,
                "output_url_is_temporary": True,
                "plan_id": plan.plan_id,
                "render_job_id": job.job_id,
                "target_platform": plan.target_platform,
                "total_duration_seconds": plan.total_duration_seconds,
                "scene_count": len(plan.scenes),
                "model": request.model,
                "poll_count": polling_result.poll_count,
                "polling_elapsed_seconds": polling_result.elapsed_seconds,
            },
        )

    def _resolve_task(self, task: RunwayTask) -> RunwayPollingResult:
        status = task.status.strip().upper()
        if status in _SUCCESS_STATUSES:
            return RunwayPollingResult(
                task=task,
                poll_count=0,
                elapsed_seconds=0.0,
            )

        if status in _POLLING_STATUSES:
            if self.poller is None:
                msg = (
                    f"Runway task '{task.task_id}' requires polling for status "
                    f"'{status}', but no poller is configured."
                )
                raise MediaProviderError(msg)
            return self.poller.wait_for_completion(task.task_id)

        if status in _FAILURE_STATUSES:
            msg = f"Runway task '{task.task_id}' ended with status '{status}'."
            raise MediaProviderError(msg)

        msg = f"Runway task '{task.task_id}' returned unknown status '{status}'."
        raise MediaProviderError(msg)

    def _create_request(
        self,
        plan: VideoProductionPlan,
    ) -> RunwayGenerationRequest:
        model = self.client.config.model
        if model is None:
            msg = "Runway media provider requires a configured model."
            raise ProviderConfigurationError(msg)

        return RunwayGenerationRequest(
            model=model,
            prompt_text=build_runway_prompt(plan),
            ratio=RUNWAY_VERTICAL_RATIO,
            duration_seconds=normalize_runway_duration(
                model,
                plan.total_duration_seconds,
            ),
            seed=None,
            mode=RunwayGenerationMode.TEXT_TO_VIDEO,
        )

    def _validate_succeeded_task(self, task: RunwayTask) -> None:
        normalized_status = task.status.strip().upper()
        if normalized_status not in _SUCCESS_STATUSES:
            msg = (
                f"Runway task '{task.task_id}' did not succeed; "
                f"received status '{task.status}'."
            )
            raise MediaProviderError(msg)

        if len(task.output_urls) != 1:
            msg = (
                f"Runway task '{task.task_id}' must provide exactly one output URL."
            )
            raise MediaProviderError(msg)


def build_runway_prompt(plan: VideoProductionPlan) -> str:
    """Create a deterministic Runway prompt from a video production plan."""
    scene_blocks = "\n\n".join(
        (
            f"Scene {scene.scene_number}\n"
            f"Duration: {scene.duration_seconds}s\n"
            f"Camera: {scene.camera_instruction}\n"
            f"Visual: {scene.visual_instruction}\n"
            f"Voice: {scene.voice_instruction}\n"
            f"Music: {scene.music_instruction}\n"
            f"Transition: {scene.transition}"
        )
        for scene in plan.scenes
    )
    return (
        f"Plan Title: {plan.title}\n"
        f"Target Platform: {plan.target_platform}\n"
        f"Summary: {plan.summary}\n\n"
        f"{scene_blocks}"
    )
