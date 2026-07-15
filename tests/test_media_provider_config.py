"""Tests for secure media provider configuration."""

import logging
import socket
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import cast
from unittest.mock import patch

from engine.media.providers.config import (
    ProviderConfig,
    ProviderConfigurationError,
    load_provider_config,
    normalize_provider_id_for_env,
    require_api_key,
)


class ProviderConfigTestCase(unittest.TestCase):
    """Tests for ProviderConfig and environment loading."""

    def test_valid_provider_config(self) -> None:
        """A complete provider configuration is immutable and valid."""
        config = ProviderConfig(
            provider_id="example-video",
            api_key="secret-value",
            base_url="https://example.invalid",
            model="video-model",
            timeout_seconds=30.0,
            max_attempts=2,
            enabled=True,
            metadata={"region": "local"},
        )

        self.assertEqual(config.provider_id, "example-video")
        self.assertEqual(config.metadata, {"region": "local"})
        with self.assertRaises(FrozenInstanceError):
            config.enabled = False  # type: ignore[misc]

    def test_empty_provider_id_is_rejected(self) -> None:
        """Provider IDs must contain non-whitespace characters."""
        with self.assertRaises(ValueError):
            ProviderConfig(provider_id="   ")

    def test_non_positive_timeout_is_rejected(self) -> None:
        """Timeouts must be greater than zero."""
        for timeout in (0.0, -1.0):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    ProviderConfig(
                        provider_id="example",
                        timeout_seconds=timeout,
                    )

    def test_non_positive_max_attempts_is_rejected(self) -> None:
        """Maximum attempts must be greater than zero."""
        for attempts in (0, -1):
            with self.subTest(attempts=attempts):
                with self.assertRaises(ValueError):
                    ProviderConfig(
                        provider_id="example",
                        max_attempts=attempts,
                    )

    def test_optional_text_values_must_not_be_empty(self) -> None:
        """Configured base URLs and models cannot be blank."""
        with self.assertRaises(ValueError):
            ProviderConfig(provider_id="example", base_url=" ")

        with self.assertRaises(ValueError):
            ProviderConfig(provider_id="example", model=" ")

    def test_metadata_requires_dictionary(self) -> None:
        """Metadata rejects non-dictionary values."""
        with self.assertRaises(ValueError):
            ProviderConfig(
                provider_id="example",
                metadata=cast(dict[str, str], []),
            )

    def test_metadata_is_protected_from_external_mutation(self) -> None:
        """Input and returned metadata cannot alter stored configuration."""
        metadata = {"region": "local"}
        config = ProviderConfig(provider_id="example", metadata=metadata)

        metadata["region"] = "external"
        self.assertEqual(config.metadata["region"], "local")
        with self.assertRaises(TypeError):
            config.metadata["region"] = "mutated"

    def test_provider_id_normalization(self) -> None:
        """Provider IDs map to safe uppercase environment names."""
        self.assertEqual(
            normalize_provider_id_for_env("mock-video-2"),
            "MOCK_VIDEO_2",
        )

        with self.assertRaises(ValueError):
            normalize_provider_id_for_env("mock.video")

    def test_environment_defaults(self) -> None:
        """Missing optional environment values use safe defaults."""
        config = load_provider_config("mock-video", env={})

        self.assertIsNone(config.api_key)
        self.assertIsNone(config.base_url)
        self.assertIsNone(config.model)
        self.assertEqual(config.timeout_seconds, 60.0)
        self.assertEqual(config.max_attempts, 1)
        self.assertTrue(config.enabled)
        self.assertEqual(config.metadata, {})

    def test_complete_environment_configuration(self) -> None:
        """Every supported environment value is loaded correctly."""
        config = load_provider_config(
            "mock-video",
            env={
                "HELIOS_MEDIA_MOCK_VIDEO_API_KEY": "secret-value",
                "HELIOS_MEDIA_MOCK_VIDEO_BASE_URL": "https://example.invalid",
                "HELIOS_MEDIA_MOCK_VIDEO_MODEL": "video-model",
                "HELIOS_MEDIA_MOCK_VIDEO_TIMEOUT_SECONDS": "15.5",
                "HELIOS_MEDIA_MOCK_VIDEO_MAX_ATTEMPTS": "3",
                "HELIOS_MEDIA_MOCK_VIDEO_ENABLED": "false",
            },
        )

        self.assertEqual(config.api_key, "secret-value")
        self.assertEqual(config.base_url, "https://example.invalid")
        self.assertEqual(config.model, "video-model")
        self.assertEqual(config.timeout_seconds, 15.5)
        self.assertEqual(config.max_attempts, 3)
        self.assertFalse(config.enabled)

    def test_invalid_float_is_rejected(self) -> None:
        """Invalid timeout values raise ValueError."""
        with self.assertRaises(ValueError):
            load_provider_config(
                "example",
                env={"HELIOS_MEDIA_EXAMPLE_TIMEOUT_SECONDS": "invalid"},
            )

    def test_invalid_integer_is_rejected(self) -> None:
        """Invalid attempt values raise ValueError."""
        with self.assertRaises(ValueError):
            load_provider_config(
                "example",
                env={"HELIOS_MEDIA_EXAMPLE_MAX_ATTEMPTS": "invalid"},
            )

    def test_supported_boolean_values(self) -> None:
        """Boolean parsing accepts true, false, one and zero."""
        expectations = {
            "true": True,
            "false": False,
            "1": True,
            "0": False,
        }
        for raw_value, expected in expectations.items():
            with self.subTest(raw_value=raw_value):
                config = load_provider_config(
                    "example",
                    env={"HELIOS_MEDIA_EXAMPLE_ENABLED": raw_value},
                )
                self.assertIs(config.enabled, expected)

    def test_invalid_boolean_is_rejected(self) -> None:
        """Unknown boolean syntax raises ValueError."""
        with self.assertRaises(ValueError):
            load_provider_config(
                "example",
                env={"HELIOS_MEDIA_EXAMPLE_ENABLED": "yes"},
            )

    def test_require_api_key(self) -> None:
        """A configured non-empty API key is returned unchanged."""
        config = ProviderConfig(provider_id="example", api_key="secret-value")

        self.assertEqual(require_api_key(config), "secret-value")

    def test_missing_api_key_raises_safe_error(self) -> None:
        """Missing and blank API keys raise configuration errors."""
        for api_key in (None, "   "):
            with self.subTest(api_key=api_key):
                config = ProviderConfig(provider_id="example", api_key=api_key)
                with self.assertRaises(ProviderConfigurationError) as context:
                    require_api_key(config)
                self.assertNotIn("secret-value", str(context.exception))

    def test_api_key_is_absent_from_repr_and_errors(self) -> None:
        """Configuration representations and validation errors hide secrets."""
        secret = "do-not-expose-this-key"
        config = ProviderConfig(provider_id="example", api_key=secret)

        self.assertNotIn(secret, repr(config))
        with self.assertRaises(ValueError) as context:
            ProviderConfig(
                provider_id="example",
                api_key=secret,
                timeout_seconds=0,
            )
        self.assertNotIn(secret, str(context.exception))

    def test_configuration_does_not_log_or_access_files_or_network(self) -> None:
        """Environment loading is silent and performs no external I/O."""
        secret = "do-not-log-this-key"
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            with (
                patch.object(logging.Logger, "_log") as log_call,
                patch.object(socket, "socket", side_effect=AssertionError("network")),
                patch.object(Path, "open", side_effect=AssertionError("file")),
            ):
                config = load_provider_config(
                    "example",
                    env={"HELIOS_MEDIA_EXAMPLE_API_KEY": secret},
                )
                self.assertEqual(require_api_key(config), secret)

            log_call.assert_not_called()
            self.assertEqual(list(directory.iterdir()), [])

    def test_readme_contains_no_test_secret(self) -> None:
        """Documentation never contains the test secret value."""
        readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")

        self.assertNotIn("do-not-expose-this-key", readme)


if __name__ == "__main__":
    unittest.main()
