"""Synchronous HTTP transport for the Runway API contract."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from engine.media.providers.base import MediaProviderError
from integrations.runway.models import RunwayGenerationRequest, RunwayTask

RUNWAY_API_VERSION = "2024-11-06"
_CREATE_VIDEO_PATH = "image_to_video"
_SUPPORTED_TASK_STATUSES = {
    "PENDING",
    "THROTTLED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELED",
    "CANCELLED",
}
_COMMON_HEADERS: Mapping[str, str] = MappingProxyType(
    {
        "X-Runway-Version": RUNWAY_API_VERSION,
        "Content-Type": "application/json",
        "Accept": "application/json",
    },
)


@dataclass(frozen=True)
class HTTPResponse:
    """Immutable response returned by an HTTP executor."""

    status_code: int
    headers: Mapping[str, str] = field(repr=False)
    body: bytes = field(repr=False)

    def __post_init__(self) -> None:
        """Validate response data and protect headers from mutation."""
        if (
            isinstance(self.status_code, bool)
            or not isinstance(self.status_code, int)
            or not 100 <= self.status_code <= 599
        ):
            msg = "status_code must be an integer between 100 and 599."
            raise ValueError(msg)

        if not isinstance(self.headers, Mapping):
            msg = "headers must be a mapping."
            raise ValueError(msg)

        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in self.headers.items()
        ):
            msg = "header names and values must be strings."
            raise ValueError(msg)

        if not isinstance(self.body, bytes):
            msg = "body must be bytes."
            raise ValueError(msg)

        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


class HTTPExecutor(Protocol):
    """Small synchronous HTTP execution boundary."""

    def execute(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> HTTPResponse:
        """Execute one HTTP request and return its raw response."""


class UrllibHTTPExecutor:
    """Standard-library HTTP executor for explicitly enabled live use."""

    def execute(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> HTTPResponse:
        """Execute one request using urllib without logging request data."""
        request = Request(
            url=url,
            data=body,
            headers=dict(headers),
            method=method,
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return HTTPResponse(
                    status_code=response.status,
                    headers=dict(response.headers.items()),
                    body=response.read(),
                )
        except HTTPError as error:
            response_headers = (
                dict(error.headers.items()) if error.headers is not None else {}
            )
            return HTTPResponse(
                status_code=error.code,
                headers=response_headers,
                body=error.read(),
            )


class RunwayHTTPTransport:
    """Map Runway transport calls to synchronous HTTP requests."""

    def __init__(self, executor: HTTPExecutor) -> None:
        """Create a transport around an injected HTTP executor."""
        self.executor = executor

    def create_video(
        self,
        request: RunwayGenerationRequest,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
    ) -> RunwayTask:
        """Create one video task through the Runway HTTP API."""
        if not isinstance(request, RunwayGenerationRequest):
            msg = "request must be a RunwayGenerationRequest."
            raise MediaProviderError(msg)

        payload: dict[str, str | float | int] = {
            "model": request.model,
            "promptText": request.prompt_text,
            "ratio": request.ratio,
            "duration": request.duration_seconds,
        }
        if request.seed is not None:
            payload["seed"] = request.seed

        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        response = self._execute(
            method="POST",
            url=_join_url(base_url, _CREATE_VIDEO_PATH),
            api_key=api_key,
            body=body,
            timeout_seconds=timeout_seconds,
        )
        return _parse_task_response(response, default_status="PENDING")

    def get_task(
        self,
        task_id: str,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
    ) -> RunwayTask:
        """Retrieve one task through a safely encoded path segment."""
        encoded_task_id = _encode_path_segment(task_id)
        response = self._execute(
            method="GET",
            url=_join_url(base_url, "tasks", encoded_task_id),
            api_key=api_key,
            body=None,
            timeout_seconds=timeout_seconds,
        )
        return _parse_task_response(response)

    def _execute(
        self,
        method: str,
        url: str,
        api_key: str,
        body: bytes | None,
        timeout_seconds: float,
    ) -> HTTPResponse:
        headers = _build_headers(api_key)
        if timeout_seconds <= 0:
            msg = "timeout_seconds must be greater than 0."
            raise MediaProviderError(msg)

        try:
            response = self.executor.execute(
                method,
                url,
                headers,
                body,
                timeout_seconds,
            )
        except Exception as error:
            msg = "Runway HTTP executor failed."
            raise MediaProviderError(msg) from error

        if not isinstance(response, HTTPResponse):
            msg = "HTTP executor must return an HTTPResponse."
            raise MediaProviderError(msg)

        if not 200 <= response.status_code <= 299:
            raise MediaProviderError(_format_http_error(response, api_key))

        return response


def _build_headers(api_key: str) -> dict[str, str]:
    if not isinstance(api_key, str) or not api_key.strip():
        msg = "Runway API key must not be empty."
        raise MediaProviderError(msg)

    return {
        **_COMMON_HEADERS,
        "Authorization": f"Bearer {api_key}",
    }


def _join_url(base_url: str, *path_segments: str) -> str:
    if not isinstance(base_url, str) or not base_url.strip():
        msg = "Runway base_url must not be empty."
        raise MediaProviderError(msg)

    path = "/".join(segment.strip("/") for segment in path_segments)
    return f"{base_url.rstrip('/')}/{path}"


def _encode_path_segment(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        msg = "task_id must not be empty."
        raise MediaProviderError(msg)

    encoded = quote(value, safe="-_")
    return encoded.replace(".", "%2E").replace("~", "%7E")


def _parse_task_response(
    response: HTTPResponse,
    default_status: str | None = None,
) -> RunwayTask:
    payload = _decode_json_object(response.body)
    task_id = payload.get("id")
    if not isinstance(task_id, str) or not task_id.strip():
        msg = "Runway response is missing a valid task id."
        raise MediaProviderError(msg)

    raw_status = payload.get("status", default_status)
    if not isinstance(raw_status, str) or not raw_status.strip():
        msg = f"Runway task '{task_id}' is missing a valid status."
        raise MediaProviderError(msg)

    status = raw_status.strip().upper()
    if status not in _SUPPORTED_TASK_STATUSES:
        msg = f"Runway task '{task_id}' returned unsupported status '{status}'."
        raise MediaProviderError(msg)

    raw_output = payload.get("output", [])
    if raw_output is None:
        raw_output = []
    if not isinstance(raw_output, list) or not all(
        isinstance(url, str) and url.strip() for url in raw_output
    ):
        msg = f"Runway task '{task_id}' returned an invalid output structure."
        raise MediaProviderError(msg)

    failure_message = payload.get("failure")
    if failure_message is None:
        failure_message = payload.get("failureMessage")
    if failure_message is not None and not isinstance(failure_message, str):
        msg = f"Runway task '{task_id}' returned an invalid failure message."
        raise MediaProviderError(msg)

    try:
        return RunwayTask(
            task_id=task_id,
            status=status,
            output_urls=tuple(raw_output),
            failure_message=failure_message,
        )
    except ValueError as error:
        msg = f"Runway task '{task_id}' contains invalid response data."
        raise MediaProviderError(msg) from error


def _decode_json_object(body: bytes) -> dict[str, object]:
    try:
        payload: object = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        msg = "Runway response contains invalid JSON."
        raise MediaProviderError(msg) from error

    if not isinstance(payload, dict):
        msg = "Runway response JSON must be an object."
        raise MediaProviderError(msg)

    if not all(isinstance(key, str) for key in payload):
        msg = "Runway response JSON keys must be strings."
        raise MediaProviderError(msg)

    return payload


def _format_http_error(response: HTTPResponse, api_key: str) -> str:
    prefix = f"Runway HTTP request failed with status {response.status_code}."
    try:
        payload = _decode_json_object(response.body)
    except MediaProviderError:
        return prefix

    candidate = payload.get("message")
    error_value = payload.get("error")
    if candidate is None and isinstance(error_value, str):
        candidate = error_value
    if candidate is None and isinstance(error_value, dict):
        candidate = error_value.get("message")
    if not isinstance(candidate, str) or not candidate.strip():
        return prefix

    sanitized = candidate.replace(api_key, "[REDACTED]")
    sanitized = re.sub(
        r"(?i)Bearer\s+\S+",
        "Bearer [REDACTED]",
        sanitized,
    )
    sanitized = " ".join(sanitized.split())[:160]
    return f"{prefix} Provider message: {sanitized}"
