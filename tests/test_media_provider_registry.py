"""Tests for the media provider registry."""

import unittest

from engine.media.asset import MediaAssetType
from engine.media.providers.mock_provider import MockVideoProvider
from engine.media.providers.registry import MediaProviderRegistry


class MediaProviderRegistryTestCase(unittest.TestCase):
    """Tests for isolated media provider registration."""

    def test_register_and_get_provider(self) -> None:
        """A registered provider can be retrieved by ID."""
        registry = MediaProviderRegistry()
        provider = MockVideoProvider()

        registry.register(provider)

        self.assertIs(registry.get("mock-video"), provider)

    def test_unregister_provider(self) -> None:
        """A provider can be removed by ID."""
        registry = MediaProviderRegistry()
        registry.register(MockVideoProvider())

        registry.unregister("mock-video")

        with self.assertRaises(KeyError):
            registry.get("mock-video")

    def test_duplicate_provider_id_is_rejected(self) -> None:
        """Duplicate provider IDs raise ValueError."""
        registry = MediaProviderRegistry()
        registry.register(MockVideoProvider())

        with self.assertRaisesRegex(ValueError, "mock-video"):
            registry.register(MockVideoProvider())

    def test_unknown_provider_id_raises_key_error(self) -> None:
        """Unknown provider IDs raise KeyError."""
        registry = MediaProviderRegistry()

        with self.assertRaises(KeyError):
            registry.get("unknown")

        with self.assertRaises(KeyError):
            registry.unregister("unknown")

        with self.assertRaises(KeyError):
            registry.supports("unknown", MediaAssetType.VIDEO)

    def test_supports_reports_asset_type_support(self) -> None:
        """Support checks use the provider's declared asset types."""
        registry = MediaProviderRegistry()
        registry.register(MockVideoProvider())

        self.assertTrue(registry.supports("mock-video", MediaAssetType.VIDEO))
        self.assertFalse(registry.supports("mock-video", MediaAssetType.IMAGE))

    def test_all_returns_a_copy(self) -> None:
        """Changing the returned list does not alter the registry."""
        registry = MediaProviderRegistry()
        provider = MockVideoProvider()
        registry.register(provider)

        providers = registry.all()
        providers.clear()

        self.assertEqual(registry.all(), [provider])

    def test_registry_instances_share_no_state(self) -> None:
        """Each registry stores providers independently."""
        first = MediaProviderRegistry()
        second = MediaProviderRegistry()

        first.register(MockVideoProvider())

        self.assertEqual(len(first.all()), 1)
        self.assertEqual(second.all(), [])


if __name__ == "__main__":
    unittest.main()
