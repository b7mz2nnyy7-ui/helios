"""Tests for configuration-aware media provider resolution."""

import socket
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.media.providers.config import (
    ProviderConfig,
    ProviderConfigurationError,
)
from engine.media.providers.factory import ProviderFactory
from engine.media.providers.mock_provider import MockVideoProvider
from engine.media.providers.registry import MediaProviderRegistry


def create_registry() -> MediaProviderRegistry:
    """Create a registry with the deterministic mock provider."""
    registry = MediaProviderRegistry()
    registry.register(MockVideoProvider())
    return registry


class ProviderFactoryTestCase(unittest.TestCase):
    """Tests for ProviderFactory state and provider resolution."""

    def test_factory_returns_config_and_provider(self) -> None:
        """Enabled configured providers can be resolved."""
        registry = create_registry()
        config = ProviderConfig(provider_id="mock-video")
        factory = ProviderFactory(registry, {"mock-video": config})

        self.assertIs(factory.get_config("mock-video"), config)
        self.assertTrue(factory.is_enabled("mock-video"))
        self.assertIs(factory.get_provider("mock-video"), registry.get("mock-video"))

    def test_disabled_provider_is_rejected_without_secret(self) -> None:
        """Disabled providers raise a secret-safe configuration error."""
        secret = "do-not-expose-this-key"
        factory = ProviderFactory(
            create_registry(),
            {
                "mock-video": ProviderConfig(
                    provider_id="mock-video",
                    api_key=secret,
                    enabled=False,
                ),
            },
        )

        with self.assertRaises(ProviderConfigurationError) as context:
            factory.get_provider("mock-video")

        self.assertNotIn(secret, str(context.exception))

    def test_unknown_configuration_raises_key_error(self) -> None:
        """Unknown configuration IDs raise KeyError."""
        factory = ProviderFactory(create_registry(), {})

        with self.assertRaises(KeyError):
            factory.get_config("unknown")

        with self.assertRaises(KeyError):
            factory.is_enabled("unknown")

        with self.assertRaises(KeyError):
            factory.get_provider("unknown")

    def test_provider_must_exist_in_registry(self) -> None:
        """Configuration alone never registers a provider."""
        registry = MediaProviderRegistry()
        factory = ProviderFactory(
            registry,
            {"mock-video": ProviderConfig(provider_id="mock-video")},
        )

        with self.assertRaises(KeyError):
            factory.get_provider("mock-video")

        self.assertEqual(registry.all(), [])

    def test_factory_does_not_mutate_registry_or_config_mapping(self) -> None:
        """Provider access leaves all supplied state unchanged."""
        registry = create_registry()
        config = ProviderConfig(provider_id="mock-video")
        configs = {"mock-video": config}
        providers_before = registry.all()

        factory = ProviderFactory(registry, configs)
        factory.get_provider("mock-video")

        self.assertEqual(registry.all(), providers_before)
        self.assertEqual(configs, {"mock-video": config})

    def test_factory_protects_itself_from_external_mapping_mutation(self) -> None:
        """Changing the source mapping does not alter factory state."""
        config = ProviderConfig(provider_id="mock-video")
        configs = {"mock-video": config}
        factory = ProviderFactory(create_registry(), configs)

        configs.clear()

        self.assertIs(factory.get_config("mock-video"), config)

    def test_factory_instances_share_no_state(self) -> None:
        """Each factory retains only its own copied configuration."""
        first = ProviderFactory(
            create_registry(),
            {"mock-video": ProviderConfig(provider_id="mock-video")},
        )
        second = ProviderFactory(MediaProviderRegistry(), {})

        self.assertIsInstance(first.get_provider("mock-video"), MockVideoProvider)
        with self.assertRaises(KeyError):
            second.get_config("mock-video")

    def test_factory_performs_no_file_or_network_io(self) -> None:
        """Factory lookups are entirely local and deterministic."""
        factory = ProviderFactory(
            create_registry(),
            {"mock-video": ProviderConfig(provider_id="mock-video")},
        )

        with (
            patch.object(socket, "socket", side_effect=AssertionError("network")),
            patch.object(Path, "open", side_effect=AssertionError("file")),
        ):
            provider = factory.get_provider("mock-video")

        self.assertEqual(provider.provider_id, "mock-video")


if __name__ == "__main__":
    unittest.main()
