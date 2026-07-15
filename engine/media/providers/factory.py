"""Configuration-aware access to registered media providers."""

from collections.abc import Mapping

from engine.media.providers.base import MediaProvider
from engine.media.providers.config import (
    ProviderConfig,
    ProviderConfigurationError,
)
from engine.media.providers.registry import MediaProviderRegistry


class ProviderFactory:
    """Resolve enabled provider adapters without registering them."""

    def __init__(
        self,
        registry: MediaProviderRegistry,
        configs: Mapping[str, ProviderConfig],
    ) -> None:
        """Create a factory from explicit registry and configuration state."""
        self._registry = registry
        self._configs = dict(configs)

    def get_config(self, provider_id: str) -> ProviderConfig:
        """Return the configuration for a provider ID."""
        return self._configs[provider_id]

    def is_enabled(self, provider_id: str) -> bool:
        """Return whether a configured provider is enabled."""
        return self.get_config(provider_id).enabled

    def get_provider(self, provider_id: str) -> MediaProvider:
        """Return an enabled provider already present in the registry."""
        config = self.get_config(provider_id)
        if not config.enabled:
            msg = f"Media provider '{provider_id}' is disabled."
            raise ProviderConfigurationError(msg)

        return self._registry.get(provider_id)
