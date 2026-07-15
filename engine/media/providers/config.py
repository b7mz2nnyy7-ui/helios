"""Environment-backed configuration for media provider adapters."""

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast


class ProviderConfigurationError(ValueError):
    """Raised when required media provider configuration is unavailable."""


@dataclass(frozen=True)
class ProviderConfig:
    """Immutable, provider-neutral media adapter configuration."""

    provider_id: str
    api_key: str | None = field(default=None, repr=False)
    base_url: str | None = None
    model: str | None = None
    timeout_seconds: float = 60.0
    max_attempts: int = 1
    enabled: bool = True
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate values and protect metadata from external mutation."""
        if not self.provider_id.strip():
            msg = "provider_id must not be empty."
            raise ValueError(msg)

        if self.timeout_seconds <= 0:
            msg = "timeout_seconds must be greater than 0."
            raise ValueError(msg)

        if self.max_attempts <= 0:
            msg = "max_attempts must be greater than 0."
            raise ValueError(msg)

        if self.base_url is not None and not self.base_url.strip():
            msg = "base_url must not be empty when configured."
            raise ValueError(msg)

        if self.model is not None and not self.model.strip():
            msg = "model must not be empty when configured."
            raise ValueError(msg)

        if not isinstance(self.metadata, dict):
            msg = "metadata must be a dictionary."
            raise ValueError(msg)

        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in self.metadata.items()
        ):
            msg = "metadata keys and values must be strings."
            raise ValueError(msg)

        protected_metadata = MappingProxyType(dict(self.metadata))
        object.__setattr__(
            self,
            "metadata",
            cast(dict[str, str], protected_metadata),
        )


def normalize_provider_id_for_env(provider_id: str) -> str:
    """Normalize a provider ID for HELIOS_MEDIA environment variables."""
    if not provider_id.strip():
        msg = "provider_id must not be empty."
        raise ValueError(msg)

    normalized = provider_id.upper().replace("-", "_")
    if re.fullmatch(r"[A-Z0-9_]+", normalized) is None:
        msg = "provider_id must contain only letters, numbers and hyphens."
        raise ValueError(msg)

    return normalized


def load_provider_config(
    provider_id: str,
    env: Mapping[str, str] = os.environ,
) -> ProviderConfig:
    """Load one provider configuration exclusively from an environment mapping."""
    normalized_id = normalize_provider_id_for_env(provider_id)
    prefix = f"HELIOS_MEDIA_{normalized_id}"
    return ProviderConfig(
        provider_id=provider_id,
        api_key=env.get(f"{prefix}_API_KEY"),
        base_url=env.get(f"{prefix}_BASE_URL"),
        model=env.get(f"{prefix}_MODEL"),
        timeout_seconds=_parse_float(
            env,
            f"{prefix}_TIMEOUT_SECONDS",
            default=60.0,
        ),
        max_attempts=_parse_int(
            env,
            f"{prefix}_MAX_ATTEMPTS",
            default=1,
        ),
        enabled=_parse_bool(
            env,
            f"{prefix}_ENABLED",
            default=True,
        ),
    )


def require_api_key(config: ProviderConfig) -> str:
    """Return a configured API key or raise a secret-safe error."""
    if config.api_key is None or not config.api_key.strip():
        msg = f"API key is required for media provider '{config.provider_id}'."
        raise ProviderConfigurationError(msg)

    return config.api_key


def _parse_float(
    env: Mapping[str, str],
    key: str,
    default: float,
) -> float:
    raw_value = env.get(key)
    if raw_value is None:
        return default

    try:
        return float(raw_value)
    except ValueError as error:
        msg = f"{key} must be a valid number."
        raise ValueError(msg) from error


def _parse_int(
    env: Mapping[str, str],
    key: str,
    default: int,
) -> int:
    raw_value = env.get(key)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError as error:
        msg = f"{key} must be a valid integer."
        raise ValueError(msg) from error


def _parse_bool(
    env: Mapping[str, str],
    key: str,
    default: bool,
) -> bool:
    raw_value = env.get(key)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False

    msg = f"{key} must be one of: true, false, 1, 0."
    raise ValueError(msg)
