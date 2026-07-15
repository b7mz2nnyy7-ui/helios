"""Base contracts for provider-neutral media rendering."""

from abc import ABC, abstractmethod

from engine.media.asset import MediaAsset, MediaAssetType
from engine.media.render_job import RenderJob, RenderJobStatus


class MediaProviderError(Exception):
    """Raised when a media provider cannot render an asset."""


class MediaProvider(ABC):
    """Base adapter for rendering validated jobs into media assets."""

    provider_id: str
    supported_asset_types: tuple[MediaAssetType, ...]

    def __init__(
        self,
        provider_id: str,
        supported_asset_types: tuple[MediaAssetType, ...],
    ) -> None:
        """Create a provider with a unique ID and supported asset types."""
        if not provider_id.strip():
            msg = "provider_id must not be empty."
            raise ValueError(msg)

        self.provider_id = provider_id
        self.supported_asset_types = supported_asset_types

    def render(self, job: RenderJob) -> MediaAsset:
        """Validate and render a video job without mutating it."""
        allowed_statuses = {RenderJobStatus.PENDING, RenderJobStatus.RUNNING}
        if job.status not in allowed_statuses:
            msg = (
                f"Provider '{self.provider_id}' requires a PENDING or RUNNING "
                f"render job; received {job.status.value}."
            )
            raise MediaProviderError(msg)

        if MediaAssetType.VIDEO not in self.supported_asset_types:
            msg = f"Provider '{self.provider_id}' does not support VIDEO assets."
            raise MediaProviderError(msg)

        try:
            asset = self._render(job)
            if not isinstance(asset, MediaAsset):
                msg = "provider render implementation must return a MediaAsset."
                raise TypeError(msg)
        except MediaProviderError:
            raise
        except Exception as error:
            msg = f"Provider '{self.provider_id}' failed to render job '{job.job_id}'."
            raise MediaProviderError(msg) from error

        return asset

    @abstractmethod
    def _render(self, job: RenderJob) -> MediaAsset:
        """Render a validated job in a concrete provider adapter."""
