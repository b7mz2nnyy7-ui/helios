"""Transport-injected client contract for the Runway API."""

from typing import Protocol

from engine.media.providers.base import MediaProviderError
from engine.media.providers.config import (
    ProviderConfig,
    ProviderConfigurationError,
    require_api_key,
)
from integrations.runway.models import RunwayGenerationRequest, RunwayTask

RUNWAY_DEFAULT_BASE_URL = "https://api.dev.runwayml.com/v1"


class RunwayTransport(Protocol):
    """Transport boundary for Runway task creation and retrieval."""

    def create_video(
        self,
        request: RunwayGenerationRequest,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
    ) -> RunwayTask:
        """Create one video generation task."""

    def get_task(
        self,
        task_id: str,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
    ) -> RunwayTask:
        """Return one existing generation task."""


class RunwayClient:
    """Secret-safe Runway client using an injected transport."""

    def __init__(
        self,
        config: ProviderConfig,
        transport: RunwayTransport,
    ) -> None:
        """Create a client from enabled configuration and a transport."""
        if not config.enabled:
            msg = f"Media provider '{config.provider_id}' is disabled."
            raise ProviderConfigurationError(msg)

        self.config = config
        self.transport = transport
        self._api_key = require_api_key(config)
        self.base_url = config.base_url or RUNWAY_DEFAULT_BASE_URL

    def create_video(self, request: RunwayGenerationRequest) -> RunwayTask:
        """Create one Runway task and wrap transport failures."""
        try:
            task = self.transport.create_video(
                request,
                self._api_key,
                self.base_url,
                self.config.timeout_seconds,
            )
            return self._validate_task(task)
        except MediaProviderError:
            raise
        except Exception as error:
            msg = "Runway transport failed while creating a video task."
            raise MediaProviderError(msg) from error

    def get_task(self, task_id: str) -> RunwayTask:
        """Retrieve one Runway task and wrap transport failures."""
        if not task_id.strip():
            msg = "task_id must not be empty."
            raise ValueError(msg)

        try:
            task = self.transport.get_task(
                task_id,
                self._api_key,
                self.base_url,
                self.config.timeout_seconds,
            )
            return self._validate_task(task)
        except MediaProviderError:
            raise
        except Exception as error:
            msg = "Runway transport failed while retrieving a task."
            raise MediaProviderError(msg) from error

    def _validate_task(self, task: RunwayTask) -> RunwayTask:
        if not isinstance(task, RunwayTask):
            msg = "Runway transport must return a RunwayTask."
            raise TypeError(msg)

        return task
