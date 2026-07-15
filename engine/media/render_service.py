"""Synchronous orchestration for provider-neutral media rendering."""

from engine.media.asset import MediaAsset, MediaAssetType
from engine.media.providers.base import MediaProvider, MediaProviderError
from engine.media.providers.registry import MediaProviderRegistry
from engine.media.render_job import RenderJob, RenderJobStatus
from engine.media.storage import MediaStorage, StoredMediaAsset


class RenderService:
    """Render jobs through explicitly registered media providers."""

    def __init__(
        self,
        registry: MediaProviderRegistry,
        storage: MediaStorage | None = None,
        store_output: bool = False,
    ) -> None:
        """Create a render service for a provider registry."""
        if store_output and storage is None:
            msg = "storage is required when store_output is enabled."
            raise ValueError(msg)
        self.registry = registry
        self.storage = storage
        self.store_output = store_output
        self.last_stored_asset: StoredMediaAsset | None = None

    def render(
        self,
        job: RenderJob,
        provider_id: str | None = None,
    ) -> MediaAsset:
        """Render a pending job and complete its lifecycle synchronously."""
        self._validate_job(job)
        provider = self._select_provider(job, provider_id)
        self._validate_video_support(provider)
        self.last_stored_asset = None

        job.start()
        try:
            asset = provider.render(job)
            if not isinstance(asset, MediaAsset):
                msg = "media provider must return a MediaAsset."
                raise TypeError(msg)

            if asset.asset_type is not MediaAssetType.VIDEO:
                msg = "media provider must return a VIDEO asset."
                raise MediaProviderError(msg)

            if self.store_output:
                if self.storage is None:
                    msg = "storage is required when store_output is enabled."
                    raise RuntimeError(msg)
                stored_asset = self.storage.download_asset(asset)
                self._register_stored_asset(asset, stored_asset)
                self.last_stored_asset = stored_asset

            job.complete(asset)
            return asset
        except Exception as error:
            self._fail_job(job, error)
            raise

    def _validate_job(self, job: RenderJob) -> None:
        if not isinstance(job, RenderJob):
            msg = "job must be a RenderJob."
            raise ValueError(msg)

        if job.status is not RenderJobStatus.PENDING:
            msg = (
                "RenderService requires a PENDING render job; "
                f"received {job.status.value}."
            )
            raise ValueError(msg)

    def _select_provider(
        self,
        job: RenderJob,
        provider_id: str | None,
    ) -> MediaProvider:
        if provider_id is not None:
            return self.registry.get(provider_id)

        if not job.provider.strip():
            msg = "job.provider must not be empty when provider_id is omitted."
            raise ValueError(msg)

        return self.registry.get(job.provider)

    def _validate_video_support(self, provider: MediaProvider) -> None:
        if MediaAssetType.VIDEO not in provider.supported_asset_types:
            msg = f"Provider '{provider.provider_id}' does not support VIDEO assets."
            raise MediaProviderError(msg)

    def _fail_job(self, job: RenderJob, error: Exception) -> None:
        try:
            job.fail(str(error))
        except Exception:
            return

    def _register_stored_asset(
        self,
        asset: MediaAsset,
        stored_asset: StoredMediaAsset,
    ) -> None:
        asset.metadata.update(
            {
                "local_path": str(stored_asset.local_path),
                "size_bytes": stored_asset.size_bytes,
                "sha256": stored_asset.sha256,
                "mime_type": stored_asset.mime_type,
            },
        )
