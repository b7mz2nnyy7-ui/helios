"""Registry for media provider adapters."""

from engine.media.asset import MediaAssetType
from engine.media.providers.base import MediaProvider


class MediaProviderRegistry:
    """Store media providers by their unique provider ID."""

    def __init__(self) -> None:
        """Create an empty provider registry."""
        self._providers: dict[str, MediaProvider] = {}

    def register(self, provider: MediaProvider) -> None:
        """Register a provider with a unique provider ID."""
        if provider.provider_id in self._providers:
            msg = (
                f"Media provider with ID '{provider.provider_id}' "
                "is already registered."
            )
            raise ValueError(msg)

        self._providers[provider.provider_id] = provider

    def unregister(self, provider_id: str) -> None:
        """Remove a provider by ID.

        Raises:
            KeyError: If the provider ID is unknown.
        """
        del self._providers[provider_id]

    def get(self, provider_id: str) -> MediaProvider:
        """Return a provider by ID.

        Raises:
            KeyError: If the provider ID is unknown.
        """
        return self._providers[provider_id]

    def all(self) -> list[MediaProvider]:
        """Return a copy of all providers in registration order."""
        return list(self._providers.values())

    def supports(self, provider_id: str, asset_type: MediaAssetType) -> bool:
        """Return whether a provider supports an asset type."""
        provider = self.get(provider_id)
        return asset_type in provider.supported_asset_types
