"""Run exactly one explicitly authorized Runway generation request."""

import argparse
import math
import os
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TextIO

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.media.asset import MediaAsset, MediaAssetType  # noqa: E402
from engine.media.providers.base import MediaProviderError  # noqa: E402
from engine.media.providers.config import (  # noqa: E402
    ProviderConfig,
    load_provider_config,
    require_api_key,
)
from engine.media.storage import MediaStorage, StoredMediaAsset  # noqa: E402
from integrations.runway.client import RunwayClient, RunwayTransport  # noqa: E402
from integrations.runway.http_transport import (  # noqa: E402
    HTTPExecutor,
    RUNWAY_API_VERSION,
    RunwayHTTPTransport,
    UrllibHTTPExecutor,
    validate_runway_api_version,
)
from integrations.runway.models import (  # noqa: E402
    RunwayGenerationRequest,
    RUNWAY_TEXT_TO_VIDEO_MODELS,
    RunwayTask,
    validate_runway_text_to_video_contract,
)
from integrations.runway.polling import (  # noqa: E402
    Clock,
    RunwayPollingConfig,
    RunwayPollingResult,
    RunwayTaskPoller,
    Sleeper,
    SystemClock,
    SystemSleeper,
)

LIVE_ENABLED_ENV = "HELIOS_RUNWAY_LIVE_ENABLED"
RUNWAY_API_KEY_ENV = "HELIOS_MEDIA_RUNWAY_API_KEY"
RUNWAY_MODEL_ENV = "HELIOS_MEDIA_RUNWAY_MODEL"
RUNWAY_PRICE_ENV = "HELIOS_MEDIA_RUNWAY_PRICE_PER_SECOND_USD"
RUNWAY_API_VERSION_ENV = "HELIOS_MEDIA_RUNWAY_API_VERSION"
_POLLING_STATUSES = {"PENDING", "THROTTLED", "RUNNING"}
_FAILURE_STATUSES = {"FAILED", "CANCELED", "CANCELLED"}

PricingTable = Mapping[str, Decimal]
ExecutorFactory = Callable[[], HTTPExecutor]
TransportFactory = Callable[[HTTPExecutor], RunwayTransport]
StorageFactory = Callable[[HTTPExecutor], MediaStorage]


@dataclass(frozen=True)
class RunwayLiveTestResult:
    """Safe summary of one completed guarded Runway request."""

    task: RunwayTask
    poll_count: int
    elapsed_seconds: float
    model: str
    duration_seconds: float
    ratio: str
    estimated_cost_usd: Decimal
    stored_asset: StoredMediaAsset


def _default_storage_factory(executor: HTTPExecutor) -> MediaStorage:
    return MediaStorage(executor=executor)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments without activating live execution."""
    parser = argparse.ArgumentParser(
        description="Run one explicitly authorized Runway video test.",
    )
    parser.add_argument("prompt_text", help="Video generation prompt.")
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--ratio", default="1280:720")
    parser.add_argument("--model")
    parser.add_argument("--max-estimated-cost-usd", type=float)
    parser.add_argument(
        "--confirm-live-runway-request",
        action="store_true",
    )
    parser.add_argument(
        "--check-live-readiness",
        action="store_true",
    )
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--max-polls", type=int, default=150)
    return parser.parse_args(argv)


def estimate_runway_cost_usd(
    model: str,
    duration_seconds: float,
    pricing_table: PricingTable | None = None,
) -> float:
    """Estimate cost from an explicit model rate without fallback pricing."""
    return float(
        _estimate_runway_cost_decimal(
            model,
            duration_seconds,
            pricing_table,
        ),
    )


def run_guarded_live_test(
    args: argparse.Namespace,
    env: Mapping[str, str] = os.environ,
    pricing_table: PricingTable | None = None,
    executor_factory: ExecutorFactory = UrllibHTTPExecutor,
    transport_factory: TransportFactory = RunwayHTTPTransport,
    storage_factory: StorageFactory = _default_storage_factory,
    clock: Clock | None = None,
    sleeper: Sleeper | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Validate all guards, optionally execute once, and return an exit code."""
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    api_key = env.get(RUNWAY_API_KEY_ENV, "")

    try:
        prompt_text = _validate_text(args.prompt_text, "prompt_text")
        ratio = _validate_text(args.ratio, "ratio")
        polling_config = RunwayPollingConfig(
            poll_interval_seconds=args.poll_interval,
            timeout_seconds=args.timeout,
            max_polls=args.max_polls,
        )
        provider_config = _load_runway_config(env)
        model = _resolve_model(args.model, provider_config)
        api_version = env.get(RUNWAY_API_VERSION_ENV, RUNWAY_API_VERSION)
        contract_errors: list[str] = []
        try:
            validate_runway_api_version(api_version)
        except ValueError as error:
            if not args.check_live_readiness:
                raise
            contract_errors.append(str(error))

        request_duration: int | None = None
        if model is not None and model not in RUNWAY_TEXT_TO_VIDEO_MODELS:
            contract_errors.append(
                f"model '{model}' is not supported for Runway text-to-video.",
            )
        elif model is not None:
            try:
                request_duration = validate_runway_text_to_video_contract(
                    model,
                    prompt_text,
                    ratio,
                    args.duration,
                )
            except ValueError as error:
                if not args.check_live_readiness:
                    raise
                contract_errors.append(str(error))
        effective_pricing = (
            pricing_table
            if pricing_table is not None
            else _load_pricing_table(model, env)
        )
        estimated_cost = _try_estimate_cost(
            model,
            args.duration,
            effective_pricing,
        )
        price_per_second = _configured_price(model, effective_pricing)
    except Exception as error:
        print(
            f"Error: {_sanitize_error(error, api_key)}",
            file=error_output,
        )
        return 1

    blockers = _live_blockers(
        args=args,
        env=env,
        api_key=api_key,
        model=model,
        estimated_cost=estimated_cost,
        pricing_table=effective_pricing,
        contract_errors=contract_errors,
        require_confirmation=not args.check_live_readiness,
    )
    if args.check_live_readiness:
        print(
            _format_readiness(
                ready=not blockers,
                model=model,
                duration_seconds=args.duration,
                ratio=ratio,
                price_per_second=price_per_second,
                estimated_cost=estimated_cost,
                max_cost=args.max_estimated_cost_usd,
                polling_config=polling_config,
                live_enabled=(
                    env.get(LIVE_ENABLED_ENV, "").strip().lower() == "true"
                ),
                api_key_present=bool(api_key.strip()),
                api_key=api_key,
                api_version=api_version,
            ),
            file=output,
        )
        for blocker in blockers:
            print(f"- {_redact_secret(blocker, api_key)}", file=output)
        return 0 if not blockers else 2

    print(
        _format_safe_summary(
            prompt_text=prompt_text,
            model=model,
            duration_seconds=args.duration,
            ratio=ratio,
            estimated_cost=estimated_cost,
            api_key=api_key,
        ),
        file=output,
    )
    if blockers:
        print("LIVE REQUEST DISABLED", file=output)
        for blocker in blockers:
            print(f"- {_redact_secret(blocker, api_key)}", file=output)
        return 2

    try:
        if (
            model is None
            or request_duration is None
            or estimated_cost is None
            or args.max_estimated_cost_usd is None
        ):
            msg = "live safety guards did not resolve required configuration."
            raise RuntimeError(msg)
        max_cost = Decimal(str(args.max_estimated_cost_usd))
        if estimated_cost > max_cost:
            msg = "estimated cost exceeds the configured live limit."
            raise RuntimeError(msg)
        live_config = _config_with_model(provider_config, model)
        result = _execute_live_request(
            prompt_text=prompt_text,
            duration_seconds=request_duration,
            ratio=ratio,
            config=live_config,
            polling_config=polling_config,
            estimated_cost=estimated_cost,
            executor_factory=executor_factory,
            transport_factory=transport_factory,
            storage_factory=storage_factory,
            clock=clock or SystemClock(),
            sleeper=sleeper or SystemSleeper(),
        )
    except Exception as error:
        print(
            f"Live Runway error: {_sanitize_error(error, api_key)}",
            file=error_output,
        )
        return 1

    print(_format_live_result(result, api_key), file=output)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the guarded command and return its process exit code."""
    try:
        args = parse_args(argv)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 1
    return run_guarded_live_test(args)


def _execute_live_request(
    prompt_text: str,
    duration_seconds: int,
    ratio: str,
    config: ProviderConfig,
    polling_config: RunwayPollingConfig,
    estimated_cost: Decimal,
    executor_factory: ExecutorFactory,
    transport_factory: TransportFactory,
    storage_factory: StorageFactory,
    clock: Clock,
    sleeper: Sleeper,
) -> RunwayLiveTestResult:
    require_api_key(config)
    model = config.model
    if model is None:
        msg = "Runway model must be configured for a live request."
        raise ValueError(msg)

    executor = executor_factory()
    transport = transport_factory(executor)
    client = RunwayClient(config, transport)
    poller = RunwayTaskPoller(client, polling_config, clock, sleeper)
    request = RunwayGenerationRequest(
        model=model,
        prompt_text=prompt_text,
        ratio=ratio,
        duration_seconds=duration_seconds,
        seed=None,
    )
    created_task = client.create_video(request)
    polling_result = _resolve_created_task(created_task, poller)
    final_task = polling_result.task
    if final_task.status.strip().upper() != "SUCCEEDED":
        msg = (
            f"Runway task '{final_task.task_id}' did not finish successfully."
        )
        raise MediaProviderError(msg)
    if len(final_task.output_urls) != 1:
        msg = (
            f"Runway task '{final_task.task_id}' must provide exactly one output URL."
        )
        raise MediaProviderError(msg)

    source_asset = _create_runway_media_asset(final_task, model)
    stored_asset = storage_factory(executor).download_asset(source_asset)

    return RunwayLiveTestResult(
        task=final_task,
        poll_count=polling_result.poll_count,
        elapsed_seconds=polling_result.elapsed_seconds,
        model=model,
        duration_seconds=float(duration_seconds),
        ratio=ratio,
        estimated_cost_usd=estimated_cost,
        stored_asset=stored_asset,
    )


def _create_runway_media_asset(task: RunwayTask, model: str) -> MediaAsset:
    return MediaAsset(
        asset_id=task.task_id,
        asset_type=MediaAssetType.VIDEO,
        name=f"Runway video {task.task_id}",
        description="Completed guarded Runway video generation.",
        provider="runway",
        format="mp4",
        metadata={
            "runway_task_id": task.task_id,
            "output_url": task.output_urls[0],
            "output_url_is_temporary": True,
            "model": model,
        },
    )


def _resolve_created_task(
    task: RunwayTask,
    poller: RunwayTaskPoller,
) -> RunwayPollingResult:
    status = task.status.strip().upper()
    if status == "SUCCEEDED":
        return RunwayPollingResult(task, 0, 0.0)
    if status in _POLLING_STATUSES:
        return poller.wait_for_completion(task.task_id)
    if status in _FAILURE_STATUSES:
        msg = f"Runway task '{task.task_id}' ended with status '{status}'."
        raise MediaProviderError(msg)

    msg = f"Runway task '{task.task_id}' returned unknown status '{status}'."
    raise MediaProviderError(msg)


def _live_blockers(
    args: argparse.Namespace,
    env: Mapping[str, str],
    api_key: str,
    model: str | None,
    estimated_cost: Decimal | None,
    pricing_table: PricingTable,
    contract_errors: list[str],
    require_confirmation: bool = True,
) -> list[str]:
    blockers: list[str] = []
    blockers.extend(contract_errors)
    if require_confirmation and not args.confirm_live_runway_request:
        blockers.append("missing --confirm-live-runway-request")
    if env.get(LIVE_ENABLED_ENV, "").strip().lower() != "true":
        blockers.append(f"{LIVE_ENABLED_ENV} must be true")
    if not api_key.strip():
        blockers.append(f"{RUNWAY_API_KEY_ENV} is not configured")
    if args.max_estimated_cost_usd is None:
        blockers.append("--max-estimated-cost-usd is required")
    elif (
        not math.isfinite(args.max_estimated_cost_usd)
        or args.max_estimated_cost_usd <= 0
    ):
        blockers.append("--max-estimated-cost-usd must be greater than 0")
    if model is None:
        blockers.append("Runway model is not configured")
    elif model not in pricing_table or estimated_cost is None:
        blockers.append(f"no explicit pricing is configured for model '{model}'")
    elif (
        args.max_estimated_cost_usd is not None
        and math.isfinite(args.max_estimated_cost_usd)
    ):
        max_cost = Decimal(str(args.max_estimated_cost_usd))
        if estimated_cost > max_cost:
            blockers.append(
                f"estimated cost {_format_usd(estimated_cost)} exceeds limit "
                f"{_format_usd(max_cost)}",
            )
    return blockers


def _load_runway_config(env: Mapping[str, str]) -> ProviderConfig:
    normalized_env = dict(env)
    for key in (
        "HELIOS_MEDIA_RUNWAY_BASE_URL",
        RUNWAY_MODEL_ENV,
    ):
        if not normalized_env.get(key, "").strip():
            normalized_env.pop(key, None)
    return load_provider_config("runway", normalized_env)


def _config_with_model(config: ProviderConfig, model: str) -> ProviderConfig:
    return ProviderConfig(
        provider_id=config.provider_id,
        api_key=config.api_key,
        base_url=config.base_url,
        model=model,
        timeout_seconds=config.timeout_seconds,
        max_attempts=config.max_attempts,
        enabled=config.enabled,
        metadata=dict(config.metadata),
    )


def _resolve_model(
    cli_model: str | None,
    config: ProviderConfig,
) -> str | None:
    if cli_model is not None and cli_model.strip():
        return cli_model.strip()
    return config.model


def _load_pricing_table(
    model: str | None,
    env: Mapping[str, str],
) -> dict[str, Decimal]:
    if model is None:
        return {}
    raw_rate = env.get(RUNWAY_PRICE_ENV, "").strip()
    if not raw_rate:
        return {}
    try:
        rate = Decimal(raw_rate)
    except InvalidOperation:
        return {}
    if not rate.is_finite() or rate <= 0:
        return {}
    return {model: rate}


def _try_estimate_cost(
    model: str | None,
    duration_seconds: float,
    pricing_table: PricingTable,
) -> Decimal | None:
    price = _configured_price(model, pricing_table)
    if model is None or price is None:
        return None
    return price * Decimal(str(duration_seconds))


def _configured_price(
    model: str | None,
    pricing_table: PricingTable,
) -> Decimal | None:
    if model is None or model not in pricing_table:
        return None
    price = pricing_table[model]
    if not price.is_finite() or price <= 0:
        return None
    return price


def _estimate_runway_cost_decimal(
    model: str,
    duration_seconds: float,
    pricing_table: PricingTable | None,
) -> Decimal:
    clean_model = _validate_text(model, "model")
    if duration_seconds <= 0:
        msg = "duration_seconds must be greater than 0."
        raise ValueError(msg)
    if pricing_table is None or clean_model not in pricing_table:
        msg = f"No explicit Runway pricing is configured for model '{clean_model}'."
        raise ValueError(msg)

    rate = pricing_table[clean_model]
    if not rate.is_finite() or rate <= 0:
        msg = f"Configured Runway price for model '{clean_model}' is invalid."
        raise ValueError(msg)
    return rate * Decimal(str(duration_seconds))


def _format_safe_summary(
    prompt_text: str,
    model: str | None,
    duration_seconds: float,
    ratio: str,
    estimated_cost: Decimal | None,
    api_key: str,
) -> str:
    cost = "not configured" if estimated_cost is None else _format_usd(estimated_cost)
    return "\n".join(
        [
            "Guarded Runway Live Test",
            f"Prompt: {_redact_secret(prompt_text, api_key)}",
            f"Model: {_redact_secret(model or 'not configured', api_key)}",
            f"Duration: {duration_seconds}s",
            f"Ratio: {_redact_secret(ratio, api_key)}",
            f"Estimated maximum cost: {cost}",
        ],
    )


def _format_live_result(result: RunwayLiveTestResult, api_key: str) -> str:
    return "\n".join(
        [
            f"Task-ID: {result.task.task_id}",
            f"Final status: {result.task.status.upper()}",
            f"Poll count: {result.poll_count}",
            f"Elapsed seconds: {result.elapsed_seconds:.3f}",
            "Output stored successfully.",
            f"Stored: {result.stored_asset.local_path}",
            f"SHA256: {result.stored_asset.sha256}",
            f"File size: {result.stored_asset.size_bytes} bytes",
            f"Model: {_redact_secret(result.model, api_key)}",
            f"Duration: {result.duration_seconds}s",
            f"Ratio: {_redact_secret(result.ratio, api_key)}",
            f"Estimated maximum cost: {_format_usd(result.estimated_cost_usd)}",
        ],
    )


def _format_usd(value: Decimal) -> str:
    return f"${value:.6f}"


def _format_readiness(
    ready: bool,
    model: str | None,
    duration_seconds: float,
    ratio: str,
    price_per_second: Decimal | None,
    estimated_cost: Decimal | None,
    max_cost: float | None,
    polling_config: RunwayPollingConfig,
    live_enabled: bool,
    api_key_present: bool,
    api_key: str,
    api_version: str,
) -> str:
    readiness = "READY" if ready else "BLOCKED"
    price = (
        "not configured"
        if price_per_second is None
        else _format_usd(price_per_second)
    )
    estimate = (
        "not available" if estimated_cost is None else _format_usd(estimated_cost)
    )
    limit = (
        "not configured"
        if max_cost is None or not math.isfinite(max_cost)
        else _format_usd(Decimal(str(max_cost)))
    )
    return "\n".join(
        [
            f"RUNWAY LIVE READINESS: {readiness}",
            f"Model: {_redact_secret(model or 'not configured', api_key)}",
            f"Duration: {duration_seconds}s",
            f"Ratio: {_redact_secret(ratio, api_key)}",
            f"Price per second: {price}",
            f"Estimated cost: {estimate}",
            f"Cost limit: {limit}",
            f"Poll interval: {polling_config.poll_interval_seconds}s",
            f"Timeout: {polling_config.timeout_seconds}s",
            f"Maximum polls: {polling_config.max_polls}",
            f"Live switch active: {'yes' if live_enabled else 'no'}",
            f"API key present: {'yes' if api_key_present else 'no'}",
            f"API version: {_redact_secret(api_version, api_key)}",
        ],
    )


def _sanitize_error(error: Exception, api_key: str) -> str:
    return " ".join(_redact_secret(str(error), api_key).split())[:240]


def _redact_secret(value: str, api_key: str) -> str:
    sanitized = value
    if api_key:
        sanitized = sanitized.replace(api_key, "[REDACTED]")
    return re.sub(
        r"(?i)Bearer\s+\S+",
        "Bearer [REDACTED]",
        sanitized,
    )


def _validate_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        msg = f"{field_name} must not be empty."
        raise ValueError(msg)
    return value.strip()


if __name__ == "__main__":
    raise SystemExit(main())
