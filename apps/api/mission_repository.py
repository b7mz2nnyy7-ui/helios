"""Thread-safe JSON repository for local Helios missions."""

from collections.abc import Mapping
from datetime import datetime
import json
from pathlib import Path
from threading import RLock
from typing import Any

from apps.api.mission_models import (
    Mission,
    MissionMediaAsset,
    MissionPipelineState,
    MissionPlatform,
    MissionStage,
    MissionStatus,
)

DEFAULT_MISSION_REPOSITORY_PATH = Path("output/missions/missions.json")
_REPOSITORY_VERSION = 1


class MissionRepository:
    """Store missions in memory with optional durable JSON persistence."""

    def __init__(self, storage_path: Path | None = None) -> None:
        """Create an isolated repository and load an existing JSON file."""
        if storage_path is not None and not isinstance(storage_path, Path):
            msg = "storage_path must be a Path or None."
            raise ValueError(msg)
        self.storage_path = storage_path
        self._missions: dict[str, Mission] = {}
        self._lock = RLock()
        if self.storage_path is not None and self.storage_path.exists():
            self._load()

    def register(self, mission: Mission) -> None:
        """Register and persist a new mission with a unique ID."""
        with self._lock:
            if mission.mission_id in self._missions:
                msg = f"Mission '{mission.mission_id}' is already registered."
                raise ValueError(msg)
            self._missions[mission.mission_id] = mission
            try:
                self._persist_locked()
            except Exception:
                del self._missions[mission.mission_id]
                raise

    def save(self, mission: Mission) -> None:
        """Replace and persist an existing mission atomically."""
        with self._lock:
            if mission.mission_id not in self._missions:
                raise KeyError(mission.mission_id)
            previous = self._missions[mission.mission_id]
            self._missions[mission.mission_id] = mission
            try:
                self._persist_locked()
            except Exception:
                self._missions[mission.mission_id] = previous
                raise

    def get(self, mission_id: str) -> Mission:
        """Return one mission or raise KeyError when it is unknown."""
        with self._lock:
            try:
                return self._missions[mission_id]
            except KeyError:
                raise KeyError(mission_id) from None

    def all(self) -> list[Mission]:
        """Return a newest-first snapshot of all mission history."""
        with self._lock:
            return sorted(
                self._missions.values(),
                key=lambda mission: (mission.created_at, mission.mission_id),
                reverse=True,
            )

    def count(self) -> int:
        """Return the number of registered missions."""
        with self._lock:
            return len(self._missions)

    def _load(self) -> None:
        if self.storage_path is None:
            return
        try:
            raw_document: object = json.loads(
                self.storage_path.read_text(encoding="utf-8"),
            )
            if not isinstance(raw_document, dict):
                raise ValueError
            if raw_document.get("version") != _REPOSITORY_VERSION:
                raise ValueError
            raw_missions = raw_document.get("missions")
            if not isinstance(raw_missions, list):
                raise ValueError
            missions = [_mission_from_dict(item) for item in raw_missions]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            msg = "Mission repository contains invalid data."
            raise ValueError(msg) from error
        for mission in missions:
            if mission.mission_id in self._missions:
                msg = "Mission repository contains duplicate IDs."
                raise ValueError(msg)
            self._missions[mission.mission_id] = mission

    def _persist_locked(self) -> None:
        if self.storage_path is None:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.storage_path.with_suffix(
            f"{self.storage_path.suffix}.tmp",
        )
        document = {
            "version": _REPOSITORY_VERSION,
            "missions": [
                _mission_to_dict(mission)
                for mission in sorted(
                    self._missions.values(),
                    key=lambda item: item.mission_id,
                )
            ],
        }
        try:
            temporary_path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            temporary_path.replace(self.storage_path)
        except OSError:
            temporary_path.unlink(missing_ok=True)
            raise


def _mission_to_dict(mission: Mission) -> dict[str, Any]:
    asset = mission.media_asset
    return {
        "id": mission.mission_id,
        "title": mission.title,
        "prompt": mission.prompt,
        "platform": mission.platform.value,
        "duration": mission.duration,
        "render_model": mission.render_model,
        "status": mission.status.value,
        "created_at": mission.created_at.isoformat(),
        "updated_at": mission.updated_at.isoformat(),
        "video_id": mission.video_id,
        "render_job_id": mission.render_job_id,
        "render_status": mission.render_status,
        "error_message": mission.error_message,
        "pipeline_state": {
            "current_stage": mission.pipeline_state.current_stage.value,
            "completed_stages": [
                stage.value for stage in mission.pipeline_state.completed_stages
            ],
            "completed_task_ids": list(
                mission.pipeline_state.completed_task_ids,
            ),
        },
        "media_asset": None
        if asset is None
        else {
            "asset_id": asset.asset_id,
            "asset_type": asset.asset_type,
            "name": asset.name,
            "description": asset.description,
            "provider": asset.provider,
            "format": asset.format,
            "metadata": _thaw_json(asset.metadata),
        },
    }


def _mission_from_dict(value: object) -> Mission:
    if not isinstance(value, dict):
        raise ValueError
    raw: dict[str, Any] = value
    pipeline = raw.get("pipeline_state")
    if not isinstance(pipeline, dict):
        raise ValueError
    completed_stages = pipeline.get("completed_stages")
    completed_task_ids = pipeline.get("completed_task_ids")
    if not isinstance(completed_stages, list) or not all(
        isinstance(item, str) for item in completed_stages
    ):
        raise ValueError
    if not isinstance(completed_task_ids, list) or not all(
        isinstance(item, str) for item in completed_task_ids
    ):
        raise ValueError
    asset = _asset_from_dict(raw.get("media_asset"))
    return Mission(
        mission_id=_required_string(raw.get("id")),
        title=_required_string(raw.get("title")),
        prompt=_required_string(raw.get("prompt")),
        platform=MissionPlatform(_required_string(raw.get("platform"))),
        duration=_required_int(raw.get("duration")),
        render_model=_required_string(raw.get("render_model")),
        status=MissionStatus(_required_string(raw.get("status"))),
        created_at=_required_datetime(raw.get("created_at")),
        updated_at=_required_datetime(raw.get("updated_at")),
        video_id=_optional_string(raw.get("video_id")),
        render_job_id=_optional_string(raw.get("render_job_id")),
        render_status=_optional_string(raw.get("render_status")),
        media_asset=asset,
        error_message=_optional_string(raw.get("error_message")),
        pipeline_state=MissionPipelineState(
            current_stage=MissionStage(
                _required_string(pipeline.get("current_stage")),
            ),
            completed_stages=tuple(
                MissionStage(item) for item in completed_stages
            ),
            completed_task_ids=tuple(completed_task_ids),
        ),
    )


def _asset_from_dict(value: object) -> MissionMediaAsset | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError
    metadata = value.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError
    return MissionMediaAsset(
        asset_id=_required_string(value.get("asset_id")),
        asset_type=_required_string(value.get("asset_type")),
        name=_required_string(value.get("name")),
        description=_required_string(value.get("description"), allow_empty=True),
        provider=_required_string(value.get("provider")),
        format=_required_string(value.get("format")),
        metadata=metadata,
    )


def _required_string(value: object, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return _required_string(value)


def _required_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError
    return value


def _required_datetime(value: object) -> datetime:
    return datetime.fromisoformat(_required_string(value))


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_thaw_json(item) for item in value]
    if isinstance(value, frozenset | set):
        return sorted(
            (_thaw_json(item) for item in value),
            key=repr,
        )
    return value
